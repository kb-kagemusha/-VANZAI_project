"""発注依頼書の保存・確定・履歴。LINE送信は未接続。"""
from datetime import date, timedelta

import pytest

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import UserRole
from src.models.master import Worker
from src.models.order_request import OrderRequestDelivery, OrderRequestVersion
from src.services.document_storage import DocumentStorage


def _token(username: str) -> str:
    return create_access_token({"sub": username})


def _auth(username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(username)}"}


@pytest.fixture
def pdf_root(tmp_path, monkeypatch):
    monkeypatch.setenv("PDF_STORAGE_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def ops_user(db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="order_ops",
        email="order_ops@example.com",
        password="pass123",
        role=UserRole.OPS.value,
    )
    db_session.commit()
    return user


@pytest.fixture
def worker_user(db_session):
    worker = Worker(id=generate_ulid(), name="稼働者A", email="order_worker_a@example.com", is_active=True)
    db_session.add(worker)
    db_session.flush()
    user = create_user_with_hashed_password(
        db=db_session,
        username="order_worker",
        email="order_worker@example.com",
        password="pass123",
        role=UserRole.WORKER.value,
    )
    user.worker_id = worker.id
    db_session.commit()
    return user, worker


def _worker(db_session, name: str) -> Worker:
    worker = Worker(id=generate_ulid(), name=name, is_active=True)
    db_session.add(worker)
    db_session.commit()
    return worker


def _body(worker_ids: list[str], **overrides) -> dict:
    payload = {
        "kind": "formal",
        "work_date_label": "2026-10-05",
        "site_name": "渋谷現場",
        "request_conditions": "9時集合",
        "body": "通常稼働",
        "contact_name": "依頼担当",
        "contact_desk": "03-0000-0000",
        "worker_ids": worker_ids,
        "phone_first": False,
        "follow_up_due_on": "2026-10-20",
        "follow_up_due_time": "21:00",
    }
    payload.update(overrides)
    return payload


