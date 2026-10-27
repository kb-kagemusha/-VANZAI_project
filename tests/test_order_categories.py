"""カテゴリ（0.48.10）：保存はするが、本文・PDFには出さない。"""
import json

import pytest

from src.services.order_request_format import (
    CATEGORY_OPTIONS,
    DOCUMENT_TITLE,
    apply_template_fields,
    category_label,
    normalize_categories,
    parse_sections,
)
from src.services.order_request_pdf import _document_fields


def _conditions(categories):
    return json.dumps(
        {"format": "additional-request-v1", "project_name": "春施策", "background": "増員", "categories": categories},
        ensure_ascii=False,
    )


def test_title_is_case_request():
    assert DOCUMENT_TITLE == "【案件依頼】"


def test_training_can_be_combined_with_one_other():
    assert normalize_categories(["研修", "飲食店巡回"]) == ["飲食店巡回", "研修"]
    assert normalize_categories(["研修"]) == ["研修"]
    assert normalize_categories([]) == []
    assert normalize_categories(None) == []


@pytest.mark.parametrize(
    "value",
    [["飲食店巡回", "フェス系"], ["飲食店巡回", "フェス系", "研修"], ["その他"], "飲食店巡回", [1]],
)
def test_invalid_categories_are_rejected(value):
    with pytest.raises(ValueError):
        normalize_categories(value)


def test_categories_are_stored_but_not_in_body_or_pdf():
    conditions, body = apply_template_fields(
        _conditions(["研修", "調査系"]), "", work_date_label="2026-10-05", site_name="渋谷"
    )
    sections = parse_sections(conditions)
    assert sections["categories"] == ["調査系", "研修"]
    assert category_label(sections) == "調査系、研修"
    assert body.startswith("【案件依頼】")
    assert "調査系" not in body and "カテゴリ" not in body
    fields = _document_fields(
        request_conditions=conditions,
        body=body,
        work_date_label="2026-10-05",
        site_name="渋谷",
        site_address=None,
        contact_name="山田",
        contact_desk="",
        counterparty_note=None,
        worker_names=[],
    )
    captions = [caption for caption, _text in fields]
    assert captions[0] == "案件名"
    assert "カテゴリ" not in captions
    assert all("調査系" not in text for _caption, text in fields)


def test_old_title_is_still_stripped_in_pdf():
    body = "【追加案件依頼】\n■案件名\n旧案件\n■背景\n増員"
    fields = _document_fields(
        request_conditions='{"format":"additional-request-v1","project_name":"旧案件"}',
        body=body,
        work_date_label="",
        site_name="",
        site_address=None,
        contact_name="",
        contact_desk="",
        counterparty_note=None,
        worker_names=[],
    )
    assert fields[0] == ("案件名", "旧案件")


def test_old_documents_have_no_categories():
    sections = parse_sections('{"format":"additional-request-v1","project_name":"旧案件"}')
    assert "categories" not in sections
    assert category_label(sections) == ""
    assert len(CATEGORY_OPTIONS) == 7
