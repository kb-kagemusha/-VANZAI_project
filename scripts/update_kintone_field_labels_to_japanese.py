"""
Kintoneアプリのフィールド名（ラベル）を日本語に一括変更

フィールドコードはそのまま維持し、表示名（ラベル）のみ日本語化します。

使用方法:
    python scripts/update_kintone_field_labels_to_japanese.py [アプリID]
    
    例: python scripts/update_kintone_field_labels_to_japanese.py 165
    またはすべてのアプリ: python scripts/update_kintone_field_labels_to_japanese.py all
    
環境変数:
    KINTONE_ADMIN_USER: 管理者ログイン名（必須）
    KINTONE_ADMIN_PASSWORD: 管理者パスワード（必須）
    
注意:
    - 管理者認証を使用します（APIトークンより強い権限）
    - システムフィールド（レコード番号、作成者など）は変更できません
    - 実行前にバックアップを取ることを推奨します
"""
import os
import sys
from pathlib import Path
import json
import requests
import base64

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv(override=True)

# フィールドコード → 日本語ラベルのマッピング
FIELD_LABELS_JA = {
    # 共通フィールド
    "id": "ID",
    "created_at": "作成日時",
    "updated_at": "更新日時",
    "is_active": "有効",
    "notes": "備考",
    
    # Workers
    "worker_id": "稼働者ID",
    "last_name": "氏名(姓)",
    "first_name": "氏名(名)",
    "lastname_furigana": "姓(フリガナ)",
    "firstname_furigana": "名(フリガナ)",
    "via_destination": "経由先",
    "introducer_supplier": "紹介者/下請け",
    "sex": "性別",
    "bussiness_name": "個人事業主屋号",
    "zipcode": "郵便番号",
    "pref": "都道府県",
    "city_etc": "市区町村以下",
    "name_of_building": "建物名・部屋番号",
    "emergency_contact_name": "緊急連絡先氏名(カナ)",
    "emergency_contact_phone": "緊急連絡先",
    "id_document": "身分証提出",
    "invoice_registration_status": "適格請求書発行事業者の登録番号_取得有無",
    "invoice_registration_number": "適格請求書発行事業者の登録番号",
    "address_line1": "住所（都道府県～市区町村）",
    "address_line2": "住所（建物名・部屋番号）",
    "phone": "電話番号",
    "email": "メールアドレス",
    "hire_date": "入社日",
    "termination_date": "退職日",
    "bank_name": "銀行名",
    "bank_branch": "支店名",
    "bank_account_type": "口座種別",
    "bank_account_number": "口座番号",
    "bank_account_holder": "口座名義",
    "introducer_name": "紹介者名",
    "introducer_supplier_id": "紹介者（下請けID）",
    
    # Clients
    "client_id": "クライアントID",
    "code": "コード",
    "client_name": "クライアント名",
    "contact_person": "担当者名",
    "contact_phone": "連絡先電話",
    "contact_email": "連絡先メール",
    "billing_address": "請求先住所",
    "payment_terms": "支払条件",
    "payment_method": "支払方法",
    
    # Sites
    "site_id": "現場ID",
    "site_name": "現場名",
    "site_address": "現場住所",
    "site_contact": "現場連絡先",
    "site_type": "現場種別",
    
    # Roles
    "role_id": "役割ID",
    "role_name": "役割名",
    "description": "説明",
    "requires_license": "資格必須",
    
    # Project Types
    "project_type_id": "案件種別ID",
    "type_name": "種別名",
    "default_unit": "デフォルト単位",
    "allow_overtime": "残業可",
    
    # Projects
    "project_id": "案件ID",
    "assignment_id": "案件ID",
    "project_name": "案件名",
    "assignment_title": "案件タイトル",
    "facility_name": "施設名",
    "event_name": "イベント名",
    "gathering_time": "集合時間",
    "dismissal_time": "解散時間",
    "working_hours": "1日稼働時間(h)",
    "billing_rate_daily": "ベース報酬",
    "billing_rate_monthly": "必要人数",
    "headcount_director": "ディレクター人数",
    "headcount_staff": "スタッフ人数",
    "owner_name": "クライアント責任者",
    "main_staff": "クライアント担当者",
    "start_date": "開始日",
    "end_date": "終了日",
    "budget": "予算",
    "actual_cost": "実績コスト",
    "project_manager": "案件責任者",
    
    # Shift Slots
    "shift_id": "シフトID",
    "shift_date": "シフト日",
    "shift_start_time": "開始時刻",
    "shift_end_time": "終了時刻",
    "required_count": "必要人数",
    "confirmed_count": "確定人数",
    "work_date": "稼働日",
    "start_time": "開始時刻",
    "end_time": "終了時刻",
    
    # Assignments
    "assignment_id": "アサインID",
    "assignment_date": "アサイン日",
    "assignment_status": "アサインステータス",
    "cancel_reason": "キャンセル理由",
    "confirmed_at": "確定日時",
    "status": "ステータス",
    
    # Actuals
    "actual_id": "実績ID",
    "worked_start_time": "出勤時間",
    "worked_end_time": "退勤時間",
    "sales_count": "販売数",
    "memo": "備考",
    "break_minutes": "休憩時間（分）",
    "actual_hours": "実績時間",
    "overtime_hours": "残業時間",
    "late_night_hours": "深夜時間",
    "import_batch_id": "取込バッチID",
    "error_reason": "エラー理由",
    
    # Expenses
    "expense_id": "経費ID",
    "expense_date": "経費日",
    "category": "カテゴリ",
    "amount": "金額",
    "receipt_number": "領収書番号",
    "approval_status": "承認ステータス",
    "approved_by": "承認者",
    "approved_at": "承認日時",
    "invoice_id": "請求書ID",
    "billing_date": "請求日",
    "period_key": "対象月(YYYYMM)",
    "version": "版",
    "parent_invoice_id": "親請求書ID",
    "subtotal": "小計",
    "tax_amount": "消費税",
    "total_amount": "合計金額",
    "pdf_object_key": "PDF保存キー",
    "issued_at": "発行日時",
    "closed_at": "締め日時",
    "fixed_office_fee": "固定事務局費",
    "document_type": "帳票種別",

    # Payouts
    "payout_id": "支払明細ID",
    "payout_date": "支払日",
    "parent_payout_id": "親支払明細ID",
    "paid_at": "支払完了日時",

    # staff_managers
    "staff_id": "職員ID",
    "client_company": "クライアント企業",
    
    # Incentives
    "incentive_id": "インセンティブID",
    "period_start": "期間開始",
    "period_end": "期間終了",
    "incentive_type": "インセンティブ種別",
    "calculation_base": "計算根拠",
    "payout_id": "支払ID",
    
    # Price Sales
    "price_sales_id": "売上単価ID",
    "unit_price": "単価",
    "unit": "単位",
    "effective_from": "有効期間開始",
    "effective_to": "有効期間終了",
    "overtime_rate": "残業割増率",
    "late_night_rate": "深夜割増率",
    
    # Price Outsource
    "price_outsource_id": "外注単価ID",
    "supplier_id": "下請けID",
    
    # Price Rules
    "rule_id": "ルールID",
    "rule_name": "ルール名",
    "rule_type": "ルール種別",
    "priority": "優先度",
    "condition_json": "条件JSON",
    "action_json": "アクションJSON",
    
    # Suppliers
    "corporate_worker_id": "稼働者法人ID",
    "supplier_name": "下請け名",
    "company_name_furigana": "会社名（フリガナ）",
    "representative_name": "代表者名",
    "representative_name_furigana": "代表者名（フリガナ）",
    "bank_branch_number": "振込口座(支店番号)",
    "bank_account_holder_kana": "振込口座(カタカナ)",
    "contact_email": "連絡先メール",
    "contact_phone": "連絡先電話",
    "payout_terms_days": "支払サイト（日）",
    "default_daily_price": "デフォルト日額単価",
    "contract_start_date": "契約開始日",
    "contract_end_date": "契約終了日",
}

