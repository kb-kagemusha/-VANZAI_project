"""DEC-072: reusable snapshots, safe defaults, non-destructive archive and access guards."""
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from alembic.migration import MigrationContext
from alembic.operations import Operations

from src.models.access_policy import RoleAccessPolicy
from src.models.order_request import OrderRequestDocument, OrderRequestTemplate, OrderRequestVersion
from src.models.transaction import AuditLog
from tests.test_api_order_requests import _auth, _body, _worker, ops_user, pdf_root  # noqa: F401
from tests.test_line_daily import _payload, _schedule


def _source(api_client, db_session, ops_user):
    worker = _worker(db_session, "元の送付先")
    body = _payload([worker.id], schedule=_schedule(1, 5, holidays=[2]), absences={worker.id: []})
    sections = json.loads(body["request_conditions"])
    sections.update(categories=["フェス系"], content="受付・案内", work_date_detail="今回だけの補足")
    body.update(request_conditions=json.dumps(sections), phone_first=True, phone_note="電話済み", allow_partial_accept=True)
    response = api_client.post("/api/order-requests", json=body, headers=_auth(ops_user.username))
    assert response.status_code == 200, response.text
    return response.json()


def _save(api_client, ops_user, version, name="月例イベント"):
    return api_client.post("/api/order-requests/templates", json={"name": name, "source_version_id": version["id"]}, headers=_auth(ops_user.username))


def test_template_is_independent_and_only_reusable_fields_are_preserved(api_client, db_session, ops_user, pdf_root):
    source = _source(api_client, db_session, ops_user)
    saved = _save(api_client, ops_user, source)
    assert saved.status_code == 200, saved.text
    tid = saved.json()["id"]
    assert db_session.query(OrderRequestVersion).count() == 1  # 保存だけでは新しい依頼を作らない
    detail = api_client.get(f"/api/order-requests/templates/{tid}", headers=_auth(ops_user.username)).json()
    payload = detail["payload"]
    sections = json.loads(payload["request_conditions"])
    assert sections["project_name"] == "駅前イベント" and sections["content"] == "受付・案内"
    assert sections["categories"] == ["フェス系"]
    assert sections["work_period"] == {"from": "", "to": "", "excluded_dates": []}
    assert sections["work_date_detail"] == ""
    group = sections["schedule"]["work_groups"][0]
    assert group["from"] == group["to"] == "" and group["excluded_dates"] == []
    assert group["start_time"] == "09:00" and group["end_time"] == "18:00"
    rate = sections["schedule"]["rate_groups"][0]
    assert rate["from"] == rate["to"] == "" and rate["amount"] == "15000"
    assert payload["worker_ids"] == [] and payload["recipient_absences"] == {}
    assert payload["work_date_label"] == "" and payload["follow_up_due_on"] is None
    assert payload["tracker_user_id"] is None and payload["phone_first"] is False and payload["phone_note"] == ""
    assert "id" not in payload and "based_on_version_id" not in payload and "deliveries" not in payload
    # 元を修正しても、一覧から外しても、保存した内容は変わらない。
    updated = api_client.patch(f"/api/order-requests/versions/{source['id']}", headers=_auth(ops_user.username), json={"site_name": "変更後の会場"})
    assert updated.status_code == 200
    document = db_session.get(OrderRequestDocument, source["document_id"])
    document.deleted_at = datetime.now(timezone.utc)
    db_session.commit()
    assert api_client.get(f"/api/order-requests/templates/{tid}", headers=_auth(ops_user.username)).json()["payload"] == payload
    new = api_client.post("/api/order-requests", json={**payload, "follow_up_due_on": source["follow_up_due_on"]}, headers=_auth(ops_user.username))
    assert new.status_code == 200, new.text
    assert new.json()["document_id"] != source["document_id"] and new.json()["revision_of_version_id"] is None
    assert new.json()["deliveries"] == [] and new.json()["draft_worker_ids"] == []
    assert db_session.query(AuditLog).filter_by(action="order_request_template_saved", target_id=tid).count() == 1


