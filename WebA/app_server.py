import base64
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import unicodedata
from datetime import datetime, timezone, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote, parse_qs
from uuid import uuid4

DB_FILE = os.path.join(os.path.dirname(__file__), "shared_reports.db")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
HOST = "0.0.0.0"
PORT = 8080
_UPLOAD_MAX_REQUEST_BYTES = 3 * 1024 * 1024    # クライアント圧縮後のbase64上限 (デコード後~2MB想定)
_UPLOAD_MAX_FILE_BYTES    = 2 * 1024 * 1024    # デコード後ファイル最大値 2MB

_SESSIONS: dict = {}          # token -> expiry (time.time())
_SESSION_TTL = 24 * 3600      # 24時間
_SESSIONS_LAST_CLEANUP = 0    # 最終クリーンアップ時刻
_SESSIONS_CLEANUP_INTERVAL = 3600  # 1時間ごとにクリーンアップ

# [SEC] ブルートフォース対策: IP別失敗記録
# { ip: {"count": int, "block_until": float, "first_fail": float} }
_LOGIN_FAIL: dict = {}
_LOGIN_MAX_FAIL = 5        # この回数失敗したらロック
_LOGIN_WINDOW   = 300      # 失敗カウントをリセットする期間（秒）
_LOGIN_LOCKOUT  = 900      # ロック時間（秒）= 15分
_MAJOR_ACTIONS = {
    "create_team",
    "delete_team",
    "rename_team",
    "create_report",
    "delete_reports",
    "reset_reports",
    "undo_delete",
    "upload_file",
    "add_member",
    "delete_member",
    "move_member",
}

_LOGIN_HTML = """<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>リーダーログイン</title>
<style>
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       display: flex; align-items: center; justify-content: center;
       min-height: 100vh; margin: 0; background: #f3f4f6; }
.card { background: #fff; border-radius: 14px; padding: 40px 32px;
        box-shadow: 0 2px 16px rgba(0,0,0,.12); width: min(360px, 92vw); }
h1 { font-size: 20px; margin: 0 0 24px; text-align: center; color: #111827; }
label { display: block; font-size: 13px; margin: 14px 0 5px; color: #374151; font-weight: 600; }
input { width: 100%; border: 1px solid #d1d5db; border-radius: 8px;
        padding: 11px 12px; font-size: 16px; }
input:focus { outline: none; border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,.15); }
button { margin-top: 22px; width: 100%; padding: 13px;
         background: #2563eb; color: #fff; border: none; border-radius: 8px;
         font-size: 16px; font-weight: 700; cursor: pointer; }
button:disabled { opacity: .6; cursor: default; }
.err { color: #dc2626; font-size: 13px; margin-top: 10px; min-height: 20px; text-align: center; }
</style>
</head>
<body>
<div class="card">
  <h1>&#128273; リーダーダッシュボード</h1>
  <label for="p">パスワード</label>
  <input id="p" type="password" autocomplete="current-password" autofocus>
  <button id="btn" onclick="login()">ログイン</button>
  <div class="err" id="err"></div>
</div>
<script>
async function login() {
  const btn = document.getElementById('btn');
  btn.disabled = true; btn.textContent = '確認中…';
  document.getElementById('err').textContent = '';
  const p = document.getElementById('p').value;
  try {
    const r = await fetch('/api/leader-login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({user: 'leader', pass: p})
    });
    if (r.ok) {
      location.reload();
    } else {
      document.getElementById('err').textContent = 'パスワードが違います';
      btn.disabled = false; btn.textContent = 'ログイン';
    }
  } catch(e) {
    document.getElementById('err').textContent = '通信エラーが発生しました';
    btn.disabled = false; btn.textContent = 'ログイン';
  }
}
document.addEventListener('keydown', e => { if (e.key === 'Enter') login(); });
</script>
</body>
</html>"""


def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            team TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(name, team)
        )
        """
    )

    # sort_order / is_leader カラムのマイグレーション
    member_cols = {r["name"] for r in cur.execute("PRAGMA table_info(members)").fetchall()}
    if "sort_order" not in member_cols:
        cur.execute("ALTER TABLE members ADD COLUMN sort_order INTEGER")
    if "is_leader" not in member_cols:
        cur.execute("ALTER TABLE members ADD COLUMN is_leader INTEGER NOT NULL DEFAULT 0")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            team TEXT NOT NULL,
            actor TEXT NOT NULL DEFAULT '未設定',
            result_type TEXT NOT NULL,
            report_no TEXT NOT NULL,
            purchase_at TEXT NOT NULL,
            store_name TEXT NOT NULL,
            store_address TEXT NOT NULL,
            receipt_file_name TEXT NOT NULL,
            comment TEXT NOT NULL,
            deleted_at TEXT,
            deleted_op_id TEXT,
            deleted_reason TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            at TEXT NOT NULL,
            op_id TEXT NOT NULL,
            action TEXT NOT NULL,
            actor TEXT NOT NULL DEFAULT 'unknown',
            target_type TEXT NOT NULL,
            target_id TEXT,
            details_json TEXT NOT NULL
        )
        """
    )

    cols = {r["name"] for r in cur.execute("PRAGMA table_info(reports)").fetchall()}
    if "deleted_at" not in cols:
        cur.execute("ALTER TABLE reports ADD COLUMN deleted_at TEXT")
    if "deleted_op_id" not in cols:
        cur.execute("ALTER TABLE reports ADD COLUMN deleted_op_id TEXT")
    if "deleted_reason" not in cols:
        cur.execute("ALTER TABLE reports ADD COLUMN deleted_reason TEXT")
    if "actor" not in cols:
        cur.execute("ALTER TABLE reports ADD COLUMN actor TEXT NOT NULL DEFAULT '未設定'")
    if "remaining_stock" not in cols:
        cur.execute("ALTER TABLE reports ADD COLUMN remaining_stock TEXT NOT NULL DEFAULT ''")

    audit_cols = {r["name"] for r in cur.execute("PRAGMA table_info(audit_logs)").fetchall()}
    if "actor" not in audit_cols:
        cur.execute("ALTER TABLE audit_logs ADD COLUMN actor TEXT NOT NULL DEFAULT 'unknown'")

    cur.execute("SELECT COUNT(*) AS c FROM teams")
    count = cur.fetchone()["c"]
    if count == 0:
        now = datetime.now(timezone.utc).isoformat()
        for name in ["チームA", "チームB", "チームC"]:
            cur.execute("INSERT INTO teams(name, created_at) VALUES(?, ?)", (name, now))

    cur.execute("SELECT COUNT(*) AS c FROM members")
    m_count = cur.fetchone()["c"]
    if m_count == 0:
        now = datetime.now(timezone.utc).isoformat()
        for team, names in [
            ("チームA", ["サンプル太郎", "テストマン"]),
            ("チームB", ["山田花子", "佐藤次郎"]),
            ("チームC", ["鈴木一郎"]),
        ]:
            for i, nm in enumerate(names):
                cur.execute(
                    "INSERT OR IGNORE INTO members(name, team, created_at, sort_order) VALUES(?, ?, ?, ?)",
                    (nm, team, now, i + 1),
                )

    # sort_order の NULL を id で埋める（既存行・遠降插入分のフォールバック）
    cur.execute("UPDATE members SET sort_order = id WHERE sort_order IS NULL")

    # --- スケジュール機能テーブル ---
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS member_profiles (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            team            TEXT NOT NULL,
            member_name     TEXT NOT NULL,
            home_area       TEXT NOT NULL DEFAULT '',
            work_area       TEXT NOT NULL DEFAULT '',
            transport_modes TEXT NOT NULL DEFAULT '',
            updated_at      TEXT NOT NULL,
            UNIQUE(team, member_name)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS member_schedules (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            team          TEXT NOT NULL,
            member_name   TEXT NOT NULL,
            schedule_date TEXT NOT NULL,
            availability  TEXT NOT NULL,
            updated_at    TEXT NOT NULL,
            UNIQUE(team, member_name, schedule_date)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS leader_assignments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            team        TEXT NOT NULL,
            member_name TEXT NOT NULL,
            assign_date TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            created_by  TEXT NOT NULL DEFAULT 'leader',
            UNIQUE(team, member_name, assign_date)
        )
        """
    )

    conn.commit()
    conn.close()

    # event_start_date マイグレーション
    conn = get_conn()
    cur = conn.cursor()
    teams_cols = {r["name"] for r in cur.execute("PRAGMA table_info(teams)").fetchall()}
    if "event_start_date" not in teams_cols:
        cur.execute("ALTER TABLE teams ADD COLUMN event_start_date TEXT NOT NULL DEFAULT ''")
    conn.commit()
    conn.close()

    # assignment_notes テーブル作成
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS assignment_notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            team        TEXT NOT NULL,
            member_name TEXT NOT NULL,
            note_date   TEXT NOT NULL,
            note_text   TEXT NOT NULL DEFAULT '',
            updated_at  TEXT NOT NULL,
            UNIQUE(team, member_name, note_date)
        )
        """
    )
    conn.commit()
    conn.close()

    # location_detail マイグレーション (member_schedules)
    conn = get_conn()
    cur = conn.cursor()
    sched_cols = {r["name"] for r in cur.execute("PRAGMA table_info(member_schedules)").fetchall()}
    if "location_detail" not in sched_cols:
        cur.execute("ALTER TABLE member_schedules ADD COLUMN location_detail TEXT NOT NULL DEFAULT ''")
    conn.commit()
    conn.close()

    # purchase_count マイグレーション (leader_assignments)
    conn = get_conn()
    cur = conn.cursor()
    asgn_cols = {r["name"] for r in cur.execute("PRAGMA table_info(leader_assignments)").fetchall()}
    if "purchase_count" not in asgn_cols:
        cur.execute("ALTER TABLE leader_assignments ADD COLUMN purchase_count INTEGER NOT NULL DEFAULT 1")
    conn.commit()
    conn.close()