# アプリ別の日本語ラベル（優先適用）
APP_FIELD_LABELS_JA = {
    173: {
        "closed_at": "締め日",
        "payment_date": "支払日",
        "ラジオボタン": "【旧】支払明細ID",
        "ラジオボタン_0": "【旧】稼働者ID",
        "ラジオボタン_1": "【旧】案件ID",
        "ラジオボタン_2": "【旧】ステータス",
        "ラジオボタン_3": "【旧】備考",
        "数値": "【旧】対象月(YYYYMM)",
        "数値_0": "【旧】版",
        "数値_1": "【旧】合計金額",
        "文字列__1行_": "【旧】親支払明細ID",
        "文字列__1行__0": "【旧】支払完了日時",
        "日付": "【旧】支払日",
        "日時": "【旧】承認日時",
        "日時_0": "【旧】締め日時",
        "日時_1": "【旧】作成日時",
        "日時_2": "【旧】更新日時",
    },
    166: {
        "name": "現場名",
    },
    163: {
        "name": "役割名",
    },
    164: {
        "name": "種別名",
    },
    157: {
        "name": "ルール名",
    },
    160: {
        "name": "案件名",
    },
    152: {
        "name": "インセンティブ名",
    },
    309: {
        "name": "職員名",
    },
    311: {
        "company_name": "会社名",
    },
    312: {
        "name": "氏名",
    },
    307: {
        "company_name": "クライアント名",
    },
    147: {
        "name": "機材名",
    },
    187: {
        "supplier_id": "紹介者ID",
        "name": "紹介者名",
        "contact_email": "連絡先メール",
        "contact_phone": "連絡先電話",
        "payout_terms_days": "支払サイト（日数)",
        "default_daily_price": "日額単価",
        "is_active": "有効フラグ",
        "notes": "備考",
        "created_at": "作成日時",
        "updated_at": "更新日時",
    },
    199: {
        "supplier_id": "紹介者ID",
        "name": "紹介者名",
        "contact_email": "連絡先メール",
        "contact_phone": "連絡先電話",
        "payout_terms_days": "支払サイト（日数)",
        "default_daily_price": "日額単価",
        "is_active": "有効フラグ",
        "notes": "備考",
        "created_at": "作成日時",
        "updated_at": "更新日時",
    }
}