def test_names_are_unique_archive_keeps_snapshot_and_allows_name_reuse(api_client, db_session, ops_user, pdf_root):
    source = _source(api_client, db_session, ops_user)
    saved = _save(api_client, ops_user, source, " EventＡ ")
    assert saved.status_code == 200, saved.text
    tid = saved.json()["id"]
    assert _save(api_client, ops_user, source, "eventa").status_code == 409
    assert _save(api_client, ops_user, source, "   ").status_code == 400
    original = db_session.get(OrderRequestTemplate, tid).payload
    archived = api_client.post(f"/api/order-requests/templates/{tid}/archive", headers=_auth(ops_user.username))
    assert archived.status_code == 200
    assert api_client.get(f"/api/order-requests/templates/{tid}", headers=_auth(ops_user.username)).status_code == 404
    assert api_client.get("/api/order-requests/templates", headers=_auth(ops_user.username)).json()["total"] == 0
    assert _save(api_client, ops_user, source, "eventa").status_code == 200
    row = db_session.get(OrderRequestTemplate, tid)
    db_session.refresh(row)
    assert row.payload == original and row.archived_at is not None
    assert db_session.query(OrderRequestTemplate).count() == 2
    assert db_session.query(AuditLog).filter_by(action="order_request_template_archived", target_id=tid).count() == 1


def test_template_search_pagination_and_literal_wildcards(api_client, db_session, ops_user, pdf_root):
    source = _source(api_client, db_session, ops_user)
    for name in ["イベント100%", "イベント1000", "イベント_季節"]:
        assert _save(api_client, ops_user, source, name).status_code == 200
    auth = _auth(ops_user.username)
    assert api_client.get("/api/order-requests/templates?q=%25", headers=auth).json()["total"] == 1
    assert api_client.get("/api/order-requests/templates?q=_", headers=auth).json()["total"] == 1
    first = api_client.get("/api/order-requests/templates?limit=1&offset=0", headers=auth).json()
    second = api_client.get("/api/order-requests/templates?limit=1&offset=1", headers=auth).json()
    assert first["total"] == 3 and len(first["items"]) == 1 and first["items"][0]["id"] != second["items"][0]["id"]


def test_read_only_permission_cannot_save_or_archive_templates(api_client, db_session, ops_user, pdf_root):
    source = _source(api_client, db_session, ops_user)
    saved = _save(api_client, ops_user, source).json()
    db_session.add(RoleAccessPolicy(role="ops", display_name="閲覧のみ", permissions=["order_read"]))
    db_session.commit()
    auth = _auth(ops_user.username)
    assert api_client.get("/api/order-requests/templates", headers=auth).status_code == 200
    assert api_client.get(f"/api/order-requests/templates/{saved['id']}", headers=auth).status_code == 200
    assert _save(api_client, ops_user, source, "保存不可").status_code == 403
    assert api_client.post(f"/api/order-requests/templates/{saved['id']}/archive", headers=auth).status_code == 403
    assert api_client.get("/api/order-requests/templates").status_code == 401


