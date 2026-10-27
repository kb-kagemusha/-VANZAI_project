"""Individual menu lifecycle. Normal richmenuswitch actions stay inside LINE."""
from datetime import timedelta, timezone
import hashlib
import json
import urllib.error
import urllib.request
from sqlalchemy import text
from src.models.line_operator import LineOperatorMenuRelease, LineOperatorMenuState
from src.models.line_order import LineWorkerLink
from src.models.master import Worker
from src.models.operator_staff import LineStaffLink
from src.services.line_operator import identity, OperatorError
from src.services.line_messaging import line_settings
from src.services import worker_schedule as ws
from src.services.audit import AuditService

API = "https://api.line.me/v2/bot"


class MenuError(Exception):
    def __init__(self, status=0):
        self.status = status


class MenuClient:
    def content(self, menu_id):
        request = urllib.request.Request(f"https://api-data.line.me/v2/bot/richmenu/{menu_id}/content", headers={"Authorization": "Bearer " + line_settings().access_token})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.read(1024 * 1024 + 1)
        except (urllib.error.URLError, TimeoutError):
            raise MenuError() from None

    def call(self, method, path, payload=None, image=None):
        token = line_settings().access_token
        if not token:
            raise MenuError()
        data = image if image is not None else json.dumps(payload).encode() if payload is not None else None
        host = "https://api-data.line.me/v2/bot" if image is not None else API
        request = urllib.request.Request(host + path, data=data, method=method, headers={"Authorization": "Bearer " + token, "Content-Type": "image/png" if image is not None else "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode() or "{}")
        except urllib.error.HTTPError as exc:
            raise MenuError(exc.code) from None
        except (urllib.error.URLError, TimeoutError, ValueError):
            raise MenuError() from None

    def current(self, subject):
        try:
            return self.call("GET", f"/user/{subject}/richmenu").get("richMenuId")
        except MenuError as exc:
            if exc.status == 404:
                return None
            raise


def current_release(db):
    return db.query(LineOperatorMenuRelease).filter_by(active=True).order_by(LineOperatorMenuRelease.created_at.desc(), LineOperatorMenuRelease.id.desc()).first()


def dual_worker(db, subject):
    link = db.query(LineWorkerLink).filter_by(line_user_id=subject, status="active").one_or_none()
    worker = db.get(Worker, link.worker_id) if link else None
    return bool(worker and worker.is_active and worker.deleted_at is None)


def reconcile(db, subject, client=None, force=False, requested_view=None):
    """Caller commits each person independently. Re-read eligibility under a per-user lock."""
    release = current_release(db)
    if not release and db.query(LineOperatorMenuRelease.id).first() is None:
        return "not_published"
    if db.bind.dialect.name == "postgresql":
        key = int.from_bytes(hashlib.sha256(("operator-menu:" + subject).encode()).digest()[:8], "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
    db.expire_all()
    state = db.get(LineOperatorMenuState, subject)
    now = ws.now_utc()
    if not force and state and state.status == "failed" and state.next_attempt_at:
        retry_at = state.next_attempt_at.replace(tzinfo=timezone.utc) if not state.next_attempt_at.tzinfo else state.next_attempt_at
        if retry_at > now:
            return "waiting"
    try:
        if not release:
            raise OperatorError(403, "Menu release disabled")
        _link, staff, _user = identity(db, subject)
        dual = dual_worker(db, subject)
        desired = release.menus["operator_dual" if dual else "operator_only"]
        allowed = {release.menus["operator_dual"], release.menus["worker_dual"]} if dual else {desired}
        # A fresh switch webhook is the user's intent, even if LINE's GET still
        # returns the previous menu or its alias switch failed. Recheck both roles.
        requested = release.menus.get({"worker": "worker_dual", "operator": "operator_dual"}.get(requested_view, "")) if dual else None
    except OperatorError:
        staff, desired, allowed, requested = None, None, set(), None
        # No eligible/past individual operator menu means no mutation is necessary.
        if state is None:
            return "not_eligible"
    if state is None:
        state = LineOperatorMenuState(line_user_id=subject, status="pending", attempts=0, updated_at=now)
        db.add(state)
        db.flush()
    client = client or MenuClient()
    try:
        actual = client.current(subject)
        # Respect a valid dual-role person's selection on LINE. Never replay an old webhook.
        target = requested or (actual if actual in allowed else desired)
        if target != actual:
            if target:
                client.call("POST", f"/user/{subject}/richmenu/{target}")
            else:
                owned = {mid for release_row in db.query(LineOperatorMenuRelease).all() for mid in release_row.menus.values()}
                if actual in owned:
                    client.call("DELETE", f"/user/{subject}/richmenu")
                else:
                    target = actual  # Do not remove an unrelated personal menu.
        changed = state.status != "applied" or state.applied_menu_id != target
        state.applied_menu_id, state.status, state.attempts, state.next_attempt_at = target, "applied", 0, None
        if changed:
            AuditService(db).log("operator_menu_applied", target_type="vanzai_staff" if staff else "line_menu", target_id=staff.id if staff else None, actor="operator-menu-sync", after_value={"operator_enabled": bool(desired)})
    except MenuError:
        state.status, state.attempts = "failed", state.attempts + 1
        state.next_attempt_at = now + timedelta(minutes=min(60, 2 ** min(state.attempts, 6)))
        AuditService(db).log("operator_menu_failed", target_type="vanzai_staff" if staff else "line_menu", target_id=staff.id if staff else None, actor="operator-menu-sync", after_value={"attempts": state.attempts})
    state.updated_at = now
    db.flush()
    return state.status


def reconcile_all(db, client=None):
    if db.query(LineOperatorMenuRelease.id).first() is None:
        return {"not_published": 1}
    subjects = {row[0] for row in db.query(LineStaffLink.line_user_id).filter_by(status="active").all()} | {row[0] for row in db.query(LineOperatorMenuState.line_user_id).all()}
    counts = {}
    for subject in sorted(subjects):
        try:
            result = reconcile(db, subject, client)
            db.commit()
        except Exception:
            db.rollback()
            result = "error"
        counts[result] = counts.get(result, 0) + 1
    return counts