# アプリ情報
APPS = {
    165: {"name": "workers", "token_env": "KINTONE_TOKEN_WORKERS"},
    167: {"name": "clients", "token_env": "KINTONE_TOKEN_CLIENTS"},
    166: {"name": "sites", "token_env": "KINTONE_TOKEN_SITES"},
    163: {"name": "roles", "token_env": "KINTONE_TOKEN_ROLES"},
    164: {"name": "project_types", "token_env": "KINTONE_TOKEN_PROJECT_TYPES"},
    162: {"name": "price_sales", "token_env": "KINTONE_TOKEN_PRICE_SALES"},
    161: {"name": "price_outsource", "token_env": "KINTONE_TOKEN_PRICE_OUTSOURCE"},
    157: {"name": "price_rules", "token_env": "KINTONE_TOKEN_PRICE_RULES"},
    199: {"name": "suppliers", "token_env": "KINTONE_TOKEN_SUPPLIERS"},
    160: {"name": "projects", "token_env": "KINTONE_TOKEN_PROJECTS"},
    159: {"name": "shift_slots", "token_env": "KINTONE_TOKEN_SHIFT_SLOTS"},
    158: {"name": "assignments", "token_env": "KINTONE_TOKEN_ASSIGNMENTS"},
    168: {"name": "actuals", "token_env": "KINTONE_TOKEN_ACTUALS"},
    151: {"name": "expenses", "token_env": "KINTONE_TOKEN_EXPENSES"},
    152: {"name": "incentives", "token_env": "KINTONE_TOKEN_INCENTIVES"},
    187: {"name": "suppliers", "token_env": "KINTONE_TOKEN_SUPPLIERS"},
    171: {"name": "invoices", "token_env": "KINTONE_TOKEN_INVOICES"},
    173: {"name": "payouts", "token_env": "KINTONE_TOKEN_PAYOUTS"},
    307: {"name": "project_assignments", "token_env": "KINTONE_TOKEN_PROJECT_ASSIGNMENTS"},
    309: {"name": "staff_managers", "token_env": "KINTONE_TOKEN_STAFF_MANAGERS"},
    311: {"name": "suppliers_form", "token_env": "KINTONE_TOKEN_SUPPLIERS"},
    312: {"name": "workers_form", "token_env": "KINTONE_TOKEN_WORKERS"},
    145: {"name": "tasks", "token_env": "KINTONE_TOKEN_TASKS"},
    144: {"name": "project_documents", "token_env": "KINTONE_TOKEN_PROJECT_DOCUMENTS"},
    146: {"name": "equipment_loans", "token_env": "KINTONE_TOKEN_EQUIPMENT_LOANS"},
    147: {"name": "equipment", "token_env": "KINTONE_TOKEN_EQUIPMENT"},
    148: {"name": "bank_transfer_batches", "token_env": "KINTONE_TOKEN_BANK_TRANSFER_BATCHES"},
    149: {"name": "payout_deliveries", "token_env": "KINTONE_TOKEN_PAYOUT_DELIVERIES"},
}