def test_confirm_creates_one_pdf_and_delivery_rows(api_client, db_session, ops_user, pdf_root, monkeypatch):
    monkeypatch.delenv("LINE_CHANNEL_ID", raising=False)
    monkeypatch.delenv("LINE_CHANNEL_SECRET", raising=False)
    monkeypatch.delenv("LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    first = _worker(db_session, "稼働者A")
    second = _worker(db_session, "稼働者B")
    created = api_client.post(
        "/api/order-requests",
        json=_body([first.id, second.id]),
        headers=_auth(ops_user.username),
    )
    assert created.status_code == 200, created.text
    version_id = created.json()["id"]

    confirmed = api_client.post(
        f"/api/order-requests/versions/{version_id}/confirm",
        headers=_auth(ops_user.username),
    )
    assert confirmed.status_code == 200, confirmed.text
    data = confirmed.json()
    assert data["status"] == "confirmed"
    assert data["has_pdf"] is True
    assert data["template_layout_applied"] is False
    assert data["line_send_available"] is False
    assert len(data["deliveries"]) == 2
    assert {row["send_status"] for row in data["deliveries"]} == {"unsent"}
    assert {row["ack_status"] for row in data["deliveries"]} == {"unacked"}
    assert "pdf_object_key" not in data

    pdf = api_client.get(
        f"/api/order-requests/versions/{version_id}/pdf",
        headers=_auth(ops_user.username),
    )
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert "attachment" in pdf.headers["content-disposition"]


def test_confirm_without_business_desk(api_client, db_session, ops_user, pdf_root, monkeypatch):
    monkeypatch.delenv("LINE_CHANNEL_ID", raising=False)
    monkeypatch.delenv("LINE_CHANNEL_SECRET", raising=False)
    monkeypatch.delenv("LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    worker = _worker(db_session, "稼働者A")
    created = api_client.post(
        "/api/order-requests",
        json=_body([worker.id], contact_desk=""),
        headers=_auth(ops_user.username),
    )
    assert created.status_code == 200, created.text
    confirmed = api_client.post(
        f"/api/order-requests/versions/{created.json()['id']}/confirm",
        headers=_auth(ops_user.username),
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["contact_name"] == "依頼担当"
    assert confirmed.json()["contact_desk"] == ""


def test_pdf_save_failure_rolls_back_confirmation(api_client, db_session, ops_user, pdf_root, monkeypatch):
    worker = _worker(db_session, "稼働者A")
    created = api_client.post(
        "/api/order-requests",
        json=_body([worker.id]),
        headers=_auth(ops_user.username),
    )
    version_id = created.json()["id"]

    def fail_save(self, object_key, content):
        raise OSError("disk full")

    monkeypatch.setattr(DocumentStorage, "save_bytes", fail_save)
    failed = api_client.post(
        f"/api/order-requests/versions/{version_id}/confirm",
        headers=_auth(ops_user.username),
    )
    assert failed.status_code == 500

    db_session.expire_all()
    version = db_session.get(OrderRequestVersion, version_id)
    assert version.status == "draft"
    assert version.pdf_object_key is None
    assert db_session.query(OrderRequestDelivery).count() == 0


def test_confirmed_snapshot_is_not_rewritten(api_client, db_session, ops_user, pdf_root):
    worker = _worker(db_session, "確定前の氏名")
    created = api_client.post(
        "/api/order-requests",
        json=_body([worker.id], work_date_label="10月5日"),
        headers=_auth(ops_user.username),
    )
    version_id = created.json()["id"]
    assert api_client.post(
        f"/api/order-requests/versions/{version_id}/confirm",
        headers=_auth(ops_user.username),
    ).status_code == 200

    worker.name = "改名後"
    db_session.commit()
    edited = api_client.patch(
        f"/api/order-requests/versions/{version_id}",
        json={"work_date_label": "変えてはいけない"},
        headers=_auth(ops_user.username),
    )
    assert edited.status_code == 409

    detail = api_client.get(
        f"/api/order-requests/versions/{version_id}",
        headers=_auth(ops_user.username),
    ).json()
    assert detail["work_date_label"] == "10月5日"
    assert detail["deliveries"][0]["worker_name_snapshot"] == "確定前の氏名"


def test_kind_cannot_change_after_confirm_and_revision_keeps_old_version(api_client, db_session, ops_user, pdf_root):
    worker = _worker(db_session, "稼働者A")
    created = api_client.post(
        "/api/order-requests",
        json=_body([worker.id], kind="test"),
        headers=_auth(ops_user.username),
    )
    version_id = created.json()["id"]
    api_client.post(
        f"/api/order-requests/versions/{version_id}/confirm",
        headers=_auth(ops_user.username),
    )
    changed = api_client.patch(
        f"/api/order-requests/versions/{version_id}",
        json={"kind": "formal"},
        headers=_auth(ops_user.username),
    )
    assert changed.status_code == 409

    revised = api_client.post(
        f"/api/order-requests/versions/{version_id}/revise",
        json={"reason": "条件変更"},
        headers=_auth(ops_user.username),
    )
    assert revised.status_code == 200, revised.text
    draft = revised.json()
    assert draft["status"] == "draft"
    assert draft["kind"] == "test"
    assert draft["version_no"] == 2
    assert draft["revision_of_version_id"] == version_id
    assert draft["deliveries"] == []

    original = api_client.get(
        f"/api/order-requests/versions/{version_id}",
        headers=_auth(ops_user.username),
    ).json()
    assert original["status"] == "confirmed"
    assert original["work_date_label"] == "2026-10-05"


def test_default_list_hides_test_documents(api_client, db_session, ops_user, pdf_root):
    worker = _worker(db_session, "稼働者A")
    api_client.post("/api/order-requests", json=_body([worker.id], kind="test"), headers=_auth(ops_user.username))
    formal = api_client.post(
        "/api/order-requests",
        json=_body(
            [worker.id],
            request_conditions='{"format":"additional-request-v1","project_name":"横浜おいも万博"}',
        ),
        headers=_auth(ops_user.username),
    )
    listed = api_client.get("/api/order-requests", headers=_auth(ops_user.username))
    assert listed.status_code == 200
    numbers = {item["document_number"] for item in listed.json()["items"]}
    assert formal.json()["document_number"] in numbers
    listed_formal = next(item for item in listed.json()["items"] if item["document_number"] == formal.json()["document_number"])
    assert listed_formal["project_name"] == "横浜おいも万博"
    assert all(item["kind"] == "formal" for item in listed.json()["items"])

    tests = api_client.get("/api/order-requests?kind=test", headers=_auth(ops_user.username))
    assert tests.json()["total"] == 1
    assert tests.json()["items"][0]["kind"] == "test"


def test_phone_first_does_not_mark_sent_and_overdue_stays_unsent(api_client, db_session, ops_user, pdf_root):
    worker = _worker(db_session, "稼働者A")
    created = api_client.post(
        "/api/order-requests",
        json=_body(
            [worker.id],
            phone_first=True,
            phone_note="先に電話した",
            follow_up_due_on=(date.today() - timedelta(days=2)).isoformat(),
            tracker_user_id=ops_user.id,
        ),
        headers=_auth(ops_user.username),
    )
    assert created.status_code == 200, created.text
    assert created.json()["phone_first"] is True
    assert created.json()["deliveries"] == []

    overdue = api_client.get("/api/order-requests?queue=overdue", headers=_auth(ops_user.username))
    assert overdue.json()["total"] == 1
    assert overdue.json()["items"][0]["phone_first"] is True
    assert overdue.json()["items"][0]["unsent_count"] == 0
    assert overdue.json()["items"][0]["status"] == "draft"


def test_cancel_stops_dispatch_without_clearing_delivery(api_client, db_session, ops_user, pdf_root):
    worker = _worker(db_session, "稼働者A")
    created = api_client.post("/api/order-requests", json=_body([worker.id]), headers=_auth(ops_user.username))
    version_id = created.json()["id"]
    api_client.post(f"/api/order-requests/versions/{version_id}/confirm", headers=_auth(ops_user.username))
    cancelled = api_client.post(
        f"/api/order-requests/versions/{version_id}/cancel",
        json={"reason": "中止"},
        headers=_auth(ops_user.username),
    )
    assert cancelled.status_code == 200, cancelled.text
    data = cancelled.json()
    assert data["status"] == "cancelled"
    assert data["dispatch_stopped"] is True
    assert data["deliveries"][0]["send_status"] == "unsent"
    assert data["deliveries"][0]["ack_status"] == "unacked"

    hidden = api_client.get("/api/order-requests?queue=unsent", headers=_auth(ops_user.username))
    assert all(item["version_id"] != version_id for item in hidden.json()["items"])


def test_worker_and_anonymous_cannot_read_pdf(api_client, db_session, ops_user, worker_user, pdf_root):
    _user, worker = worker_user
    created = api_client.post("/api/order-requests", json=_body([worker.id]), headers=_auth(ops_user.username))
    version_id = created.json()["id"]
    api_client.post(f"/api/order-requests/versions/{version_id}/confirm", headers=_auth(ops_user.username))

    denied = api_client.get(
        f"/api/order-requests/versions/{version_id}/pdf",
        headers=_auth("order_worker"),
    )
    assert denied.status_code == 403
    assert api_client.get(f"/api/order-requests/versions/{version_id}/pdf").status_code == 401
    assert api_client.get("/storage/pdfs/order-requests/secret.pdf").status_code == 404


def test_additional_request_format_replaces_condition_and_body_blob(api_client, db_session, ops_user, pdf_root):
    import json

    worker = _worker(db_session, "稼働者A")
    conditions = json.dumps(
        {
            "format": "additional-request-v1",
            "project_name": "春施策_渋谷",
            "background": "増員",
            "gather_time": "9:00",
            "work_time": "10:00-17:00",
            "dismiss_time": "17:30",
            "content": "受付",
            "belongings": "名札",
            "base_fee": "12000",
            "incentive": "達成時",
            "notes": "報酬の期限等その他の事項は、業務委託契約書記載のとおり。",
        },
        ensure_ascii=False,
    )
    created = api_client.post(
        "/api/order-requests",
        json=_body([worker.id], request_conditions=conditions, body="無視される本文"),
        headers=_auth(ops_user.username),
    )
    assert created.status_code == 200, created.text
    body = created.json()["body"]
    headings = [
        "【追加案件依頼】",
        "■案件名",
        "春施策_渋谷",
        "■背景",
        "増員",
        "■稼働場所",
        "渋谷現場",
        "■稼働日",
        "2026-10-05",
        "■稼働時間",
        "集合時間：9:00",
        "実施時間：10:00-17:00",
        "解散時間：17:30",
        "■内容：",
        "受付",
        "■持ち物：",
        "名札",
        "■単価：",
        "ベース：¥12000",
        "■インセンティブ：",
        "達成時",
        "■備考：",
        "・報酬の期限等その他の事項は、業務委託契約書記載のとおり。",
    ]
    cursor = -1
    for heading in headings:
        found = body.find(heading)
        assert found > cursor, heading
        cursor = found
    assert "無視される本文" not in body
    assert "依頼条件" not in body

    confirmed = api_client.post(
        f"/api/order-requests/versions/{created.json()['id']}/confirm",
        headers=_auth(ops_user.username),
    )
    assert confirmed.status_code == 200, confirmed.text


def test_multiline_hours_and_fee_are_kept_as_written(api_client, db_session, ops_user):
    import json

    worker = _worker(db_session, "稼働者A")
    hours = "\n".join(
        [
            "10/9(金)　※初日30分前集合",
            "　8:30　集合・準備",
            "　10:00~18:00　PR実施",
            "　19:00　片付け・解散",
            "",
            "10/10(土)〜10/13(火)",
            "　9:00　集合・準備",
        ]
    )
    fee = "\n".join(
        [
            "10/9(金)　初日30分前集合",
            "報酬：¥20,500(税抜)",
            "　(昼食代、交通費込み)",
            "",
            "※インセン無し",
        ]
    )
    site = "横浜赤レンガ倉庫 イベント広場\n（神奈川県横浜市中区新港1-1）\n※具体的な集合場所は追って。"
    work_dates = "10/8(木)　前日準備\n10/9(金)～10/13(火)　実施日"
    conditions = json.dumps(
        {
            "format": "additional-request-v1",
            "project_name": "【横浜おいも万博2026】\nhttps://example.com/event",
            "background": "-",
            "hours": hours,
            "content": "・商品販売促進",
            "belongings": "・ipad\n・プリンター",
            "fee": fee,
            "notes": "報酬の期限等その他の事項は、業務委託契約書記載のとおり。",
        },
        ensure_ascii=False,
    )
    created = api_client.post(
        "/api/order-requests",
        json=_body(
            [worker.id],
            work_date_label=work_dates,
            site_name=site,
            request_conditions=conditions,
            body="無視される本文",
        ),
        headers=_auth(ops_user.username),
    )
    assert created.status_code == 200, created.text
    data = created.json()
    expected_hours = hours.replace("~", "～")
    assert data["site_name"] == site
    assert data["work_date_label"] == work_dates
    stored = json.loads(data["request_conditions"])
    assert stored["hours"] == expected_hours
    assert stored["fee"] == fee
    body = data["body"]
    assert "集合時間：" not in body
    assert "ベース：" not in body
    assert "~" not in stored["hours"]
    for line in (expected_hours, fee, site, work_dates, "・商品販売促進", "・ipad"):
        assert line in body


def test_ascii_tilde_becomes_fullwidth_on_save(api_client, db_session, ops_user):
    worker = _worker(db_session, "稼働者A")
    created = api_client.post(
        "/api/order-requests",
        json=_body(
            [worker.id],
            work_date_label="10/9(金)~10/13(火)",
            site_name="会場A~会場B",
            contact_name="担当~次郎",
        ),
        headers=_auth(ops_user.username),
    )
    assert created.status_code == 200, created.text
    data = created.json()
    assert data["work_date_label"] == "10/9(金)～10/13(火)"
    assert data["site_name"] == "会場A～会場B"
    assert data["contact_name"] == "担当～次郎"
    assert "~" not in data["work_date_label"]


def test_legacy_free_text_stays_until_rewritten(api_client, db_session, ops_user):
    worker = _worker(db_session, "稼働者A")
    created = api_client.post(
        "/api/order-requests",
        json=_body([worker.id]),
        headers=_auth(ops_user.username),
    )
    assert created.status_code == 200, created.text
    assert created.json()["request_conditions"] == "9時集合"
    assert created.json()["body"] == "通常稼働"


def test_rejects_too_many_or_duplicate_recipients(api_client, db_session, ops_user):
    worker = _worker(db_session, "稼働者A")
    duplicated = api_client.post(
        "/api/order-requests",
        json=_body([worker.id, worker.id]),
        headers=_auth(ops_user.username),
    )
    assert duplicated.status_code == 400

    ids = [_worker(db_session, f"人{index}").id for index in range(31)]
    too_many = api_client.post(
        "/api/order-requests",
        json=_body(ids),
        headers=_auth(ops_user.username),
    )
    assert too_many.status_code == 400
    assert db_session.query(OrderRequestDelivery).count() == 0


def test_follow_up_due_date_is_required_and_defaults_to_21(api_client, db_session, ops_user):
    worker = _worker(db_session, "稼働者A")
    missing = api_client.post(
        "/api/order-requests",
        json=_body([worker.id], follow_up_due_on=None),
        headers=_auth(ops_user.username),
    )
    assert missing.status_code == 400, missing.text

    created = api_client.post(
        "/api/order-requests",
        json=_body([worker.id], follow_up_due_on="2026-10-08", follow_up_due_time="21:00"),
        headers=_auth(ops_user.username),
    )
    assert created.status_code == 200, created.text
    assert created.json()["follow_up_due_on"] == "2026-10-08"
    assert created.json()["follow_up_due_time"] == "21:00"


def test_line_push_text_includes_project_name():
    from src.services.line_order import _push_messages

    messages = _push_messages(
        document_number="OR-1",
        version_no=1,
        project_name="横浜おいも万博",
        work_date_label="10/9",
        site_name="赤レンガ倉庫",
        pdf_url="https://example.invalid/pdf",
        delivery_id="delivery-1",
        is_test=True,
    )
    text = messages[0]["text"]
    assert "発注依頼書 OR-1（版1）" in text
    assert "案件名: 横浜おいも万博" in text
    assert text.index("発注依頼書") < text.index("案件名:") < text.index("稼働日:")


def test_order_pdf_embeds_japanese_font():
    from src.services.order_request_pdf import PDF_LAYOUT_ID, _headed_fields, render_order_request_pdf
    from src.services.pdf_generator import DEFAULT_FONT

    body = "\n".join([
        "【追加案件依頼】",
        "■案件名",
        "有楽町交通会館",
        "■背景",
        "交通量の多い時間帯の案内",
        "■稼働場所",
        "有楽町",
        "■稼働日",
        "10/5～10/8",
        "■稼働時間",
        "集合時間：9:00\n実施時間：10:00～18:00",
        "■内容：",
        "受付と誘導",
        "■持ち物：",
        "動きやすい服装",
        "■単価：",
        "ベース：¥12000",
        "■インセンティブ：",
        "",
        "■備考：",
        "・報酬の期限等その他の事項は、業務委託契約書記載のとおり。",
    ])
    pdf = render_order_request_pdf(
        document_number="OR-1",
        version_no=1,
        kind="formal",
        work_date_label="10/5～10/8",
        site_name="有楽町",
        site_address=None,
        request_conditions='{"format":"additional-request-v1","project_name":"有楽町交通会館"}',
        body=body,
        contact_name="山田",
        contact_desk="",
        counterparty_note=None,
        worker_names=["山田"],
    )
    assert pdf.startswith(b"%PDF")
    assert DEFAULT_FONT == "IPAexGothic"
    assert b"IPAexGothic" in pdf
    assert PDF_LAYOUT_ID.encode("ascii") in pdf
    assert b"/Subtype /Image" in pdf or b"/Subtype/Image" in pdf
    assert len(pdf) > 20000
    fields = _headed_fields(body.split("【追加案件依頼】", 1)[1])
    assert [caption for caption, _text in fields] == [
        "案件名",
        "背景",
        "稼働場所",
        "稼働日",
        "稼働時間",
        "内容",
        "持ち物",
        "単価",
        "インセンティブ",
        "備考",
    ]
    assert fields[4][1].startswith("集合時間：9:00")


def test_order_pdf_created_on_uses_japan_date():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from src.services.order_request_pdf import format_created_on

    created = datetime(2026, 10, 6, 15, 30, tzinfo=ZoneInfo("UTC"))
    assert format_created_on(created) == "2026年10月7日"


def test_order_pdf_filename_is_date_plus_project():
    from src.services.order_request_pdf import attachment_content_disposition, order_request_pdf_filename

    name = order_request_pdf_filename(work_date_label="10/5～10/8", project_name="有楽町交通会館")
    assert name == "10／5～10／8＋有楽町交通会館.pdf"
    header = attachment_content_disposition(name)
    assert "filename*=UTF-8''" in header
    assert "10%EF%BC%8F5" in header
    blank = order_request_pdf_filename(work_date_label="", project_name="")
    assert blank == "発注依頼書.pdf"