def test_template_migration_creates_snapshot_table_and_partial_unique_index():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/20261023b001_order_request_templates.py"
    spec = importlib.util.spec_from_file_location("template_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        # 既存DBの親テーブルを最小限再現し、既存行が保持されることを確認。
        connection.execute(text("CREATE TABLE users (id VARCHAR(26) PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE order_request_versions (id VARCHAR(26) PRIMARY KEY)"))
        connection.execute(text("INSERT INTO order_request_versions VALUES ('existing-version')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        columns = {column["name"] for column in inspect(connection).get_columns("order_request_templates")}
        assert {"payload", "source_version_id", "archived_at", "archived_by_user_id", "name_key"} <= columns
        index = next(i for i in inspect(connection).get_indexes("order_request_templates") if i["name"] == "uq_order_request_templates_active_name")
        assert index["unique"] == 1 and "archived_at IS NULL" in str(index["dialect_options"]["sqlite_where"])
        assert connection.execute(text("SELECT id FROM order_request_versions")).scalar() == "existing-version"


def test_direct_template_creation_does_not_create_orders_and_clears_operational_data(api_client, db_session, ops_user, pdf_root):
    from src.models.order_request import OrderRequestDelivery
    worker = _worker(db_session, "テンプレートに含めない送付先")
    content = _payload([worker.id], schedule=_schedule(1, 5, holidays=[2]), absences={worker.id: []})
    conditions = json.loads(content["request_conditions"])
    conditions.update(incentive_enabled=True, incentive="販売1台につき500円")
    content.update(request_conditions=json.dumps(conditions), phone_first=True, phone_note="保存しない電話メモ")
    auth = _auth(ops_user.username)
    response = api_client.post("/api/order-requests/templates/create", headers=auth, json={"name": "直接作成の基本", "content": content})
    assert response.status_code == 200, response.text
    row = db_session.get(OrderRequestTemplate, response.json()["id"])
    assert row.source_version_id is None and row.source_document_number == ""
    assert db_session.query(OrderRequestVersion).count() == 0
    assert db_session.query(OrderRequestDocument).count() == 0
    assert db_session.query(OrderRequestDelivery).count() == 0
    payload = api_client.get(f"/api/order-requests/templates/{row.id}", headers=auth).json()["payload"]
    assert payload["worker_ids"] == [] and payload["recipient_absences"] == {}
    assert payload["follow_up_due_on"] is None and payload["phone_first"] is False and payload["phone_note"] == ""
    reusable = json.loads(payload["request_conditions"])
    assert reusable["schedule"]["work_groups"][0]["from"] == reusable["schedule"]["work_groups"][0]["to"] == ""
    assert reusable["schedule"]["work_groups"][0]["excluded_dates"] == []
    assert reusable["schedule"]["work_groups"][0]["start_time"] == "09:00"
    assert reusable["schedule"]["rate_groups"][0]["amount"] == "15000"
    assert reusable["incentive_enabled"] is True and reusable["incentive"] == "販売1台につき500円"
    assert api_client.post("/api/order-requests/templates/create", headers=auth, json={"name": "直接作成の基本", "content": {}}).status_code == 409
    audit = db_session.query(AuditLog).filter_by(action="order_request_template_saved", target_id=row.id).one()
    assert audit.after_value["direct_creation"] is True
    created = api_client.post("/api/order-requests", headers=auth, json={**payload, "follow_up_due_on": content["follow_up_due_on"]})
    assert created.status_code == 200, created.text
    assert created.json()["status"] == "draft"


def test_direct_template_permission_and_bad_source_are_rejected(api_client, db_session, ops_user):
    auth = _auth(ops_user.username)
    assert api_client.post("/api/order-requests/templates/create", headers=auth, json={"name": "未設定でも作成可", "content": {}}).status_code == 200
    assert api_client.post("/api/order-requests/templates/create", headers=auth, json={"name": "不正発注元", "content": {"internal_source": {"client_id": "unknown"}}}).status_code == 400
    assert api_client.post("/api/order-requests/templates/create", headers=auth, json={"name": "不正書式", "content": {"request_conditions": json.dumps({"format": "additional-request-v1", "incentive_enabled": "false"})}}).status_code == 400
    db_session.add(RoleAccessPolicy(role="ops", permissions=["order_read"]))
    db_session.commit()
    assert api_client.post("/api/order-requests/templates/create", headers=auth, json={"name": "閲覧だけ", "content": {}}).status_code == 403
    assert api_client.post("/api/order-requests/templates/create", json={"name": "未認証", "content": {}}).status_code == 401


def test_direct_template_migration_preserves_sources_and_refuses_lossy_downgrade():
    import pytest
    path = Path(__file__).resolve().parents[1] / "alembic/versions/20261023e001_direct_order_templates.py"
    spec = importlib.util.spec_from_file_location("direct_template_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE order_request_templates (id VARCHAR PRIMARY KEY, source_version_id VARCHAR(26) NOT NULL, payload TEXT)"))
        connection.execute(text("INSERT INTO order_request_templates VALUES ('old', 'source', 'unchanged')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert connection.execute(text("SELECT source_version_id, payload FROM order_request_templates WHERE id='old'")).one() == ("source", "unchanged")
        connection.execute(text("INSERT INTO order_request_templates VALUES ('new', NULL, 'direct')"))
        with Operations.context(MigrationContext.configure(connection)), pytest.raises(RuntimeError, match="直接作成"):
            migration.downgrade()