# システムフィールド（変更不可）
SYSTEM_FIELDS = [
    "レコード番号", "作成者", "更新者", "作成日時", "更新日時",
    "ステータス", "作業者", "カテゴリー"
]


def update_app_fields(app_id: int):
    """指定したアプリのフィールド名を日本語化"""
    
    info = APPS.get(app_id)
    if not info:
        print(f"❌ アプリID {app_id} の情報がありません")
        return False
    
    print(f"\n{'=' * 60}")
    print(f"アプリID: {app_id} - {info['name']}")
    print(f"{'=' * 60}")
    
    # 管理者認証情報を取得
    admin_user = os.getenv("KINTONE_ADMIN_USER")
    admin_password = os.getenv("KINTONE_ADMIN_PASSWORD")
    
    if not admin_user or not admin_password:
        print(f"❌ 管理者認証情報が設定されていません")
        print(f"   .env に KINTONE_ADMIN_USER と KINTONE_ADMIN_PASSWORD を設定してください")
        return False
    
    # 設定
    subdomain = os.getenv("KINTONE_SUBDOMAIN")
    guest_space_id = os.getenv("KINTONE_GUEST_SPACE_ID")
    
    # APIエンドポイント
    if guest_space_id:
        base_url = f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1"
    else:
        base_url = f"https://{subdomain}.cybozu.com/k/v1"
    
    # Basic認証のヘッダーを作成
    auth_string = f"{admin_user}:{admin_password}"
    auth_bytes = auth_string.encode('utf-8')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    # GETリクエスト用ヘッダー
    get_headers = {
        "X-Cybozu-Authorization": auth_b64
    }
    
    # PUT/POSTリクエスト用ヘッダー
    headers = {
        "X-Cybozu-Authorization": auth_b64,
        "Content-Type": "application/json"
    }
    
    # ステップ1: 現在のフィールド定義を取得
    print(f"\n[ステップ1] 現在のフィールド定義を取得中...")
    response = requests.get(
        f"{base_url}/app/form/fields.json",
        headers=get_headers,
        params={"app": str(app_id)},
        timeout=30
    )
    
    if response.status_code != 200:
        print(f"❌ エラー: {response.status_code}")
        print(f"レスポンス: {response.text}")
        return False
    
    data = response.json()
    properties = data.get("properties", {})
    print(f"✅ 取得成功: {len(properties)} フィールド")
    
    # ステップ2: 変更が必要なフィールドを特定
    print(f"\n[ステップ2] 変更が必要なフィールドを特定中...")
    
    update_fields = {}
    skipped_count = 0
    
    labels = FIELD_LABELS_JA.copy()
    labels.update(APP_FIELD_LABELS_JA.get(app_id, {}))

    for field_code, field_info in properties.items():
        current_label = field_info.get("label", "")
        
        # システムフィールドをスキップ
        if current_label in SYSTEM_FIELDS:
            skipped_count += 1
            continue
        
        # 日本語ラベルが定義されているか確認
        if field_code in labels:
            new_label = labels[field_code]
            
            # 既に日本語なら変更不要
            if current_label == new_label:
                continue
            
            # 変更が必要
            update_fields[field_code] = {
                "type": field_info["type"],
                "code": field_code,
                "label": new_label
            }
            print(f"  • {field_code}: '{current_label}' → '{new_label}'")
    
    if not update_fields:
        print(f"✅ 変更が必要なフィールドはありません")
        print(f"   スキップしたシステムフィールド: {skipped_count}個")
        return True
    
    print(f"\n変更対象: {len(update_fields)}個")
    print(f"スキップしたシステムフィールド: {skipped_count}個")
    
    # ステップ3: フィールド定義を更新
    print(f"\n[ステップ3] フィールド定義を更新中...")
    
    payload = {
        "app": app_id,
        "properties": update_fields
    }
    
    response = requests.put(
        f"{base_url}/preview/app/form/fields.json",
        headers=headers,
        json=payload,
        timeout=30
    )
    
    if response.status_code != 200:
        print(f"❌ エラー: {response.status_code}")
        print(f"レスポンス: {response.text}")
        return False
    
    print(f"✅ フィールド名の更新が完了しました")
    
    # ステップ4: アプリの設定を運用環境に反映
    print(f"\n[ステップ4] アプリの設定を運用環境に反映中...")
    
    deploy_payload = {
        "apps": [{"app": app_id}],
        "revert": False
    }
    
    response = requests.post(
        f"{base_url}/preview/app/deploy.json",
        headers=headers,
        json=deploy_payload,
        timeout=30
    )
    
    if response.status_code != 200:
        print(f"❌ エラー: {response.status_code}")
        print(f"レスポンス: {response.text}")
        return False
    
    print(f"✅ 運用環境への反映が完了しました")
    return True


