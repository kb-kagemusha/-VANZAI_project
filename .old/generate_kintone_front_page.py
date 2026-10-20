"""Kintoneフロントページ（ポータル）用のHTML/JS生成スクリプト。

Kintoneのポータル本文はHTML文字数に制限（例: 10,000文字）があるため、
本文HTMLは「root divのみ」にし、見た目・カード生成はJS/CSSに寄せる。

生成物:
- docs/kintone/front_page.html: ポータル本文に貼り付ける最小HTML
- kintone_app/customizations/front_portal.js: ポータル用カスタマイズJS（DOM生成）

Usage:
  C:/VANZAI_project/.venv/Scripts/python.exe scripts/generate_kintone_front_page.py
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


@dataclass(frozen=True)
class FrontLink:
    label: str
    description: str
    env_key: str
    category: str = "other"
    allow_add: bool = True
    add_label: str = "新規追加"


FEATURES: list[FrontLink] = [
    FrontLink("請求書", "請求書の発行/確認", "KINTONE_APP_INVOICES", category="billing"),
    FrontLink("支払明細", "稼働者への支払明細", "KINTONE_APP_PAYOUTS", category="billing"),
    FrontLink(
        "支払明細送信",
        "送信履歴/状況",
        "KINTONE_APP_PAYOUT_DELIVERIES",
        category="billing",
        allow_add=False,
    ),
    FrontLink(
        "銀行振込",
        "全銀フォーマット作成",
        "KINTONE_APP_BANK_TRANSFERS",
        category="billing",
        allow_add=False,
    ),
    FrontLink("稼働者マスタ", "稼働者の登録/更新", "KINTONE_APP_WORKERS", category="master"),
    FrontLink(
        "クライアント職員",
        "クライアント先の職員（責任者/担当者など）",
        "KINTONE_APP_STAFF_MANAGERS",
        category="master",
    ),
    FrontLink(
        "VANZAI職員",
        "自社職員の登録/更新",
        "KINTONE_APP_VANZAI_STAFF",
        category="internal",
        add_label="職員を登録",
    ),
    FrontLink("クライアント", "クライアント情報の管理", "KINTONE_APP_CLIENTS", category="master"),
    FrontLink("案件種別", "案件種別マスタ", "KINTONE_APP_PROJECT_TYPES", category="master"),
    FrontLink("下請け（紹介者）", "suppliersマスタ", "KINTONE_APP_SUPPLIERS", category="master"),
    FrontLink(
        "単価管理",
        "売上単価・外注単価・単価ルール",
        "KINTONE_APP_PRICE_RULES",
        category="master",
        allow_add=False,
    ),
    FrontLink("現場", "現場/サイト情報", "KINTONE_APP_SITES", category="field"),
    FrontLink("案件", "案件マスタ", "KINTONE_APP_PROJECTS", category="field"),
    FrontLink(
        "案件登録（カテゴリ分け）",
        "案件登録・担当/スタッフ登録の起点",
        "KINTONE_APP_PROJECT_ASSIGNMENTS",
        category="field",
    ),
    FrontLink("シフト管理", "シフト枠/アサイン", "KINTONE_APP_SHIFT_SLOTS", category="field"),
    FrontLink("実績管理", "CSV取り込み/実績確認", "KINTONE_APP_ACTUALS", category="field"),
    FrontLink(
        "登録ダッシュボード",
        "フロント（登録/確認）",
        "KINTONE_APP_FRONT_DASHBOARD",
        category="field",
        allow_add=False,
        add_label="",
    ),
    FrontLink("経費精算", "経費申請/承認", "KINTONE_APP_EXPENSES", category="other"),
    FrontLink("インセンティブ", "インセンティブ支給", "KINTONE_APP_INCENTIVES", category="other"),
    FrontLink("タスク進捗", "案件タスクとアラート", "KINTONE_APP_TASKS", category="other"),
    FrontLink("案件資料", "案件説明資料", "KINTONE_APP_PROJECT_DOCUMENTS", category="other"),
    FrontLink("貸出備品", "備品マスタ/貸出", "KINTONE_APP_EQUIPMENT", category="other"),
    FrontLink("貸出備品（貸出）", "備品貸出履歴", "KINTONE_APP_EQUIPMENT_LOANS", category="other"),
]


def _build_url(subdomain: str, guest_space_id: str | None, app_id: str | None) -> str:
    if not subdomain or not app_id:
        return "#"
    if guest_space_id:
        return f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/{app_id}/"
    return f"https://{subdomain}.cybozu.com/k/{app_id}/"


def _build_add_url(subdomain: str, guest_space_id: str | None, app_id: str | None) -> str:
    if not subdomain or not app_id:
        return "#"
    if guest_space_id:
        return f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/{app_id}/edit"
    return f"https://{subdomain}.cybozu.com/k/{app_id}/edit"


def _build_space_url(subdomain: str, guest_space_id: str | None) -> str:
    if not subdomain:
        return "#"
    if guest_space_id:
        return f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/"
    return f"https://{subdomain}.cybozu.com/k/"


def _build_cards(subdomain: str, guest_space_id: str | None) -> list[dict]:
    cards: list[dict] = []
    for link in FEATURES:
        app_id = os.getenv(link.env_key, "").strip() or None
        enabled = bool(subdomain and app_id)
        href = _build_url(subdomain, guest_space_id, app_id)
        add_href = (
            _build_add_url(subdomain, guest_space_id, app_id)
            if (enabled and link.allow_add)
            else ""
        )
        cards.append(
            {
                **asdict(link),
                "app_id": app_id or "",
                "enabled": enabled,
                "href": href,
                "add_href": add_href,
            }
        )
    return cards


def _render_min_html() -> str:
    # ポータル本文に貼り付けるのはこれだけ（HTML文字数対策）
    return "<div id=\"vanzai-front-root\"></div>"


def _render_portal_js(cards: list[dict]) -> str:
    payload = {
        "cards": cards,
    }
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    # JS側でDOM生成。CSSは front_portal.css に寄せる。
    return (
        "(function(){\n"
        "  'use strict';\n"
        f"  var CONFIG={payload_json};\n"
        "\n"
        "  function el(tag, attrs, children){\n"
        "    var node=document.createElement(tag);\n"
        "    if(attrs){\n"
        "      Object.keys(attrs).forEach(function(k){\n"
        "        if(k==='class') node.className=attrs[k];\n"
        "        else if(k==='text') node.textContent=attrs[k];\n"
        "        else if(k==='html') node.innerHTML=attrs[k];\n"
        "        else node.setAttribute(k, attrs[k]);\n"
        "      });\n"
        "    }\n"
        "    if(children){\n"
        "      children.forEach(function(c){\n"
        "        if(c==null) return;\n"
        "        node.appendChild(typeof c==='string'?document.createTextNode(c):c);\n"
        "      });\n"
        "    }\n"
        "    return node;\n"
        "  }\n"
        "\n"
        "  function buildCard(card){\n"
        "    var cardClass='vf-card vf-cat-'+card.category + (card.enabled?'':' vf-disabled');\n"
        "    var title=el('div',{class:'vf-card-title',text:card.label});\n"
        "    var desc=el('div',{class:'vf-card-desc',text:card.description});\n"
        "\n"
        "    var actions=el('div',{class:'vf-card-actions'});\n"
        "    var listBtn=el('a',{class:'vf-btn',href:card.enabled?card.href:'#',text:'一覧を開く'});\n"
        "    if(!card.enabled){ listBtn.setAttribute('aria-disabled','true'); }\n"
        "    actions.appendChild(listBtn);\n"
        "\n"
        "    if(card.add_href){\n"
        "      actions.appendChild(el('a',{class:'vf-btn vf-secondary',href:card.add_href,text:card.add_label||'新規追加'}));\n"
        "    }else if(card.allow_add){\n"
        "      actions.appendChild(el('a',{class:'vf-btn vf-secondary vf-disabled',href:'#',text:'未設定'}));\n"
        "    }\n"
        "\n"
        "    var badge=el('div',{class:'vf-card-badge',text:card.enabled?'Open':'未設定'});\n"
        "    return el('div',{class:cardClass},[title,desc,actions,badge]);\n"
        "  }\n"
        "\n"
        "  function init(){\n"
        "    var root=document.getElementById('vanzai-front-root');\n"
        "    if(!root) return;\n"
        "    if(root.dataset.vanzaiFrontInitialized==='1') return;\n"
        "    root.dataset.vanzaiFrontInitialized='1';\n"
        "\n"
        "    var container=el('div',{class:'vanzai-front'});\n"
        "    var header=el('div',{class:'vf-header'});\n"
        "    header.appendChild(el('h1',{class:'vf-h1',html:'VANZAI Portal Page <span style=\"font-size:14px;font-weight:500;color:#bfdbfe;\">- 仮運用開始日：2026年2月～</span>'}));\n"
        "\n"
        "    var main=el('div',{class:'vf-main'});\n"
        "    var grid=el('div',{class:'vf-grid'});\n"
        "    (CONFIG.cards||[]).forEach(function(c){ grid.appendChild(buildCard(c)); });\n"
        "\n"
        "    main.appendChild(grid);\n"
        "\n"
        "    container.appendChild(header);\n"
        "    container.appendChild(main);\n"
        "    root.appendChild(container);\n"
        "  }\n"
        "\n"
        "  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', init);\n"
        "  else init();\n"
        "  try{ if(window.kintone && kintone.events && kintone.events.on) kintone.events.on('portal.show', init); }catch(e){}\n"
        "})();\n"
    )


def main() -> None:
    subdomain = os.getenv("KINTONE_SUBDOMAIN", "").strip()
    guest_space_id = os.getenv("KINTONE_GUEST_SPACE_ID", "").strip() or None

    # 1) ポータル本文（HTML）は最小化
    html_path = Path("docs/kintone/front_page.html")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(_render_min_html(), encoding="utf-8")

    # 2) ポータル用JSを.envから生成
    cards = _build_cards(subdomain, guest_space_id)
    js_path = Path("kintone_app/customizations/front_portal.js")
    js_path.parent.mkdir(parents=True, exist_ok=True)
    js_path.write_text(_render_portal_js(cards), encoding="utf-8")

    print(f"Generated: {html_path}")
    print(f"Generated: {js_path}")


if __name__ == "__main__":
    main()
