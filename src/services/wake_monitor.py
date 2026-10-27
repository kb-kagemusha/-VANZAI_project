"""起床の監視（④ A2、0.54.0、DEC-126）。

期限（その日最初の勤務の開始 − 3時間）までに起床報告が無い稼働者へ公式LINEで催促し、
15分後も無ければ「起床報告が無い場合の連絡受け取り」を持つ運営の全員へ、案件ごとにまとめて知らせる。
知らせには1人ずつ「私が連絡します」ボタンを付け、押した人にだけ電話番号と結果のボタンを返し、
ほかの運営へ「○○さんが対応します」と知らせる。誰も押さなければ10分ごとに再通知する。
運営へ知らせたあとに本人から報告が届いたら、その運営へ「報告がありました」と知らせる。
送る前に wake_monitor_sends へ記録し、一意制約で同じ知らせを2回送らない。開始時刻を過ぎたら送らない。
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.base import generate_ulid
from src.models.enums import Permission
from src.models.line_daily import (
    WAKE_ALERT_DELAY_MINUTES,
    WAKE_CONTACT_CLAIM,
    WAKE_CONTACT_RESOLVED,
    WAKE_CONTACT_RESULTS,
    WAKE_DEADLINE_HOURS,
    WAKE_RENOTIFY_MINUTES,
    WakeMonitorSend,
)
from src.models.line_order import LINK_ACTIVE, LineWorkerLink
from src.models.operator_staff import LineStaffLink
from src.services import worker_schedule as ws
from src.services.audit import AuditService
from src.services.auth import has_permission

RESULT_BUTTONS = (("confirmed_awake", "起床を確認した"), ("no_answer", "電話がつながらない"), ("site_notified", "現場へ連絡した"), ("absent", "欠勤"))
ORANGE = "#B45309"
LOCK_KEY = 261027540


def deadline_for(day: date, first_start: str | None) -> tuple[datetime, datetime, datetime] | None:
    """(期限, 運営へ知らせる時刻, 開始時刻)。日本時間の tz なし。開始時刻が無ければ None。"""
    if not first_start:
        return None
    start = datetime.combine(day, time.fromisoformat(first_start))
    deadline = start - timedelta(hours=WAKE_DEADLINE_HOURS)
    return deadline, deadline + timedelta(minutes=WAKE_ALERT_DELAY_MINUTES), start


def _label(row: dict) -> str:
    return "【テスト】" if row["entries"] and all(e.get("is_test") for e in row["entries"]) else ""


def _first_entry(row: dict) -> dict:
    return row["entries"][0] if row["entries"] else {"project_name": "", "site_name": "", "start_time": None}


def _handler(contacts: list[dict]):
    handler = None
    for contact in contacts:
        if contact["result"] == WAKE_CONTACT_CLAIM:
            handler = contact
        elif contact["result"] in WAKE_CONTACT_RESOLVED:
            handler = None
    return handler


def _resolved(contacts: list[dict]) -> bool:
    results = [c["result"] for c in contacts if c["result"] != WAKE_CONTACT_CLAIM]
    return bool(results) and results[-1] in WAKE_CONTACT_RESOLVED


class WakeMonitorService:
    def __init__(self, db: Session, client=None):
        self.db = db
        self.is_test = False
        self.test_from = None
        self.test_until = None
        if client is None:
            from src.services.line_messaging import build_line_client
            client = build_line_client()
        self.client = client

    # ---- 送信先 -------------------------------------------------------------------------------
    def operator_recipients(self) -> list[tuple[str, object, object]]:
        """(LINEユーザー, 運営スタッフ, 管理画面ID)。連携・ID対応・権限を毎回確かめる。"""
        from src.services.line_operator import OperatorError, identity
        result = []
        for link in self.db.query(LineStaffLink).filter_by(status="active").order_by(LineStaffLink.line_user_id).all():
            try:
                _link, staff, user = identity(self.db, link.line_user_id)
            except OperatorError:
                continue
            if has_permission(user, Permission.WAKE_ALERT_RECEIVE):
                result.append((link.line_user_id, staff, user))
        return result

    def _worker_line(self, worker_id: str) -> str | None:
        link = self.db.query(LineWorkerLink).filter_by(worker_id=worker_id, status=LINK_ACTIVE).one_or_none()
        return link.line_user_id if link else None

    def _sent(self, worker_id: str, day: date, kind: str, round_no: int | None = None):
        query = self.db.query(WakeMonitorSend).filter_by(worker_id=worker_id, work_date=day, kind=kind, is_test=self.is_test)
        if self.is_test and self.test_from:
            query = query.filter(WakeMonitorSend.created_at >= self.test_from)
        if round_no is not None:
            query = query.filter_by(round=round_no)
        return query.all()

    def _reserve(self, worker_id: str, day: date, kind: str, round_no: int, recipient: str) -> WakeMonitorSend | None:
        """送る前に記録する。同じ知らせが既にあれば None（二重送信しない）。"""
        row = WakeMonitorSend(id=generate_ulid(), worker_id=worker_id, work_date=day, kind=kind, round=round_no,
                              recipient=recipient, is_test=self.is_test, status="pending", created_at=ws.now_utc())
        try:
            with self.db.begin_nested():
                self.db.add(row)
                self.db.flush()
        except IntegrityError:
            return None
        return row

    def _push(self, to: str, messages: list[dict], rows: list[WakeMonitorSend]) -> bool:
        from src.services.line_messaging import LineNotConfigured
        if self.is_test:
            from src.services.wake_test_notifications import utc
            if self.test_until is None or ws.now_utc() >= utc(self.test_until):
                for row in rows:
                    row.status = "skipped"
                self.db.flush()
                return False
        try:
            result = self.client.push_messages(to, messages)
            ok = result.status == 200
        except LineNotConfigured:
            ok = False
        except Exception:
            ok = False
        for row in rows:
            row.status = "sent" if ok else "failed"
        self.db.flush()
        return ok

    # ---- 定期の確認（毎分） --------------------------------------------------------------------
    def run(self, now_jst: datetime | None = None) -> dict:
        from src.services.wake_test_notifications import active, setting, utc
        now = now_jst or ws.now_utc().astimezone(ws.JST).replace(tzinfo=None)
        if self.db.bind.dialect.name == "postgresql":
            if not self.db.execute(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": LOCK_KEY}).scalar():
                return {"skipped": "running"}
        self.is_test = False
        counts = self._run_scope(now)
        config = setting(self.db)
        if active(config, now.replace(tzinfo=ws.JST)):
            self.is_test = True
            self.test_from, self.test_until = utc(config.enabled_from), utc(config.enabled_until)
            for key, value in self._run_scope(now).items():
                counts[key] += value
        self.is_test = False
        return counts

    def _run_scope(self, now):
        from src.services.wake_status import build_wake_status
        day = now.date()
        data = build_wake_status(self.db, day, include_test=self.is_test)
        counts = {"worker_reminder": 0, "operator_alert": 0, "operator_reported": 0}
        recipients = None
        groups: dict[tuple, list[tuple[dict, int]]] = {}
        for row in data["items"]:
            if self.is_test and not all(entry["is_test"] for entry in row["entries"]):
                continue  # Formal work always takes priority on mixed worker days.
            times = deadline_for(day, row["first_start"])
            if times is None:
                continue
            deadline, alert_at, start = times
            if self.is_test and deadline.replace(tzinfo=ws.JST) < self.test_from:
                continue  # Do not flush overdue test schedules when enabling.
            if row["wake_reported_at"] is not None:
                counts["operator_reported"] += self._notify_reported(row, day)
                continue
            if now >= start or now < deadline:
                continue
            if not self._sent(row["worker_id"], day, "worker_reminder"):
                counts["worker_reminder"] += self._remind_worker(row, day, start)
            if now < alert_at or _handler(row["contacts"]) is not None or _resolved(row["contacts"]):
                continue
            round_no = int((now - alert_at).total_seconds() // (WAKE_RENOTIFY_MINUTES * 60))
            if self._sent(row["worker_id"], day, "operator_alert", round_no):
                continue
            entry = _first_entry(row)
            key = (_label(row), entry["project_name"] or "", entry["site_name"] or "", row["first_start"])
            groups.setdefault(key, []).append((row, round_no))
        if groups:
            recipients = self.operator_recipients()
        for key, members in sorted(groups.items()):
            for line_user_id, _staff, _user in recipients or []:
                reserved = []
                for row, round_no in members:
                    sent = self._reserve(row["worker_id"], day, "operator_alert", round_no, line_user_id)
                    if sent is not None:
                        reserved.append((row, round_no, sent))
                if not reserved:
                    continue
                if self._push(line_user_id, [self._alert_message(key, [(r, n) for r, n, _ in reserved], day)], [s for _, _, s in reserved]):
                    counts["operator_alert"] += 1
            if not recipients:
                # 受け取る運営がいない。記録だけ残し、同じ回で繰り返し探さない
                for row, round_no in members:
                    sent = self._reserve(row["worker_id"], day, "operator_alert", round_no, "-")
                    if sent is not None:
                        sent.status = "skipped"
        self.db.flush()
        return counts

    def _remind_worker(self, row: dict, day: date, start: datetime) -> int:
        to = self._worker_line(row["worker_id"])
        reserved = self._reserve(row["worker_id"], day, "worker_reminder", 0, to or "-")
        if reserved is None:
            return 0
        if not to:
            reserved.status = "skipped"
            return 0
        entry = _first_entry(row)
        body = f"{_label(row)}{row['worker_name']}さん、今日 {start:%H:%M} 開始の「{entry['project_name'] or '案件'}」の起床報告がまだ届いていません。起きていたら、下のボタンを押してください。"
        message = {"type": "template", "altText": "起床報告がまだ届いていません",
                   "template": {"type": "buttons", "text": body[:160], "actions": [{"type": "postback", "label": "起きました（起床報告）", "data": "wk_wake", "displayText": "起床報告"}]}}
        ok = self._push(to, [message], [reserved])
        if ok:
            AuditService(self.db).log("wake_worker_reminded", target_type="worker", target_id=row["worker_id"], actor="wake-monitor", after_value={"date": day.isoformat()})
        return 1 if ok else 0

    def _notify_reported(self, row: dict, day: date) -> int:
        alerted = {s.recipient for s in self._sent(row["worker_id"], day, "operator_alert") if s.status == "sent"}
        if not alerted:
            return 0
        reported = datetime.fromisoformat(str(row["wake_reported_at"])) if not isinstance(row["wake_reported_at"], datetime) else row["wake_reported_at"]
        at = reported.astimezone(ws.JST) if reported.tzinfo else reported
        sent = 0
        for to in sorted(alerted):
            reserved = self._reserve(row["worker_id"], day, "operator_reported", 0, to)
            if reserved is None:
                continue
            text_value = f"{_label(row)}{row['worker_name']}さんから起床報告が届きました（{at:%H:%M}）。連絡は不要です。"
            if self._push(to, [{"type": "text", "text": text_value}], [reserved]):
                sent += 1
        return sent

    def _alert_message(self, key: tuple, members: list[tuple[dict, int]], day: date) -> dict:
        label, project, site, first_start = key
        times = deadline_for(day, first_start)
        deadline, _alert_at, start = times
        round_no = max(n for _, n in members)
        rows = []
        for row, _n in members:
            rows.append({"type": "box", "layout": "horizontal", "spacing": "md", "alignItems": "center", "contents": [
                {"type": "text", "text": f"{row['worker_name']}さん", "flex": 3, "wrap": True, "weight": "bold", "size": "md"},
                {"type": "button", "style": "primary", "color": ORANGE, "height": "sm", "flex": 4,
                 "action": {"type": "postback", "label": "私が連絡します", "data": f"wa_claim:{row['worker_id']}:{day.isoformat()}{':test' if self.is_test else ''}", "displayText": f"{row['worker_name']}さんに連絡します"}},
            ]})
        contents = [
            {"type": "text", "text": "起床報告がまだの方がいます", "weight": "bold", "color": ORANGE, "size": "sm"},
            {"type": "text", "text": f"{label}{project or '案件'}", "weight": "bold", "size": "lg", "wrap": True},
            {"type": "text", "text": f"{site + '　' if site else ''}{start:%H:%M}開始（報告の期限 {deadline:%H:%M}）", "size": "sm", "color": "#4B5563", "wrap": True},
            {"type": "separator", "margin": "md"},
            *rows,
        ]
        if round_no > 0:
            contents.append({"type": "text", "text": f"まだ誰も対応していません（{round_no + 1}回目のお知らせ）", "size": "xs", "color": "#9A3412", "wrap": True, "margin": "md"})
        names = "、".join(f"{row['worker_name']}さん" for row, _ in members)
        return {"type": "flex", "altText": f"{label}起床報告がまだ：{project or '案件'} {names}"[:400],
                "contents": {"type": "bubble", "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": contents}}}

    # ---- 運営が押したボタン（Webhook） ---------------------------------------------------------
    def handle_postback(self, line_user_id: str, data: str) -> tuple[str, list[dict], list[tuple[str, list[dict]]]]:
        """(記録用の結果, 本人への返信, ほかの人への知らせ[(宛先, メッセージ)])。"""
        from src.services.line_operator import LineOperatorService, OperatorError, identity
        from src.services.wake_test_notifications import lock
        lock(self.db)
        try:
            _link, staff, user = identity(self.db, line_user_id)
        except OperatorError:
            return "wake_alert_denied", [{"type": "text", "text": "この操作は運営スタッフだけができます。"}], []
        parts = data.split(":")
        try:
            action, worker_id, day = parts[0], parts[1], date.fromisoformat(parts[2])
        except (IndexError, ValueError):
            return "wake_alert_invalid", [{"type": "text", "text": "このボタンは使えません。運営メニューの起床状況から確認してください。"}], []
        service = LineOperatorService(self.db)
        test_button = parts[-1] == "test"
        try:
            if test_button:
                require_test_row = service._wake_row(day, worker_id)
                if not all(e["is_test"] for e in require_test_row["entries"]):
                    raise OperatorError(409, "テスト予定が変更されています。正式予定の操作は運営メニューから確認してください。")
            if action in ("wa_claim", "wa_take"):
                claim = service.claim(staff, user, day, worker_id, takeover=action == "wa_take")
                claim["is_test"] = test_button
                shares = self._share_claim(worker_id, day, staff.name, line_user_id, claim["worker_name"]) if claim["new_claim"] else []
                return "wake_alert_claimed", [self._claim_reply(claim, day)], shares
            if action == "wa_res":
                result = parts[3] if len(parts) > 3 else ""
                saved = service.record(staff, user, day, worker_id, result, "")
                return "wake_alert_recorded", [{"type": "text", "text": f"記録しました：{saved['result_label']}"}], []
        except OperatorError as exc:
            if exc.status == 409 and "対応中" in exc.message:
                return "wake_alert_busy", [{"type": "template", "altText": exc.message, "template": {"type": "buttons", "text": exc.message[:160], "actions": [
                    {"type": "postback", "label": "代わりに私が対応する", "data": f"wa_take:{worker_id}:{day.isoformat()}{':test' if test_button else ''}", "displayText": "代わりに私が対応します"}]}}], []
            return "wake_alert_rejected", [{"type": "text", "text": exc.message}], []
        return "wake_alert_invalid", [{"type": "text", "text": "このボタンは使えません。"}], []

    def _claim_reply(self, claim: dict, day: date) -> dict:
        contents = [
            {"type": "text", "text": "連絡をお願いします", "weight": "bold", "color": ORANGE, "size": "sm"},
            {"type": "text", "text": f"{claim['worker_name']}さん", "weight": "bold", "size": "xl", "wrap": True},
        ]
        if claim["phone"]:
            digits = "".join(ch for ch in claim["phone"] if ch.isdigit() or ch == "+")
            contents.append({"type": "button", "style": "primary", "color": "#0E7A52", "action": {"type": "uri", "label": f"電話する {claim['phone']}"[:40], "uri": f"tel:{digits}"}})
        else:
            contents.append({"type": "text", "text": "電話番号が登録されていません。管理画面の稼働者登録で確認してください。", "wrap": True, "color": "#9B1C14", "size": "sm"})
        contents.append({"type": "text", "text": "結果を押すと、ほかの運営にも記録が見えます。", "size": "xs", "color": "#4B5563", "wrap": True, "margin": "md"})
        for value, label in RESULT_BUTTONS:
            contents.append({"type": "button", "style": "secondary", "height": "sm", "action": {"type": "postback", "label": label, "data": f"wa_res:{claim['worker_id']}:{day.isoformat()}:{value}{':test' if claim.get('is_test') else ''}", "displayText": label}})
        return {"type": "flex", "altText": f"{claim['worker_name']}さんへの連絡", "contents": {"type": "bubble", "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": contents}}}

    def _share_claim(self, worker_id: str, day: date, staff_name: str, claimer: str, worker_name: str) -> list[tuple[str, list[dict]]]:
        from src.services.wake_status import build_wake_status
        from src.services.wake_test_notifications import active, setting, utc
        self.is_test = not any(row["worker_id"] == worker_id for row in build_wake_status(self.db, day, include_test=False)["items"])
        if self.is_test:
            config = setting(self.db)
            if not active(config):
                return []
            self.test_from, self.test_until = utc(config.enabled_from), utc(config.enabled_until)
        alerted = {s.recipient for s in self._sent(worker_id, day, "operator_alert") if s.status == "sent"} - {claimer, "-"}
        if not alerted:
            return []
        round_no = len(self._sent(worker_id, day, "operator_claimed")) and max(s.round for s in self._sent(worker_id, day, "operator_claimed")) + 1
        pushes = []
        for to in sorted(alerted):
            if self._reserve(worker_id, day, "operator_claimed", round_no, to) is None:
                continue
            pushes.append((to, [{"type": "text", "text": f"{'【テスト】' if self.is_test else ''}{worker_name}さんは、{staff_name}さんが連絡します。"}]))
        return pushes


def result_labels() -> dict:
    return {k: v for k, v in WAKE_CONTACT_RESULTS.items() if k != WAKE_CONTACT_CLAIM}