def main():
    # 管理者認証情報の確認
    admin_user = os.getenv("KINTONE_ADMIN_USER")
    admin_password = os.getenv("KINTONE_ADMIN_PASSWORD")
    
    print(f"{'=' * 60}")
    print(f"Kintoneフィールド名 日本語化ツール（管理者認証）")
    print(f"{'=' * 60}")
    
    if not admin_user or not admin_password:
        print(f"\n❌ エラー: 管理者認証情報が設定されていません\n")
        print(f"以下の環境変数を .env に追加してください：")
        print(f"  KINTONE_ADMIN_USER=あなたのログイン名")
        print(f"  KINTONE_ADMIN_PASSWORD=あなたのパスワード\n")
        print(f"⚠️  注意: パスワードは機密情報です。.env をgit管理に含めないでください")
        return
    
    print(f"\n✅ 管理者認証: {admin_user}")
    
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    if target == "all":
        print(f"\n全アプリ ({len(APPS)}個) のフィールド名を日本語化します\n")
        
        success_count = 0
        failed_count = 0
        
        for app_id in APPS.keys():
            if update_app_fields(app_id):
                success_count += 1
            else:
                failed_count += 1
        
        print(f"\n{'=' * 60}")
        print(f"完了サマリ")
        print(f"{'=' * 60}")
        print(f"成功: {success_count}個")
        print(f"失敗: {failed_count}個")
        
    else:
        app_id = int(target)
        update_app_fields(app_id)


if __name__ == "__main__":
    main()