class AppHandler(SimpleHTTPRequestHandler):
    # [SEC] Actor値を最大64文字に制限し、制御文字を除外
    _ACTOR_MAX_LEN = 64

    def _leader_user(self):
        return os.environ.get("LEADER_USER", "leader")

    def _leader_pass(self):
        pw = os.environ.get("LEADER_PASS", "")
        if not pw:
            import sys
            print("[WARN] LEADER_PASS is not set! Defaulting to '1111'. Set env var before production use.", file=sys.stderr)
            return "1111"
        return pw

    def _client_ip(self):
        """X-Forwarded-For (Nginx経由) またはソースIPを返す"""
        xff = self.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
        return self.client_address[0]

    def _is_login_blocked(self, ip):
        """IPがロック中なら True を返す。期限切れ・ウィンドウ切れはクリア。"""
        rec = _LOGIN_FAIL.get(ip)
        if not rec:
            return False
        now = time.time()
        if now < rec.get("block_until", 0):
            return True
        # ウィンドウ超過は自動解除
        if now - rec.get("first_fail", 0) > _LOGIN_WINDOW:
            del _LOGIN_FAIL[ip]
            return False
        return False

    def _record_login_fail(self, ip):
        now = time.time()
        rec = _LOGIN_FAIL.get(ip)
        if rec is None or now - rec.get("first_fail", 0) > _LOGIN_WINDOW:
            _LOGIN_FAIL[ip] = {"count": 1, "block_until": 0, "first_fail": now}
        else:
            rec["count"] += 1
            if rec["count"] >= _LOGIN_MAX_FAIL:
                rec["block_until"] = now + _LOGIN_LOCKOUT

    def _clear_login_fail(self, ip):
        _LOGIN_FAIL.pop(ip, None)

    def _cleanup_sessions(self):
        """期限切れセッションとログイン失敗レコードを定期的に削除"""
        global _SESSIONS_LAST_CLEANUP
        now = time.time()
        if now - _SESSIONS_LAST_CLEANUP < _SESSIONS_CLEANUP_INTERVAL:
            return
        _SESSIONS_LAST_CLEANUP = now
        expired_tokens = [t for t, exp in list(_SESSIONS.items()) if exp <= now]
        for t in expired_tokens:
            del _SESSIONS[t]
        expired_ips = [ip for ip, rec in list(_LOGIN_FAIL.items())
                       if now - rec.get("first_fail", 0) > max(_LOGIN_WINDOW, _LOGIN_LOCKOUT)]
        for ip in expired_ips:
            del _LOGIN_FAIL[ip]

    def _is_https_request(self):
        """NginxがX-Forwarded-Protoを付けている場合にHTTPS判定"""
        return self.headers.get("X-Forwarded-Proto", "").lower() == "https"

    def _is_leader_authorized(self):
        # --- Cookie session ---
        for part in self.headers.get("Cookie", "").split(";"):
            kv = part.strip()
            if kv.startswith("leader_session="):
                token = kv[len("leader_session="):]
                # [SEC] トークンにhex64文字のみ許可（不正文字を弾く）
                if not re.match(r'^[0-9a-f]{64}$', token):
                    continue
                if _SESSIONS.get(token, 0) > time.time():
                    return True
        # --- Basic Auth (fallback) ---
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return False
        raw = auth[6:].strip()
        try:
            decoded = base64.b64decode(raw).decode("utf-8")
        except Exception:
            return False
        if ":" not in decoded:
            return False
        user, password = decoded.split(":", 1)
        return hmac.compare_digest(user, self._leader_user()) and hmac.compare_digest(password, self._leader_pass())

    def _require_leader_auth(self):
        body = _LOGIN_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _needs_leader_auth(self, method, parts):
        if parts == ["leader.html"]:
            return True

        if method == "GET":
            if len(parts) >= 3 and parts[0] == "api" and parts[1] == "summary":
                return True
            if parts in (["api", "reports"], ["api", "deletions"], ["api", "logs"]):
                return True
            if len(parts) >= 2 and parts[0] == "api" and parts[1] == "logs":
                return True

        if method == "POST":
            if parts in (["api", "teams"], ["api", "members"], ["api", "reports", "delete"], ["api", "deletions", "undo"]):
                return True
            if parts == ["api", "members", "reorder"]:
                return True

        if method == "PUT":
            if parts == ["api", "assignments", "bulk"]:
                return True
            if parts == ["api", "team-settings"]:
                return True
            if parts == ["api", "assignment-notes"]:
                return True

        if method == "DELETE":
            if parts == ["api", "reports"]:
                return True
            if len(parts) == 3 and parts[0] == "api" and parts[1] in ("teams", "members"):
                return True
            if parts == ["api", "assignments"]:
                return True
            if parts == ["api", "schedules"]:
                return True

        if method == "PATCH":
            if len(parts) == 3 and parts[0] == "api" and parts[1] in ("members", "teams"):
                return True
            if len(parts) == 3 and parts[0] == "api" and parts[1] == "reports":
                return True

        return False

    def _query_summary(self, conn, where, params):
        """report_no / actor / total でまとめて集計して返す"""
        rows_rn = conn.execute(
            f"SELECT report_no, COUNT(*) AS c FROM reports {where} GROUP BY report_no",
            params,
        ).fetchall()
        rows_actor = conn.execute(
            f"SELECT actor, COUNT(*) AS c FROM reports {where} GROUP BY actor",
            params,
        ).fetchall()
        # actor × report_no クロス集計（メンバー別カテゴリー内訳用）
        rows_actor_rn = conn.execute(
            f"SELECT actor, report_no, COUNT(*) AS c FROM reports {where} GROUP BY actor, report_no",
            params,
        ).fetchall()
        total_row = conn.execute(
            f"SELECT COUNT(*) AS c FROM reports {where}",
            params,
        ).fetchone()
        by_report_no = {}
        for r in rows_rn:
            by_report_no[r["report_no"]] = int(r["c"])
        by_actor = {}
        for r in rows_actor:
            by_actor[r["actor"]] = int(r["c"])
        # { actor: { report_no: count } }
        by_actor_detail = {}
        for r in rows_actor_rn:
            actor = r["actor"]
            if actor not in by_actor_detail:
                by_actor_detail[actor] = {}
            by_actor_detail[actor][r["report_no"]] = int(r["c"])
        return {
            "total": int(total_row["c"]) if total_row else 0,
            "byReportNo": by_report_no,
            "byActor": by_actor,
            "byActorDetail": by_actor_detail,
        }

    def _actor(self):
        from urllib.parse import unquote
        raw = (self.headers.get("X-Actor", "") or "").strip()
        try:
            raw = unquote(raw)
        except Exception:
            pass
        # 制御文字・サロゲート等の不正文字を除去（全角スペース等のUnicode空白類は保持）
        raw = "".join(c for c in raw if unicodedata.category(c) not in ('Cc', 'Cf', 'Cs', 'Co', 'Cn'))
        actor = raw[: self._ACTOR_MAX_LEN]
        return actor if actor else "unknown"

    def _now_iso(self):
        return datetime.now(timezone.utc).isoformat()

    def _new_op_id(self):
        return f"op_{uuid4().hex}"

    def _write_log(self, conn, action, target_type, target_id, details, op_id=None):
        op = op_id or self._new_op_id()
        actor = self._actor()
        merged = dict(details or {})
        merged["actor"] = actor
        conn.execute(
            """
            INSERT INTO audit_logs(at, op_id, action, actor, target_type, target_id, details_json)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self._now_iso(),
                op,
                str(action),
                actor,
                str(target_type),
                str(target_id) if target_id is not None else None,
                json.dumps(merged, ensure_ascii=False),
            ),
        )
        return op

    def _soft_delete_reports(self, conn, report_ids, reason):
        ids = [str(x).strip() for x in report_ids if str(x).strip()]
        if not ids:
            return {"opId": None, "affected": 0}

        op_id = self._new_op_id()
        now = self._now_iso()
        placeholders = ",".join(["?"] * len(ids))
        params = [now, op_id, str(reason)] + ids
        cur = conn.execute(
            f"""
            UPDATE reports
               SET deleted_at = ?,
                   deleted_op_id = ?,
                   deleted_reason = ?
             WHERE deleted_at IS NULL
               AND id IN ({placeholders})
            """,
            params,
        )
        affected = int(cur.rowcount or 0)
        self._write_log(
            conn,
            action="delete_reports",
            target_type="reports",
            target_id=op_id,
            details={"reason": reason, "ids": ids, "affected": affected},
            op_id=op_id,
        )
        return {"opId": op_id, "affected": affected}

    def _soft_delete_all_reports(self, conn, reason):
        op_id = self._new_op_id()
        now = self._now_iso()
        cur = conn.execute(
            """
            UPDATE reports
               SET deleted_at = ?,
                   deleted_op_id = ?,
                   deleted_reason = ?
             WHERE deleted_at IS NULL
            """,
            (now, op_id, str(reason)),
        )
        affected = int(cur.rowcount or 0)
        self._write_log(
            conn,
            action="reset_reports",
            target_type="reports",
            target_id=op_id,
            details={"reason": reason, "affected": affected},
            op_id=op_id,
        )
        return {"opId": op_id, "affected": affected}

    def _undo_delete(self, conn, op_id):
        cur = conn.execute(
            """
            UPDATE reports
               SET deleted_at = NULL,
                   deleted_op_id = NULL,
                   deleted_reason = NULL
             WHERE deleted_op_id = ?
               AND deleted_at IS NOT NULL
            """,
            (str(op_id),),
        )
        affected = int(cur.rowcount or 0)
        self._write_log(
            conn,
            action="undo_delete",
            target_type="reports",
            target_id=str(op_id),
            details={"undoOpId": str(op_id), "affected": affected},
        )
        return {"affected": affected}

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # [SEC] セキュリティレスポンスヘッダ
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    # [SEC] リクエストボディ最大サイズ: 1MB
    _MAX_BODY_BYTES = 1 * 1024 * 1024

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except (ValueError, TypeError):
            length = 0
        if length > self._MAX_BODY_BYTES:
            raise ValueError(f"Request body too large ({length} bytes, max {self._MAX_BODY_BYTES})")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _path_parts(self):
        parsed = urlparse(self.path)
        return [p for p in parsed.path.split("/") if p]

    def do_GET(self):
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]

        # ルートアクセスはスタッフ用アプリへリダイレクト
        if parsed.path == "/" or parsed.path == "":
            self.send_response(302)
            self.send_header("Location", "/mobile-report-app.html")
            self.end_headers()
            return

        # ディレクトリ一覧を無効化
        if not parts or (len(parts) >= 1 and parts[-1] == ""):
            self.send_response(403)
            self.end_headers()
            return

        if self._needs_leader_auth("GET", parts) and not self._is_leader_authorized():
            return self._require_leader_auth()

        if len(parts) >= 1 and parts[0] == "api":
            if parts == ["api", "health"]:
                return self._send_json(200, {"ok": True, "mode": "sqlite"})

            if parts == ["api", "summary", "range"]:
                query = parse_qs(parsed.query)
                start_str = (query.get("start", [""])[0] or "").strip()
                end_str = (query.get("end", [""])[0] or "").strip()
                team = (query.get("team", [""])[0] or "").strip()
                if not start_str or not end_str:
                    return self._send_json(400, {"error": "start and end are required (YYYY-MM-DD)"})

                try:
                    start_date = datetime.fromisoformat(start_str).date()
                    end_date = datetime.fromisoformat(end_str).date()
                except ValueError:
                    return self._send_json(400, {"error": "invalid date format, expected YYYY-MM-DD"})

                if start_date > end_date:
                    return self._send_json(400, {"error": "start must be <= end"})

                diff_days = (end_date - start_date).days + 1
                prev_end = start_date - timedelta(days=1)
                prev_start = prev_end - timedelta(days=diff_days - 1)

                _JST = "CASE WHEN purchase_at LIKE '%Z' THEN substr(datetime(replace(purchase_at,'Z',''),'+9 hours'),1,10) ELSE substr(purchase_at,1,10) END"
                conn = get_conn()
                base_where = f"WHERE deleted_at IS NULL AND {_JST} BETWEEN ? AND ?"
                base_params = [start_str, end_str]
                prev_params = [prev_start.isoformat(), prev_end.isoformat()]
                if team and team != "__ALL__":
                    base_where += " AND team = ?"
                    base_params.append(team)
                    prev_params.append(team)
                prev_where = f"WHERE deleted_at IS NULL AND {_JST} BETWEEN ? AND ?"
                if team and team != "__ALL__":
                    prev_where += " AND team = ?"

                cur_data = self._query_summary(conn, base_where, base_params)
                prev_data = self._query_summary(conn, prev_where, prev_params)
                conn.close()

                return self._send_json(200, {
                    "startDate": start_str,
                    "endDate": end_str,
                    "team": team or "__ALL__",
                    "total": cur_data["total"],
                    "byReportNo": cur_data["byReportNo"],
                    "byActor": cur_data["byActor"],
                    "byActorDetail": cur_data["byActorDetail"],
                    "prevTotal": prev_data["total"],
                    "prevByReportNo": prev_data["byReportNo"],
                    "prevStartDate": prev_start.isoformat(),
                    "prevEndDate": prev_end.isoformat(),
                })

            if parts == ["api", "summary", "daily"]:
                query = parse_qs(parsed.query)
                day = (query.get("date", [""])[0] or "").strip()
                team = (query.get("team", [""])[0] or "").strip()
                if not day:
                    day = datetime.now().strftime("%Y-%m-%d")

                try:
                    day_date = datetime.fromisoformat(day).date()
                except ValueError:
                    return self._send_json(400, {"error": "invalid date format, expected YYYY-MM-DD"})
                prev_day = (day_date - timedelta(days=1)).isoformat()

                _JST = "CASE WHEN purchase_at LIKE '%Z' THEN substr(datetime(replace(purchase_at,'Z',''),'+9 hours'),1,10) ELSE substr(purchase_at,1,10) END"
                conn = get_conn()
                team_clause = ""
                team_val = []
                if team and team != "__ALL__":
                    team_clause = " AND team = ?"
                    team_val = [team]

                cur_where  = f"WHERE deleted_at IS NULL AND {_JST} = ?" + team_clause
                prev_where = f"WHERE deleted_at IS NULL AND {_JST} = ?" + team_clause

                cur_data  = self._query_summary(conn, cur_where,  [day]      + team_val)
                prev_data = self._query_summary(conn, prev_where, [prev_day] + team_val)
                conn.close()

                return self._send_json(200, {
                    "date": day,
                    "team": team or "__ALL__",
                    "total": cur_data["total"],
                    "byReportNo": cur_data["byReportNo"],
                    "byActor": cur_data["byActor"],
                    "byActorDetail": cur_data["byActorDetail"],
                    "prevTotal": prev_data["total"],
                    "prevByReportNo": prev_data["byReportNo"],
                    "prevDate": prev_day,
                })

            if parts == ["api", "summary", "weekly"]:
                query = parse_qs(parsed.query)
                end_date_str = (query.get("date", [""])[0] or "").strip()
                team = (query.get("team", [""])[0] or "").strip()
                days_raw = (query.get("days", ["7"])[0] or "7").strip()

                try:
                    days = int(days_raw)
                except ValueError:
                    days = 7
                days = max(1, min(days, 31))

                if end_date_str:
                    try:
                        end_date = datetime.fromisoformat(end_date_str).date()
                    except ValueError:
                        return self._send_json(400, {"error": "invalid date format, expected YYYY-MM-DD"})
                else:
                    end_date = datetime.now().date()

                start_date = end_date - timedelta(days=days - 1)
                start_str  = start_date.isoformat()
                end_str    = end_date.isoformat()
                prev_end   = start_date - timedelta(days=1)
                prev_start = prev_end - timedelta(days=days - 1)

                _JST = "CASE WHEN purchase_at LIKE '%Z' THEN substr(datetime(replace(purchase_at,'Z',''),'+9 hours'),1,10) ELSE substr(purchase_at,1,10) END"
                conn = get_conn()
                base_where = f"WHERE deleted_at IS NULL AND {_JST} BETWEEN ? AND ?"
                team_clause = ""
                team_val = []
                if team and team != "__ALL__":
                    team_clause = " AND team = ?"
                    team_val = [team]
                cur_where  = base_where + team_clause
                prev_where = base_where + team_clause

                cur_data  = self._query_summary(conn, cur_where,  [start_str, end_str]                          + team_val)
                prev_data = self._query_summary(conn, prev_where, [prev_start.isoformat(), prev_end.isoformat()] + team_val)
                conn.close()

                return self._send_json(200, {
                    "startDate": start_str,
                    "endDate": end_str,
                    "days": days,
                    "team": team or "__ALL__",
                    "total": cur_data["total"],
                    "byReportNo": cur_data["byReportNo"],
                    "byActor": cur_data["byActor"],
                    "byActorDetail": cur_data["byActorDetail"],
                    "prevTotal": prev_data["total"],
                    "prevByReportNo": prev_data["byReportNo"],
                    "prevStartDate": prev_start.isoformat(),
                    "prevEndDate": prev_end.isoformat(),
                })

            if parts == ["api", "summary", "monthly"]:
                query = parse_qs(parsed.query)
                end_date_str = (query.get("date", [""])[0] or "").strip()
                team = (query.get("team", [""])[0] or "").strip()
                days_raw = (query.get("days", ["30"])[0] or "30").strip()

                try:
                    days = int(days_raw)
                except ValueError:
                    days = 30
                days = max(1, min(days, 92))

                if end_date_str:
                    try:
                        end_date = datetime.fromisoformat(end_date_str).date()
                    except ValueError:
                        return self._send_json(400, {"error": "invalid date format, expected YYYY-MM-DD"})
                else:
                    end_date = datetime.now().date()

                start_date = end_date - timedelta(days=days - 1)
                start_str  = start_date.isoformat()
                end_str    = end_date.isoformat()
                prev_end   = start_date - timedelta(days=1)
                prev_start = prev_end - timedelta(days=days - 1)

                _JST = "CASE WHEN purchase_at LIKE '%Z' THEN substr(datetime(replace(purchase_at,'Z',''),'+9 hours'),1,10) ELSE substr(purchase_at,1,10) END"
                conn = get_conn()
                base_where = f"WHERE deleted_at IS NULL AND {_JST} BETWEEN ? AND ?"
                team_clause = ""
                team_val = []
                if team and team != "__ALL__":
                    team_clause = " AND team = ?"
                    team_val = [team]
                cur_where  = base_where + team_clause
                prev_where = base_where + team_clause

                cur_data  = self._query_summary(conn, cur_where,  [start_str, end_str]                          + team_val)
                prev_data = self._query_summary(conn, prev_where, [prev_start.isoformat(), prev_end.isoformat()] + team_val)
                conn.close()

                return self._send_json(200, {
                    "startDate": start_str,
                    "endDate": end_str,
                    "days": days,
                    "team": team or "__ALL__",
                    "total": cur_data["total"],
                    "byReportNo": cur_data["byReportNo"],
                    "byActor": cur_data["byActor"],
                    "byActorDetail": cur_data["byActorDetail"],
                    "prevTotal": prev_data["total"],
                    "prevByReportNo": prev_data["byReportNo"],
                    "prevStartDate": prev_start.isoformat(),
                    "prevEndDate": prev_end.isoformat(),
                })

            if parts == ["api", "teams"]:
                conn = get_conn()
                rows = conn.execute("SELECT name FROM teams ORDER BY name ASC").fetchall()
                conn.close()
                return self._send_json(200, [{"name": r["name"]} for r in rows])

            if parts == ["api", "members"]:
                query = parse_qs(parsed.query)
                team = (query.get("team", [""])[0] or "").strip()
                conn = get_conn()
                if team:
                    rows = conn.execute(
                        "SELECT id, name, team, is_leader FROM members WHERE team = ? ORDER BY is_leader DESC, sort_order ASC, id ASC",
                        (team,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT id, name, team, is_leader FROM members ORDER BY team ASC, is_leader DESC, sort_order ASC, id ASC"
                    ).fetchall()
                conn.close()
                return self._send_json(200, [{"id": r["id"], "name": r["name"], "team": r["team"], "is_leader": r["is_leader"]} for r in rows])

            if parts == ["api", "reports"]:
                query = parse_qs(parsed.query)
                include_deleted = query.get("include_deleted", ["0"])[0] == "1"
                conn = get_conn()
                if include_deleted:
                    rows = conn.execute(
                        """
                        SELECT id, created_at, team,
                               actor,
                               result_type, report_no, purchase_at,
                               store_name, store_address, receipt_file_name, comment,
                               COALESCE(remaining_stock,'') AS remaining_stock,
                               deleted_at
                        FROM reports
                        ORDER BY created_at DESC
                        """
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT id, created_at, team,
                               actor,
                               result_type, report_no, purchase_at,
                               store_name, store_address, receipt_file_name, comment,
                               COALESCE(remaining_stock,'') AS remaining_stock,
                               NULL as deleted_at
                        FROM reports
                        WHERE deleted_at IS NULL
                        ORDER BY created_at DESC
                        """
                    ).fetchall()
                conn.close()
                payload = []
                for r in rows:
                    payload.append(
                        {
                            "id": r["id"],
                            "createdAt": r["created_at"],
                            "team": r["team"],
                            "actor": r["actor"],
                            "resultType": r["result_type"],
                            "reportNo": r["report_no"],
                            "purchaseAt": r["purchase_at"],
                            "storeName": r["store_name"],
                            "storeAddress": r["store_address"],
                            "receiptFileName": r["receipt_file_name"],
                            "comment": r["comment"],
                            "remainingStock": r["remaining_stock"],
                            "deletedAt": r["deleted_at"],
                        }
                    )
                return self._send_json(200, payload)

            if parts == ["api", "deletions"]:
                query = parse_qs(parsed.query)
                try:
                    limit = int((query.get("limit", ["20"])[0] or "20").strip())
                except ValueError:
                    limit = 20
                limit = max(1, min(limit, 200))

                conn = get_conn()
                rows = conn.execute(
                    """
                    SELECT at, op_id, action, target_type, target_id, details_json
                    FROM audit_logs
                    WHERE action IN ('delete_reports', 'reset_reports')
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                conn.close()

                payload = []
                for r in rows:
                    details = {}
                    try:
                        details = json.loads(r["details_json"])
                    except Exception:
                        details = {"raw": r["details_json"]}
                    payload.append(
                        {
                            "at": r["at"],
                            "opId": r["op_id"],
                            "action": r["action"],
                            "targetType": r["target_type"],
                            "targetId": r["target_id"],
                            "details": details,
                        }
                    )
                return self._send_json(200, payload)

            if parts == ["api", "logs"]:
                query = parse_qs(parsed.query)
                try:
                    limit = int((query.get("limit", ["50"])[0] or "50").strip())
                except ValueError:
                    limit = 50
                limit = max(1, min(limit, 500))

                start = (query.get("start", [""])[0] or "").strip()
                end = (query.get("end", [""])[0] or "").strip()
                actor = (query.get("actor", [""])[0] or "").strip()
                action = (query.get("action", [""])[0] or "").strip()

                where_clauses = ["1=1"]
                params = []
                if start:
                    where_clauses.append("substr(at, 1, 10) >= ?")
                    params.append(start)
                if end:
                    where_clauses.append("substr(at, 1, 10) <= ?")
                    params.append(end)
                if actor:
                    where_clauses.append("actor = ?")
                    params.append(actor)
                if action:
                    where_clauses.append("action = ?")
                    params.append(action)

                where_sql = " AND ".join(where_clauses)
                params.append(limit)

                conn = get_conn()
                rows = conn.execute(
                    f"""
                    SELECT at, op_id, action, actor, target_type, target_id, details_json
                    FROM audit_logs
                    WHERE {where_sql}
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
                conn.close()

                payload = []
                for r in rows:
                    details = {}
                    try:
                        details = json.loads(r["details_json"])
                    except Exception:
                        details = {"raw": r["details_json"]}
                    payload.append(
                        {
                            "at": r["at"],
                            "opId": r["op_id"],
                            "action": r["action"],
                            "actor": r["actor"],
                            "targetType": r["target_type"],
                            "targetId": r["target_id"],
                            "details": details,
                        }
                    )
                return self._send_json(200, payload)

            if parts == ["api", "logs", "major"]:
                query = parse_qs(parsed.query)
                try:
                    limit = int((query.get("limit", ["50"])[0] or "50").strip())
                except ValueError:
                    limit = 50
                limit = max(1, min(limit, 500))

                placeholders = ",".join(["?"] * len(_MAJOR_ACTIONS))
                params = list(_MAJOR_ACTIONS) + [limit]

                conn = get_conn()
                rows = conn.execute(
                    f"""
                    SELECT at, op_id, action, actor, target_type, target_id, details_json
                    FROM audit_logs
                    WHERE action IN ({placeholders})
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
                conn.close()

                payload = []
                for r in rows:
                    details = {}
                    try:
                        details = json.loads(r["details_json"])
                    except Exception:
                        details = {"raw": r["details_json"]}
                    payload.append(
                        {
                            "at": r["at"],
                            "opId": r["op_id"],
                            "action": r["action"],
                            "actor": r["actor"],
                            "targetType": r["target_type"],
                            "targetId": r["target_id"],
                            "details": details,
                        }
                    )
                return self._send_json(200, payload)

            # GET /api/team-settings?team=...
            if parts == ["api", "team-settings"]:
                query = parse_qs(parsed.query)
                team = (query.get("team", [""])[0] or "").strip()
                if not team:
                    return self._send_json(400, {"error": "team required"})
                conn = get_conn()
                row = conn.execute(
                    "SELECT event_start_date FROM teams WHERE name = ?", (team,)
                ).fetchone()
                conn.close()
                if not row:
                    return self._send_json(404, {"error": "team not found"})
                return self._send_json(200, {"team": team, "eventStartDate": row["event_start_date"] or ""})

            # GET /api/assignment-notes?team=...&member=...&from=...&to=...
            if parts == ["api", "assignment-notes"]:
                query = parse_qs(parsed.query)
                team      = (query.get("team",   [""])[0] or "").strip()
                member    = (query.get("member", [""])[0] or "").strip()
                from_date = (query.get("from",   [""])[0] or "").strip()
                to_date   = (query.get("to",     [""])[0] or "").strip()
                if not team or not from_date or not to_date:
                    return self._send_json(400, {"error": "team, from, to required"})
                # メンバー指定なし → リーダー認証必要
                if not member and not self._is_leader_authorized():
                    return self._require_leader_auth()
                import re as _re
                for d in (from_date, to_date):
                    if not _re.match(r'^\d{4}-\d{2}-\d{2}$', d):
                        return self._send_json(400, {"error": "invalid date format"})
                conn = get_conn()
                if member:
                    rows = conn.execute(
                        "SELECT member_name, note_date, note_text FROM assignment_notes "
                        "WHERE team=? AND member_name=? AND note_date BETWEEN ? AND ? "
                        "AND note_text != '' ORDER BY note_date",
                        (team, member, from_date, to_date)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT member_name, note_date, note_text FROM assignment_notes "
                        "WHERE team=? AND note_date BETWEEN ? AND ? "
                        "AND note_text != '' ORDER BY note_date",
                        (team, from_date, to_date)
                    ).fetchall()
                conn.close()
                return self._send_json(200, [{"member": r["member_name"], "date": r["note_date"], "text": r["note_text"]} for r in rows])

            # GET /api/profile?team=...&member=...
            if parts == ["api", "profile"]:
                query = parse_qs(parsed.query)
                team   = (query.get("team",   [""])[0] or "").strip()
                member = (query.get("member", [""])[0] or "").strip()
                if not team or not member:
                    return self._send_json(400, {"error": "team and member are required"})
                # 本人またはリーダーのみ閲覧可能
                if (not self._is_leader_authorized()) and (self._actor() != member):
                    return self._send_json(403, {"error": "forbidden"})
                conn = get_conn()
                row = conn.execute(
                    "SELECT home_area, work_area, transport_modes FROM member_profiles WHERE team = ? AND member_name = ?",
                    (team, member),
                ).fetchone()
                conn.close()
                if row:
                    return self._send_json(200, {
                        "team": team, "member": member,
                        "homeArea": row["home_area"],
                        "workArea": row["work_area"],
                        "transportModes": row["transport_modes"],
                    })
                return self._send_json(200, {
                    "team": team, "member": member,
                    "homeArea": "", "workArea": "", "transportModes": "",
                })

            # GET /api/schedules?team=...&from=...&to=...
            if parts == ["api", "schedules"]:
                query = parse_qs(parsed.query)
                team      = (query.get("team", [""])[0] or "").strip()
                from_date = (query.get("from", [""])[0] or "").strip()
                to_date   = (query.get("to",   [""])[0] or "").strip()
                if not team or not from_date or not to_date:
                    return self._send_json(400, {"error": "team, from, to are required"})
                try:
                    datetime.fromisoformat(from_date).date()
                    datetime.fromisoformat(to_date).date()
                except ValueError:
                    return self._send_json(400, {"error": "invalid date format, expected YYYY-MM-DD"})
                conn = get_conn()
                rows = conn.execute(
                    """
                    SELECT member_name, schedule_date, availability, COALESCE(location_detail,'') AS location_detail
                    FROM member_schedules
                    WHERE team = ? AND schedule_date BETWEEN ? AND ?
                    ORDER BY member_name, schedule_date
                    """,
                    (team, from_date, to_date),
                ).fetchall()
                conn.close()
                return self._send_json(200, [
                    {"member": r["member_name"], "date": r["schedule_date"], "availability": r["availability"], "locationDetail": r["location_detail"]}
                    for r in rows
                ])

            # GET /api/assignments?team=...&from=...&to=...
            if parts == ["api", "assignments"]:
                query = parse_qs(parsed.query)
                team      = (query.get("team", [""])[0] or "").strip()
                from_date = (query.get("from", [""])[0] or "").strip()
                to_date   = (query.get("to",   [""])[0] or "").strip()
                if not team or not from_date or not to_date:
                    return self._send_json(400, {"error": "team, from, to are required"})
                try:
                    datetime.fromisoformat(from_date).date()
                    datetime.fromisoformat(to_date).date()
                except ValueError:
                    return self._send_json(400, {"error": "invalid date format, expected YYYY-MM-DD"})
                conn = get_conn()
                rows = conn.execute(
                    """
                    SELECT member_name, assign_date, COALESCE(purchase_count,1) AS purchase_count
                    FROM leader_assignments
                    WHERE team = ? AND assign_date BETWEEN ? AND ?
                    ORDER BY assign_date, member_name
                    """,
                    (team, from_date, to_date),
                ).fetchall()
                conn.close()
                return self._send_json(200, [
                    {"member": r["member_name"], "date": r["assign_date"], "purchaseCount": r["purchase_count"]}
                    for r in rows
                ])

            # GET /api/reported-dates?team=...&member=...&from=...&to=...
            # member を省略するとチーム全体の日別購入冊数を返す
            if parts == ["api", "reported-dates"]:
                query = parse_qs(parsed.query)
                team        = (query.get("team",   [""])[0] or "").strip()
                member      = (query.get("member", [""])[0] or "").strip()
                from_date   = (query.get("from",   [""])[0] or "").strip()
                to_date     = (query.get("to",     [""])[0] or "").strip()
                report_type = (query.get("type",   [""])[0] or "").strip()  # purchase | reservation | (empty=all)
                if not team or not from_date or not to_date:
                    return self._send_json(400, {"error": "team, from, to are required"})
                try:
                    datetime.fromisoformat(from_date).date()
                    datetime.fromisoformat(to_date).date()
                except ValueError:
                    return self._send_json(400, {"error": "invalid date format, expected YYYY-MM-DD"})
                _JST = "CASE WHEN purchase_at LIKE '%Z' THEN substr(datetime(replace(purchase_at,'Z',''),'+9 hours'),1,10) ELSE substr(purchase_at,1,10) END"
                conn = get_conn()
                if member:
                    # 既存挙動: 本人の購入済み日付一覧
                    rows = conn.execute(
                        f"""
                        SELECT DISTINCT {_JST} AS rdate
                        FROM reports
                        WHERE deleted_at IS NULL
                          AND team = ? AND actor = ?
                          AND {_JST} BETWEEN ? AND ?
                        ORDER BY rdate
                        """,
                        (team, member, from_date, to_date),
                    ).fetchall()
                    conn.close()
                    return self._send_json(200, [{"date": r["rdate"]} for r in rows])
                else:
                    # チーム全体の日別件数（typeフィルター対応）
                    if report_type == "purchase":
                        type_filter = "AND result_type LIKE '%\u8cfc\u5165%'"
                    elif report_type == "reservation":
                        type_filter = "AND result_type = '\u4e88\u7d04\u3067\u304d\u305f'"
                    else:
                        type_filter = ""
                    rows = conn.execute(
                        f"""
                        SELECT {_JST} AS rdate, COUNT(*) AS cnt
                        FROM reports
                        WHERE deleted_at IS NULL
                          AND team = ?
                          {type_filter}
                          AND {_JST} BETWEEN ? AND ?
                        GROUP BY rdate
                        ORDER BY rdate
                        """,
                        (team, from_date, to_date),
                    ).fetchall()
                    conn.close()
                    return self._send_json(200, [{"date": r["rdate"], "count": r["cnt"]} for r in rows])
                try:
                    datetime.fromisoformat(from_date).date()
                    datetime.fromisoformat(to_date).date()
                except ValueError:
                    return self._send_json(400, {"error": "invalid date format, expected YYYY-MM-DD"})
                _JST = "CASE WHEN purchase_at LIKE '%Z' THEN substr(datetime(replace(purchase_at,'Z',''),'+9 hours'),1,10) ELSE substr(purchase_at,1,10) END"
                conn = get_conn()
                rows = conn.execute(
                    f"""
                    SELECT DISTINCT {_JST} AS rdate
                    FROM reports
                    WHERE deleted_at IS NULL
                      AND team = ? AND actor = ?
                      AND {_JST} BETWEEN ? AND ?
                    ORDER BY rdate
                    """,
                    (team, member, from_date, to_date),
                ).fetchall()
                conn.close()
                return self._send_json(200, [{"date": r["rdate"]} for r in rows])

            return self._send_json(404, {"error": "not found"})

        # [UPLOADS] 安全な画像配信 (ディレクトリリスト禁止)
        if len(parts) == 2 and parts[0] == "uploads":
            filename = parts[1]
            _pat = re.compile(r"^[0-9a-f]{32}\.(jpg|png|gif|webp)$")
            if not _pat.match(filename):
                return self._send_json(400, {"error": "invalid filename"})
            filepath = os.path.join(UPLOAD_DIR, filename)
            if not os.path.isfile(filepath):
                return self._send_json(404, {"error": "not found"})
            _ct = {"jpg": "image/jpeg", "png": "image/png",
                   "gif": "image/gif", "webp": "image/webp"}
            ext = filename.rsplit(".", 1)[1]
            with open(filepath, "rb") as fp:
                data = fp.read()
            self.send_response(200)
            self.send_header("Content-Type", _ct.get(ext, "application/octet-stream"))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "max-age=86400, immutable")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)
            return

        if len(parts) >= 1 and parts[0] == "uploads":
            return self._send_json(403, {"error": "forbidden"})

        # .html ファイルはブラウザキャッシュを無効化して返す
        if len(parts) == 1 and parts[0].endswith(".html"):
            filepath = os.path.join(os.path.dirname(__file__), parts[0])
            if os.path.isfile(filepath):
                with open(filepath, "rb") as fp:
                    data = fp.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(data)
                return

        return super().do_GET()

    def do_POST(self):
        parts = self._path_parts()

        # ログイン（認証不要）
        if parts == ["api", "leader-login"]:
            try:
                self._cleanup_sessions()
                client_ip = self._client_ip()
                # [SEC] ブルートフォースロック確認
                if self._is_login_blocked(client_ip):
                    self._send_json(429, {"error": "too many failed attempts. try again later."})
                    return
                body = self._read_json()
                user = str(body.get("user", ""))
                pw   = str(body.get("pass", ""))
                ok = (hmac.compare_digest(user, self._leader_user()) and
                      hmac.compare_digest(pw, self._leader_pass()))
                if ok:
                    try:
                        conn = get_conn()
                        self._write_log(
                            conn,
                            action="leader_login_success",
                            target_type="auth",
                            target_id=user,
                            details={"user": user},
                        )
                        conn.commit()
                        conn.close()
                    except Exception:
                        pass
                    self._clear_login_fail(client_ip)
                    token = secrets.token_hex(32)
                    _SESSIONS[token] = time.time() + _SESSION_TTL
                    resp = json.dumps({"ok": True}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(resp)))
                    # [SEC] HTTPS時はSecureフラグを付与
                    secure = "; Secure" if self._is_https_request() else ""
                    self.send_header("Set-Cookie",
                        f"leader_session={token}; HttpOnly; SameSite=Lax; Path=/{secure}")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(resp)
                else:
                    self._record_login_fail(client_ip)
                    try:
                        conn = get_conn()
                        self._write_log(
                            conn,
                            action="leader_login_failed",
                            target_type="auth",
                            target_id=user or "unknown",
                            details={"user": user or "unknown"},
                        )
                        conn.commit()
                        conn.close()
                    except Exception:
                        pass
                    self._send_json(401, {"error": "invalid credentials"})
            except Exception:
                self._send_json(400, {"error": "bad request"})
            return

        if self._needs_leader_auth("POST", parts) and not self._is_leader_authorized():
            return self._require_leader_auth()

        if parts == ["api", "teams"]:
            try:
                body = self._read_json()
                name = str(body.get("name", "")).strip()
                if not name:
                    return self._send_json(400, {"error": "name required"})
                # [SEC] チーム名最大60文字
                if len(name) > 60:
                    return self._send_json(400, {"error": "name too long (max 60)"})

                conn = get_conn()
                conn.execute(
                    "INSERT INTO teams(name, created_at) VALUES(?, ?)",
                    (name, datetime.now(timezone.utc).isoformat()),
                )
                self._write_log(
                    conn,
                    action="create_team",
                    target_type="team",
                    target_id=name,
                    details={"name": name},
                )
                conn.commit()
                conn.close()
                return self._send_json(201, {"ok": True})
            except sqlite3.IntegrityError:
                return self._send_json(409, {"error": "team already exists"})
            except (ValueError, json.JSONDecodeError) as ex:
                return self._send_json(400, {"error": str(ex)})
            except Exception:
                return self._send_json(500, {"error": "internal server error"})

        if parts == ["api", "members", "reorder"]:
            try:
                body = self._read_json()
                team = str(body.get("team", "")).strip()
                ids  = body.get("ids", [])
                if not team or not isinstance(ids, list):
                    return self._send_json(400, {"error": "team and ids required"})
                conn = get_conn()
                for i, mid in enumerate(ids):
                    conn.execute(
                        "UPDATE members SET sort_order = ? WHERE id = ? AND team = ?",
                        (i + 1, int(mid), team),
                    )
                self._write_log(
                    conn,
                    action="reorder_members",
                    target_type="member",
                    target_id=team,
                    details={"team": team, "ids": ids},
                )
                conn.commit()
                conn.close()
                return self._send_json(200, {"ok": True})
            except (ValueError, json.JSONDecodeError) as ex:
                return self._send_json(400, {"error": str(ex)})
            except Exception:
                return self._send_json(500, {"error": "internal server error"})

        if parts == ["api", "members"]:
            try:
                body = self._read_json()
                name = str(body.get("name", "")).strip()
                team = str(body.get("team", "")).strip()
                if not name:
                    return self._send_json(400, {"error": "name required"})
                if not team:
                    return self._send_json(400, {"error": "team required"})
                if len(name) > 60:
                    return self._send_json(400, {"error": "name too long (max 60)"})
                conn = get_conn()
                team_exists = conn.execute("SELECT 1 FROM teams WHERE name = ?", (team,)).fetchone()
                if not team_exists:
                    conn.close()
                    return self._send_json(400, {"error": "unknown team"})
                max_order = conn.execute(
                    "SELECT COALESCE(MAX(sort_order), 0) FROM members WHERE team = ?",
                    (team,),
                ).fetchone()[0]
                conn.execute(
                    "INSERT INTO members(name, team, created_at, sort_order) VALUES(?, ?, ?, ?)",
                    (name, team, datetime.now(timezone.utc).isoformat(), max_order + 1),
                )
                self._write_log(
                    conn,
                    action="add_member",
                    target_type="member",
                    target_id=name,
                    details={"name": name, "team": team},
                )
                conn.commit()
                conn.close()
                return self._send_json(201, {"ok": True})
            except sqlite3.IntegrityError:
                return self._send_json(409, {"error": "member already exists in this team"})
            except (ValueError, json.JSONDecodeError) as ex:
                return self._send_json(400, {"error": str(ex)})
            except Exception:
                return self._send_json(500, {"error": "internal server error"})

        if parts == ["api", "reports"]:
            try:
                body = self._read_json()
                required = [
                    "id",
                    "createdAt",
                    "team",
                    "actor",
                    "resultType",
                    "reportNo",
                    "purchaseAt",
                    "storeName",
                    "storeAddress",
                    "receiptFileName",
                    "comment",
                    # remainingStock は任意なので required に含めない
                ]
                for key in required:
                    if key not in body:
                        return self._send_json(400, {"error": f"missing field: {key}"})

                # [SEC] フィールド長バリデーション
                _FIELD_LIMITS = {
                    "id": 128,
                    "createdAt": 40,
                    "team": 60,
                    "actor": 64,
                    "resultType": 80,
                    "reportNo": 20,
                    "purchaseAt": 40,
                    "storeName": 200,
                    "storeAddress": 400,
                    "receiptFileName": 256,
                    "comment": 1000,
                    "remainingStock": 100,
                }
                for field, max_len in _FIELD_LIMITS.items():
                    val = str(body.get(field, ""))
                    if len(val) > max_len:
                        return self._send_json(400, {"error": f"{field} too long (max {max_len})"})

                conn = get_conn()
                team_exists = conn.execute(
                    "SELECT 1 FROM teams WHERE name = ?", (body["team"],)
                ).fetchone()
                if not team_exists:
                    conn.close()
                    return self._send_json(400, {"error": "unknown team"})

                conn.execute(
                    """
                    INSERT INTO reports(
                        id, created_at, team, actor, result_type, report_no,
                        purchase_at, store_name, store_address, receipt_file_name, comment, remaining_stock
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(body["id"]),
                        str(body["createdAt"]),
                        str(body["team"]),
                        str(body["actor"]),
                        str(body["resultType"]),
                        str(body["reportNo"]),
                        str(body["purchaseAt"]),
                        str(body["storeName"]),
                        str(body["storeAddress"]),
                        str(body["receiptFileName"]),
                        str(body["comment"]),
                        str(body.get("remainingStock", "")),
                    ),
                )
                self._write_log(
                    conn,
                    action="create_report",
                    target_type="report",
                    target_id=str(body["id"]),
                    details={"team": str(body["team"]), "reportNo": str(body["reportNo"])},
                )
                conn.commit()
                conn.close()
                return self._send_json(201, {"ok": True})
            except sqlite3.IntegrityError:
                return self._send_json(409, {"error": "report id already exists"})
            except (ValueError, json.JSONDecodeError) as ex:
                return self._send_json(400, {"error": str(ex)})
            except Exception:
                return self._send_json(500, {"error": "internal server error"})

        if parts == ["api", "reports", "delete"]:
            try:
                body = self._read_json()
                ids = body.get("ids", [])
                if not isinstance(ids, list) or len(ids) == 0:
                    return self._send_json(400, {"error": "ids list is required"})
                # [SEC] 一度に削除できる件数を最大500件に制限
                if len(ids) > 500:
                    return self._send_json(400, {"error": "too many ids (max 500)"})

                conn = get_conn()
                result = self._soft_delete_reports(conn, ids, reason="bulk_delete")
                conn.commit()
                conn.close()
                return self._send_json(200, {"ok": True, **result})
            except (ValueError, json.JSONDecodeError) as ex:
                return self._send_json(400, {"error": str(ex)})
            except Exception:
                return self._send_json(500, {"error": "internal server error"})

        if parts == ["api", "deletions", "undo"]:
            try:
                body = self._read_json()
                op_id = str(body.get("opId", "")).strip()[:128]
                if not op_id:
                    return self._send_json(400, {"error": "opId is required"})

                conn = get_conn()
                result = self._undo_delete(conn, op_id)
                conn.commit()
                conn.close()
                return self._send_json(200, {"ok": True, "opId": op_id, **result})
            except (ValueError, json.JSONDecodeError) as ex:
                return self._send_json(400, {"error": str(ex)})
            except Exception:
                return self._send_json(500, {"error": "internal server error"})

        if parts == ["api", "uploads"]:
            try:
                try:
                    req_len = int(self.headers.get("Content-Length", "0"))
                except (ValueError, TypeError):
                    req_len = 0
                if req_len > _UPLOAD_MAX_REQUEST_BYTES:
                    return self._send_json(413, {"error": "request too large (max ~2MB after compression)"})
                raw = self.rfile.read(req_len) if req_len > 0 else b"{}"
                try:
                    body = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    return self._send_json(400, {"error": "invalid JSON"})

                orig_name = str(body.get("filename", "")).strip()
                data_b64  = str(body.get("dataBase64", ""))

                if not orig_name:
                    return self._send_json(400, {"error": "filename required"})
                ext_lower = os.path.splitext(orig_name)[1].lower()
                if ext_lower not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                    return self._send_json(400, {"error": "unsupported type. Allowed: jpg, png, gif, webp"})

                # Base64デコード
                try:
                    file_bytes = base64.b64decode(data_b64, validate=True)
                except Exception:
                    return self._send_json(400, {"error": "invalid base64 data"})

                if len(file_bytes) > _UPLOAD_MAX_FILE_BYTES:
                    return self._send_json(413, {"error": "file too large (max 2MB after compression)"})
                if len(file_bytes) < 8:
                    return self._send_json(400, {"error": "file too small"})

                # マジックバイト検証 (拡張子偽装防止)
                if file_bytes[:3] == b"\xff\xd8\xff":
                    safe_ext = ".jpg"
                elif file_bytes[:8] == b"\x89PNG\r\n\x1a\n":
                    safe_ext = ".png"
                elif file_bytes[:4] in (b"GIF8", b"GIF9"):
                    safe_ext = ".gif"
                elif file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP":
                    safe_ext = ".webp"
                else:
                    return self._send_json(400, {"error": "file content is not a recognized image"})

                # UUIDファイル名で保存
                stored_name = f"{uuid4().hex}{safe_ext}"
                stored_path = os.path.join(UPLOAD_DIR, stored_name)
                with open(stored_path, "wb") as fp:
                    fp.write(file_bytes)

                # 監査ログ
                conn = get_conn()
                self._write_log(
                    conn,
                    action="upload_file",
                    target_type="upload",
                    target_id=stored_name,
                    details={"originalName": orig_name, "size": len(file_bytes), "ext": safe_ext},
                )
                conn.commit()
                conn.close()
                return self._send_json(201, {"storedName": stored_name, "url": f"/uploads/{stored_name}"})
            except Exception:
                return self._send_json(500, {"error": "internal server error"})

        return self._send_json(404, {"error": "not found"})

    def do_PUT(self):
        parts = self._path_parts()

        if self._needs_leader_auth("PUT", parts) and not self._is_leader_authorized():
            return self._require_leader_auth()

        # PUT /api/team-settings  (リーダー認証済み)
        if parts == ["api", "team-settings"]:
            try:
                body = self._read_json()
                team = str(body.get("team", "")).strip()
                event_start_date = str(body.get("eventStartDate", "")).strip()
                if not team:
                    return self._send_json(400, {"error": "team required"})
                if len(team) > 60:
                    return self._send_json(400, {"error": "team name too long"})
                # 日付形式バリデーション (YYYY-MM-DD または空文字)
                import re as _re
                if event_start_date and not _re.match(r'^\d{4}-\d{2}-\d{2}$', event_start_date):
                    return self._send_json(400, {"error": "invalid date format"})
                conn = get_conn()
                conn.execute(
                    "UPDATE teams SET event_start_date = ? WHERE name = ?",
                    (event_start_date, team)
                )
                conn.commit()
                conn.close()
                return self._send_json(200, {"ok": True})
            except (ValueError, json.JSONDecodeError) as ex:
                return self._send_json(400, {"error": str(ex)})
            except Exception:
                return self._send_json(500, {"error": "internal server error"})

        # PUT /api/assignment-notes  (リーダー認証済み)
        if parts == ["api", "assignment-notes"]:
            try:
                body   = self._read_json()
                team   = str(body.get("team",   "")).strip()
                member = str(body.get("member", "")).strip()
                date   = str(body.get("date",   "")).strip()
                text   = str(body.get("text",   "")).strip()
                if not team or not member or not date:
                    return self._send_json(400, {"error": "team, member, date required"})
                if len(team) > 60 or len(member) > 60:
                    return self._send_json(400, {"error": "name too long (max 60)"})
                if len(text) > 2000:
                    return self._send_json(400, {"error": "text too long (max 2000)"})
                import re as _re
                if not _re.match(r'^\d{4}-\d{2}-\d{2}$', date):
                    return self._send_json(400, {"error": "invalid date format"})
                import datetime as _dt
                updated_at = _dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
                conn = get_conn()
                conn.execute("""
                    INSERT INTO assignment_notes (team, member_name, note_date, note_text, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(team, member_name, note_date)
                    DO UPDATE SET note_text=excluded.note_text, updated_at=excluded.updated_at
                """, (team, member, date, text, updated_at))
                conn.commit()
                conn.close()
                return self._send_json(200, {"ok": True})
            except (ValueError, json.JSONDecodeError) as ex:
                return self._send_json(400, {"error": str(ex)})
            except Exception:
                return self._send_json(500, {"error": "internal server error"})

        # PUT /api/profile  (認証不要 — 本人データ保存)
        if parts == ["api", "profile"]:
            try:
                body = self._read_json()
                team   = str(body.get("team",   "")).strip()
                member = str(body.get("member", "")).strip()
                home_area       = str(body.get("homeArea",       "")).strip()
                work_area       = str(body.get("workArea",       "")).strip()
                transport_modes = str(body.get("transportModes", "")).strip()
                if not team or not member:
                    return self._send_json(400, {"error": "team and member required"})
                if len(team) > 60 or len(member) > 60:
                    return self._send_json(400, {"error": "team/member name too long (max 60)"})
                if len(home_area) > 200 or len(work_area) > 200:
                    return self._send_json(400, {"error": "area too long (max 200)"})
                if len(transport_modes) > 50:
                    return self._send_json(400, {"error": "transport_modes too long"})
                # 本人またはリーダーのみ更新可能
                if (not self._is_leader_authorized()) and (self._actor() != member):
                    return self._send_json(403, {"error": "forbidden"})
                allowed = {"car", "train", "walk"}
                modes = [m for m in transport_modes.split(",") if m]
                if not all(m in allowed for m in modes):
                    return self._send_json(400, {"error": "invalid transport mode"})
                conn = get_conn()
                conn.execute(
                    """
                    INSERT INTO member_profiles(team, member_name, home_area, work_area, transport_modes, updated_at)
                    VALUES(?, ?, ?, ?, ?, ?)
                    ON CONFLICT(team, member_name) DO UPDATE SET
                        home_area       = excluded.home_area,
                        work_area       = excluded.work_area,
                        transport_modes = excluded.transport_modes,
                        updated_at      = excluded.updated_at
                    """,
                    (team, member, home_area, work_area, transport_modes, self._now_iso()),
                )
                conn.commit()
                conn.close()
                return self._send_json(200, {"ok": True})
            except (ValueError, json.JSONDecodeError) as ex:
                return self._send_json(400, {"error": str(ex)})
            except Exception:
                return self._send_json(500, {"error": "internal server error"})

        # PUT /api/schedules/bulk  (認証不要 — 本人スケジュール保存)
        if parts == ["api", "schedules", "bulk"]:
            try:
                body    = self._read_json()
                team    = str(body.get("team",   "")).strip()
                member  = str(body.get("member", "")).strip()
                entries = body.get("entries", [])
                if not team or not member:
                    return self._send_json(400, {"error": "team and member required"})
                if not isinstance(entries, list):
                    return self._send_json(400, {"error": "entries must be a list"})
                if len(entries) > 30:
                    return self._send_json(400, {"error": "too many entries (max 30)"})
                now = self._now_iso()
                conn = get_conn()
                for entry in entries:
                    date   = str(entry.get("date",           "")).strip()
                    avail  = str(entry.get("availability",   "")).strip()
                    detail = str(entry.get("locationDetail", "")).strip()
                    if not date or avail not in ("o", "d", "x"):
                        conn.close()
                        return self._send_json(400, {"error": "invalid entry"})
                    if len(detail) > 500:
                        conn.close()
                        return self._send_json(400, {"error": "locationDetail too long (max 500)"})
                    try:
                        datetime.fromisoformat(date).date()
                    except ValueError:
                        conn.close()
                        return self._send_json(400, {"error": f"invalid date: {date}"})
                    conn.execute(
                        """
                        INSERT INTO member_schedules(team, member_name, schedule_date, availability, location_detail, updated_at)
                        VALUES(?, ?, ?, ?, ?, ?)
                        ON CONFLICT(team, member_name, schedule_date) DO UPDATE SET
                            availability    = excluded.availability,
                            location_detail = excluded.location_detail,
                            updated_at      = excluded.updated_at
                        """,
                        (team, member, date, avail, detail, now),
                    )
                self._write_log(
                    conn,
                    action="update_schedule_bulk",
                    target_type="schedule",
                    target_id=f"{team}/{member}",
                    details={"team": team, "member": member, "count": len(entries)},
                )
                conn.commit()
                conn.close()
                return self._send_json(200, {"ok": True})
            except (ValueError, json.JSONDecodeError) as ex:
                return self._send_json(400, {"error": str(ex)})
            except Exception:
                return self._send_json(500, {"error": "internal server error"})

        # PUT /api/assignments/bulk  (リーダー認証済み)
        if parts == ["api", "assignments", "bulk"]:
            try:
                body        = self._read_json()
                team        = str(body.get("team", "")).strip()
                ops         = body.get("assignments", [])
                if not team:
                    return self._send_json(400, {"error": "team required"})
                if not isinstance(ops, list):
                    return self._send_json(400, {"error": "assignments must be a list"})
                if len(ops) > 200:
                    return self._send_json(400, {"error": "too many assignments (max 200)"})
                now = self._now_iso()
                actor = self._actor()
                conn = get_conn()
                for asgn in ops:
                    member = str(asgn.get("member", "")).strip()
                    date   = str(asgn.get("date",   "")).strip()
                    action = str(asgn.get("action", "add")).strip()  # "add" or "remove"
                    purchase_count = int(asgn.get("purchaseCount", 1))
                    if purchase_count not in (1, 2, 3):
                        purchase_count = 1
                    if not member or not date:
                        conn.close()
                        return self._send_json(400, {"error": "each assignment needs member and date"})
                    try:
                        datetime.fromisoformat(date).date()
                    except ValueError:
                        conn.close()
                        return self._send_json(400, {"error": f"invalid date: {date}"})
                    if action == "remove":
                        conn.execute(
                            "DELETE FROM leader_assignments WHERE team = ? AND member_name = ? AND assign_date = ?",
                            (team, member, date),
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO leader_assignments(team, member_name, assign_date, created_at, created_by, purchase_count)
                            VALUES(?, ?, ?, ?, ?, ?)
                            ON CONFLICT(team, member_name, assign_date) DO UPDATE SET purchase_count=excluded.purchase_count
                            """,
                            (team, member, date, now, actor, purchase_count),
                        )
                self._write_log(
                    conn,
                    action="update_assignments_bulk",
                    target_type="assignment",
                    target_id=team,
                    details={"team": team, "count": len(ops)},
                )
                conn.commit()
                conn.close()
                return self._send_json(200, {"ok": True})
            except (ValueError, json.JSONDecodeError) as ex:
                return self._send_json(400, {"error": str(ex)})
            except Exception:
                return self._send_json(500, {"error": "internal server error"})

        return self._send_json(404, {"error": "not found"})

    def do_DELETE(self):
        parts = self._path_parts()

        if self._needs_leader_auth("DELETE", parts) and not self._is_leader_authorized():
            return self._require_leader_auth()

        if parts == ["api", "reports"]:
            conn = get_conn()
            result = self._soft_delete_all_reports(conn, reason="reset_all")
            conn.commit()
            conn.close()
            return self._send_json(200, {"ok": True, **result})

        if len(parts) == 3 and parts[0] == "api" and parts[1] == "reports":
            report_id = unquote(parts[2])
            conn = get_conn()
            result = self._soft_delete_reports(conn, [report_id], reason="single_delete")
            conn.commit()
            conn.close()
            return self._send_json(200, {"ok": True, **result})

        if len(parts) == 3 and parts[0] == "api" and parts[1] == "teams":
            team_name = unquote(parts[2])
            conn = get_conn()
            rows = conn.execute("SELECT name FROM teams ORDER BY name ASC").fetchall()
            if len(rows) <= 1:
                conn.close()
                return self._send_json(400, {"error": "at least one team required"})

            exists = conn.execute("SELECT 1 FROM teams WHERE name = ?", (team_name,)).fetchone()
            if not exists:
                conn.close()
                return self._send_json(404, {"error": "team not found"})

            fallback_team = None
            for r in rows:
                if r["name"] != team_name:
                    fallback_team = r["name"]
                    break
            if not fallback_team:
                conn.close()
                return self._send_json(400, {"error": "fallback team not found"})

            conn.execute("DELETE FROM teams WHERE name = ?", (team_name,))
            conn.execute("UPDATE reports SET team = ? WHERE team = ?", (fallback_team, team_name))
            conn.execute("DELETE FROM members WHERE team = ?", (team_name,))
            conn.execute("DELETE FROM member_profiles WHERE team = ?", (team_name,))
            conn.execute("DELETE FROM member_schedules WHERE team = ?", (team_name,))
            conn.execute("DELETE FROM leader_assignments WHERE team = ?", (team_name,))
            self._write_log(
                conn,
                action="delete_team",
                target_type="team",
                target_id=team_name,
                details={"deleted": team_name, "fallback": fallback_team},
            )
            conn.commit()
            conn.close()
            return self._send_json(200, {"ok": True})

        if len(parts) == 3 and parts[0] == "api" and parts[1] == "members":
            try:
                member_id = int(parts[2])
            except ValueError:
                return self._send_json(400, {"error": "invalid id"})
            conn = get_conn()
            row = conn.execute("SELECT name, team FROM members WHERE id = ?", (member_id,)).fetchone()
            if not row:
                conn.close()
                return self._send_json(404, {"error": "member not found"})
            conn.execute("DELETE FROM members WHERE id = ?", (member_id,))
            conn.execute("DELETE FROM member_profiles WHERE team = ? AND member_name = ?", (row["team"], row["name"]))
            conn.execute("DELETE FROM member_schedules WHERE team = ? AND member_name = ?", (row["team"], row["name"]))
            conn.execute("DELETE FROM leader_assignments WHERE team = ? AND member_name = ?", (row["team"], row["name"]))
            self._write_log(
                conn,
                action="delete_member",
                target_type="member",
                target_id=str(member_id),
                details={"name": row["name"], "team": row["team"]},
            )
            conn.commit()
            conn.close()
            return self._send_json(200, {"ok": True})

        # DELETE /api/assignments?team=...&member=...&date=...  (リーダー認証済み)
        if parts == ["api", "assignments"]:
            try:
                q      = parse_qs(urlparse(self.path).query)
                team   = (q.get("team",   [""])[0] or "").strip()
                member = (q.get("member", [""])[0] or "").strip()
                date   = (q.get("date",   [""])[0] or "").strip()
                if not team or not member or not date:
                    return self._send_json(400, {"error": "team, member, date required"})
                conn = get_conn()
                conn.execute(
                    "DELETE FROM leader_assignments WHERE team = ? AND member_name = ? AND assign_date = ?",
                    (team, member, date),
                )
                self._write_log(
                    conn,
                    action="remove_assignment",
                    target_type="assignment",
                    target_id=f"{team}/{member}/{date}",
                    details={"team": team, "member": member, "date": date},
                )
                conn.commit()
                conn.close()
                return self._send_json(200, {"ok": True})
            except Exception:
                return self._send_json(500, {"error": "internal server error"})

        # DELETE /api/schedules?team=...&member=...&date=...  (リーダー認証済み — 予定1件クリア)
        if parts == ["api", "schedules"]:
            try:
                q      = parse_qs(urlparse(self.path).query)
                team   = (q.get("team",   [""])[0] or "").strip()
                member = (q.get("member", [""])[0] or "").strip()
                date   = (q.get("date",   [""])[0] or "").strip()
                if not team or not member or not date:
                    return self._send_json(400, {"error": "team, member, date required"})
                conn = get_conn()
                conn.execute(
                    "DELETE FROM member_schedules WHERE team = ? AND member_name = ? AND schedule_date = ?",
                    (team, member, date),
                )
                self._write_log(
                    conn,
                    action="clear_schedule",
                    target_type="schedule",
                    target_id=f"{team}/{member}/{date}",
                    details={"team": team, "member": member, "date": date},
                )
                conn.commit()
                conn.close()
                return self._send_json(200, {"ok": True})
            except Exception:
                return self._send_json(500, {"error": "internal server error"})

        return self._send_json(404, {"error": "not found"})

    def do_PATCH(self):
        parts = self._path_parts()
        if self._needs_leader_auth("PATCH", parts) and not self._is_leader_authorized():
            return self._require_leader_auth()

        if len(parts) == 3 and parts[0] == "api" and parts[1] == "teams":
            old_name = parts[2]
            try:
                body = self._read_json()
                new_name = str(body.get("name", "")).strip()
                if not new_name:
                    return self._send_json(400, {"error": "name required"})
                if new_name == old_name:
                    return self._send_json(200, {"ok": True})
                conn = get_conn()
                exists = conn.execute("SELECT 1 FROM teams WHERE name = ?", (old_name,)).fetchone()
                if not exists:
                    conn.close()
                    return self._send_json(404, {"error": "team not found"})
                conflict = conn.execute("SELECT 1 FROM teams WHERE name = ?", (new_name,)).fetchone()
                if conflict:
                    conn.close()
                    return self._send_json(400, {"error": "team name already exists"})
                conn.execute("UPDATE teams SET name = ? WHERE name = ?", (new_name, old_name))
                conn.execute("UPDATE members SET team = ? WHERE team = ?", (new_name, old_name))
                conn.execute("UPDATE reports SET team = ? WHERE team = ?", (new_name, old_name))
                conn.execute("UPDATE member_profiles SET team = ? WHERE team = ?", (new_name, old_name))
                conn.execute("UPDATE member_schedules SET team = ? WHERE team = ?", (new_name, old_name))
                conn.execute("UPDATE leader_assignments SET team = ? WHERE team = ?", (new_name, old_name))
                self._write_log(
                    conn,
                    action="rename_team",
                    target_type="team",
                    target_id=old_name,
                    details={"from": old_name, "to": new_name},
                )
                conn.commit()
                conn.close()
                return self._send_json(200, {"ok": True})
            except (ValueError, json.JSONDecodeError) as ex:
                return self._send_json(400, {"error": str(ex)})

        if len(parts) == 3 and parts[0] == "api" and parts[1] == "members":
            try:
                member_id = int(parts[2])
            except ValueError:
                return self._send_json(400, {"error": "invalid id"})
            try:
                body = self._read_json()
                # --- is_leader の更新 ---
                if "is_leader" in body:
                    val = 1 if body["is_leader"] else 0
                    conn = get_conn()
                    row = conn.execute("SELECT name, team FROM members WHERE id = ?", (member_id,)).fetchone()
                    if not row:
                        conn.close()
                        return self._send_json(404, {"error": "member not found"})
                    if val == 1:
                        # 同チームの既存リーダーを解除してから設定
                        conn.execute("UPDATE members SET is_leader = 0 WHERE team = ?", (row["team"],))
                    conn.execute("UPDATE members SET is_leader = ? WHERE id = ?", (val, member_id))
                    self._write_log(
                        conn,
                        action="set_leader",
                        target_type="member",
                        target_id=str(member_id),
                        details={"name": row["name"], "team": row["team"], "is_leader": val},
                    )
                    conn.commit()
                    conn.close()
                    return self._send_json(200, {"ok": True})
                # --- チーム移動 ---
                new_team = str(body.get("team", "")).strip()
                if not new_team:
                    return self._send_json(400, {"error": "team or is_leader required"})
                conn = get_conn()
                row = conn.execute("SELECT name, team FROM members WHERE id = ?", (member_id,)).fetchone()
                if not row:
                    conn.close()
                    return self._send_json(404, {"error": "member not found"})
                team_ok = conn.execute("SELECT 1 FROM teams WHERE name = ?", (new_team,)).fetchone()
                if not team_ok:
                    conn.close()
                    return self._send_json(400, {"error": "unknown team"})
                conn.execute("UPDATE members SET team = ? WHERE id = ?", (new_team, member_id))
                conn.execute("UPDATE member_profiles SET team = ? WHERE team = ? AND member_name = ?", (new_team, row["team"], row["name"]))
                conn.execute("UPDATE member_schedules SET team = ? WHERE team = ? AND member_name = ?", (new_team, row["team"], row["name"]))
                conn.execute("UPDATE leader_assignments SET team = ? WHERE team = ? AND member_name = ?", (new_team, row["team"], row["name"]))
                self._write_log(
                    conn,
                    action="move_member",
                    target_type="member",
                    target_id=str(member_id),
                    details={"name": row["name"], "from": row["team"], "to": new_team},
                )
                conn.commit()
                conn.close()
                return self._send_json(200, {"ok": True})
            except (ValueError, json.JSONDecodeError) as ex:
                return self._send_json(400, {"error": str(ex)})

        # PATCH /api/reports/{id}  (リーダー認証済み — 報告編集)
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "reports":
            report_id = unquote(parts[2])
            try:
                body = self._read_json()
                allowed = {"actor", "result_type", "report_no", "purchase_at",
                           "store_name", "store_address", "comment", "team", "created_at",
                           "remaining_stock"}
                updates = {k: str(v).strip() for k, v in body.items() if k in allowed}
                if not updates:
                    return self._send_json(400, {"error": "no valid fields"})
                conn = get_conn()
                row = conn.execute(
                    "SELECT id FROM reports WHERE id = ?", (report_id,)
                ).fetchone()
                if not row:
                    conn.close()
                    return self._send_json(404, {"error": "report not found"})
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                conn.execute(
                    f"UPDATE reports SET {set_clause} WHERE id = ?",
                    (*updates.values(), report_id),
                )
                self._write_log(
                    conn,
                    action="edit_report",
                    target_type="report",
                    target_id=report_id,
                    details=updates,
                )
                conn.commit()
                conn.close()
                return self._send_json(200, {"ok": True})
            except (ValueError, json.JSONDecodeError) as ex:
                return self._send_json(400, {"error": str(ex)})
            except Exception:
                return self._send_json(500, {"error": "internal server error"})

        return self._send_json(404, {"error": "not found"})


def run():
    init_db()
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.chdir(os.path.dirname(__file__))
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"Server started: http://127.0.0.1:{PORT}")
    print("Shared DB: shared_reports.db")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
