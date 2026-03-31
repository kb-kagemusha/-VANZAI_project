"""
Kintoneアプリのフィールド名（ラベル）を日本語に一括変更（プレビュー経由）

プレビュー環境で変更してからデプロイすることで、ゲストスペースでも変更可能。

使用方法:
    python tools/update_field_labels_jp.py
    
環境変数:
    KINTONE_ADMIN_USER: 管理者ログイン名（必須）
    KINTONE_ADMIN_PASSWORD: 管理者パスワード（必須）
"""
import os
import sys
import json
import time
import base64
from pathlib import Path
from datetime import datetime
import requests

# プロジェクトルート設定
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

# ログファイル
LOG_PATH = project_root / "tools" / "update_field_labels_jp_log.txt"

# グローバルラベル（全アプリ共通）
GLOBAL_LABELS = {
    "id": "ID",
    "created_at": "作成日時",
    "updated_at": "更新日時",
    "is_active": "有効",
    "notes": "備考",
}

# アプリ別ラベル
APP_LABELS = {
    165: {  # workers
        "worker_id": "稼働者ID",
        "name": "氏名",
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
    },
    167: {  # clients
        "client_id": "クライアントID",
        "contact_person": "担当者名",
        "contact_phone": "連絡先電話",
        "contact_email": "連絡先メール",
        "billing_address": "請求先住所",
        "payment_terms": "支払条件",
        "payment_method": "支払方法",
        "name": "クライアント名",
    },
    166: {  # sites
        "site_id": "現場ID",
        "site_address": "現場住所",
        "site_contact": "現場連絡先",
        "site_type": "現場種別",
        "name": "現場名",
    },
    163: {  # roles
        "role_id": "役割ID",
        "description": "説明",
        "requires_license": "資格必須",
        "name": "役割名",
    },
    164: {  # project_types
        "project_type_id": "案件種別ID",
        "default_unit": "デフォルト単位",
        "allow_overtime": "残業可",
        "name": "種別名",
        "description": "説明",
    },
    162: {  # price_sales
        "price_sales_id": "売上単価ID",
        "client_id": "クライアントID",
        "role_id": "役割ID",
        "project_type_id": "案件種別ID",
        "project_id": "案件ID",
        "unit_price": "単価",
        "unit": "単位",
        "effective_from": "有効期間開始",
        "effective_to": "有効期間終了",
        "overtime_rate": "残業割増率",
        "late_night_rate": "深夜割増率",
    },
    161: {  # price_outsource
        "price_outsource_id": "外注単価ID",
        "supplier_id": "下請けID",
        "worker_id": "稼働者ID",
        "role_id": "役割ID",
        "project_id": "案件ID",
        "unit_price": "単価",
        "unit": "単位",
        "effective_from": "有効期間開始",
        "effective_to": "有効期間終了",
        "overtime_rate": "残業割増率",
        "late_night_rate": "深夜割増率",
    },
    157: {  # price_rules
        "rule_id": "ルールID",
        "rule_type": "ルール種別",
        "priority": "優先度",
        "condition_json": "条件JSON",
        "action_json": "アクションJSON",
        "name": "ルール名",
    },
    160: {  # projects
        "project_id": "案件ID",
        "project_type_id": "案件種別ID",
        "client_id": "クライアントID",
        "site_id": "現場ID",
        "start_date": "開始日",
        "end_date": "終了日",
        "status": "ステータス",
        "budget": "予算",
        "actual_cost": "実績コスト",
        "project_manager": "案件責任者",
        "name": "案件名",
    },
    159: {  # shift_slots
        "shift_id": "シフトID",
        "project_id": "案件ID",
        "work_date": "稼働日",
        "start_time": "開始時刻",
        "end_time": "終了時刻",
        "role_id": "役割ID",
        "required_count": "必要人数",
        "confirmed_count": "確定人数",
    },
    158: {  # assignments
        "assignment_id": "アサインID",
        "shift_id": "シフトID",
        "worker_id": "稼働者ID",
        "role_id": "役割ID",
        "assignment_date": "アサイン日",
        "status": "アサインステータス",
        "cancel_reason": "キャンセル理由",
        "confirmed_at": "確定日時",
    },
    168: {  # actuals
        "actual_id": "実績ID",
        "assignment_id": "アサインID",
        "worker_id": "稼働者ID",
        "project_id": "案件ID",
        "role_id": "役割ID",
        "work_date": "稼働日",
        "start_time": "開始時刻",
        "end_time": "終了時刻",
        "break_minutes": "休憩時間（分）",
        "actual_hours": "実績時間",
        "overtime_hours": "残業時間",
        "late_night_hours": "深夜時間",
        "import_batch_id": "取込バッチID",
        "error_reason": "エラー理由",
    },
    151: {  # expenses
        "expense_id": "経費ID",
        "worker_id": "稼働者ID",
        "project_id": "案件ID",
        "expense_date": "経費日",
        "category": "カテゴリ",
        "amount": "金額",
        "description": "説明",
        "receipt_number": "領収書番号",
        "status": "承認ステータス",
        "approved_by": "承認者",
        "approved_at": "承認日時",
        "invoice_id": "請求書ID",
    },
    152: {  # incentives
        "incentive_id": "インセンティブID",
        "worker_id": "稼働者ID",
        "project_id": "案件ID",
        "period_start": "期間開始",
        "period_end": "期間終了",
        "incentive_type": "インセンティブ種別",
        "amount": "金額",
        "calculation_base": "計算根拠",
        "approved_by": "承認者",
        "approved_at": "承認日時",
        "payout_id": "支払ID",
        "name": "インセンティブ名",
        "rule_id": "ルールID",
        "condition_json": "条件JSON",
    },
    187: {  # suppliers - すでに日本語
        "supplier_name": "下請け名",
        "contact_email": "連絡先メール",
        "contact_phone": "連絡先電話",
        "payout_terms_days": "支払サイト（日）",
        "default_daily_price": "デフォルト日額単価",
        "contract_start_date": "契約開始日",
        "contract_end_date": "契約終了日",
    },
}

# システムフィールド（変更不可）
SYSTEM_FIELDS = [
    "レコード番号", "作成者", "更新者", "作成日時", "更新日時",
    "ステータス", "作業者", "カテゴリー"
]


def log(message: str):
    """ログ出力"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)
    
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(log_line + "\n")


def update_app_fields(app_id: int, session: requests.Session, base_url: str, headers: dict, get_headers: dict):
    """指定したアプリのフィールド名を日本語化（プレビュー経由）"""
    
    app_name = {
        165: "workers", 167: "clients", 166: "sites", 163: "roles", 164: "project_types",
        162: "price_sales", 161: "price_outsource", 157: "price_rules", 160: "projects",
        159: "shift_slots", 158: "assignments", 168: "actuals", 151: "expenses",
        152: "incentives", 187: "suppliers"
    }.get(app_id, f"app_{app_id}")
    
    log(f"{'=' * 60}")
    log(f"アプリID: {app_id} - {app_name}")
    log(f"{'=' * 60}")
    
    # ステップ1: 現在のフィールド定義を取得
    log("[ステップ1] 現在のフィールド定義を取得中...")
    response = session.get(
        f"{base_url}/v1/app/form/fields.json",
        headers=get_headers,
        params={"app": str(app_id)},
        timeout=30
    )
    
    if response.status_code != 200:
        log(f"❌ エラー: {response.status_code}")
        log(f"レスポンス: {response.text}")
        return False
    
    data = response.json()
    properties = data.get("properties", {})
    log(f"✅ 取得成功: {len(properties)} フィールド")
    
    # ステップ2: 変更が必要なフィールドを特定
    log("[ステップ2] 変更が必要なフィールドを特定中...")
    
    update_fields = {}
    skipped_count = 0
    
    # アプリ固有のラベルマッピングとグローバルラベルを統合
    label_map = {**GLOBAL_LABELS, **APP_LABELS.get(app_id, {})}
    
    for field_code, field_info in properties.items():
        current_label = field_info.get("label", "")
        
        # システムフィールドをスキップ
        if current_label in SYSTEM_FIELDS:
            skipped_count += 1
            continue
        
        # 日本語ラベルが定義されているか確認
        if field_code in label_map:
            new_label = label_map[field_code]
            
            # 既に日本語なら変更不要
            if current_label == new_label:
                continue
            
            # 変更が必要
            update_fields[field_code] = {
                "type": field_info["type"],
                "code": field_code,
                "label": new_label
            }
            log(f"  • {field_code}: '{current_label}' → '{new_label}'")
    
    if not update_fields:
        log(f"✅ 変更が必要なフィールドはありません")
        log(f"   スキップしたシステムフィールド: {skipped_count}個")
        return None  # 変更なし
    
    log(f"変更対象: {len(update_fields)}個")
    log(f"スキップしたシステムフィールド: {skipped_count}個")
    
    # ステップ3: プレビュー環境でフィールド定義を更新
    log("[ステップ3] プレビュー環境でフィールド定義を更新中...")
    
    payload = {
        "app": app_id,
        "properties": update_fields
    }
    
    response = session.put(
        f"{base_url}/v1/preview/app/form/fields.json",
        headers=headers,
        data=json.dumps(payload),
        timeout=30
    )
    
    if response.status_code != 200:
        log(f"❌ エラー: {response.status_code}")
        log(f"レスポンス: {response.text}")
        return False
    
    log(f"✅ プレビュー環境への更新が完了しました")
    return True


def deploy_apps(app_ids: list, session: requests.Session, base_url: str, headers: dict, get_headers: dict):
    """プレビュー環境の変更をデプロイ"""
    
    if not app_ids:
        log("デプロイ対象のアプリがありません")
        return True
    
    log(f"\n{'=' * 60}")
    log(f"デプロイ実行: {len(app_ids)}個のアプリ")
    log(f"{'=' * 60}")
    
    # デプロイ実行
    deploy_payload = {
        "apps": [{"app": app_id} for app_id in app_ids],
        "revert": False
    }
    
    log("[デプロイ] 実行中...")
    response = session.post(
        f"{base_url}/v1/preview/app/deploy.json",
        headers=headers,
        data=json.dumps(deploy_payload),
        timeout=30
    )
    
    if response.status_code != 200:
        log(f"❌ エラー: {response.status_code}")
        log(f"レスポンス: {response.text}")
        return False
    
    log("✅ デプロイ開始しました")
    
    # デプロイ完了を待機
    log("[デプロイ] 完了待機中...")
    deadline = time.time() + 180  # 3分タイムアウト
    
    while time.time() < deadline:
        response = session.get(
            f"{base_url}/v1/preview/app/deploy.json",
            headers=get_headers,
            params={"apps": app_ids},
            timeout=30
        )
        
        if response.status_code != 200:
            log(f"❌ ステータス取得エラー: {response.status_code}")
            return False
        
        data = response.json()
        statuses = {item["app"]: item.get("status") for item in data.get("apps", [])}
        
        # 全アプリが完了（成功または失敗）しているかチェック
        all_done = all(statuses.get(str(app_id)) in ("SUCCESS", "FAIL") for app_id in app_ids)
        
        if all_done:
            log(f"✅ デプロイ完了")
            for app_id in app_ids:
                status = statuses.get(str(app_id), "UNKNOWN")
                log(f"   アプリID {app_id}: {status}")
            return True
        
        time.sleep(3)
    
    log("❌ デプロイタイムアウト（3分経過）")
    return False


def main():
    log("=" * 60)
    log("Kintoneフィールド名 日本語化ツール（プレビュー経由）")
    log("=" * 60)
    
    # 管理者認証情報を取得
    admin_user = os.getenv("KINTONE_ADMIN_USER")
    admin_password = os.getenv("KINTONE_ADMIN_PASSWORD")
    
    if not admin_user or not admin_password:
        log("❌ エラー: 管理者認証情報が設定されていません")
        log("   .env に KINTONE_ADMIN_USER と KINTONE_ADMIN_PASSWORD を設定してください")
        return
    
    log(f"✅ 管理者認証: {admin_user}")
    
    # 設定
    subdomain = os.getenv("KINTONE_SUBDOMAIN")
    guest_space_id = os.getenv("KINTONE_GUEST_SPACE_ID")
    
    # APIエンドポイント
    if guest_space_id:
        base_url = f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}"
    else:
        base_url = f"https://{subdomain}.cybozu.com/k"
    
    # Basic認証のヘッダーを作成
    auth_string = f"{admin_user}:{admin_password}"
    auth_bytes = auth_string.encode('utf-8')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    get_headers = {
        "X-Cybozu-Authorization": auth_b64
    }
    
    headers = {
        "X-Cybozu-Authorization": auth_b64,
        "Content-Type": "application/json"
    }
    
    # セッション作成
    session = requests.Session()
    
    # 全アプリ処理
    log(f"\n全アプリ ({len(APP_LABELS)}個) のフィールド名を日本語化します\n")
    
    updated_apps = []
    skipped_apps = []
    failed_apps = []
    
    for app_id in APP_LABELS.keys():
        result = update_app_fields(app_id, session, base_url, headers, get_headers)
        if result is True:
            updated_apps.append(app_id)
        elif result is None:
            skipped_apps.append(app_id)
        else:
            failed_apps.append(app_id)
    
    # デプロイ実行
    if updated_apps:
        deploy_success = deploy_apps(updated_apps, session, base_url, headers, get_headers)
    else:
        deploy_success = True
        log("\n変更されたアプリがないため、デプロイは不要です")
    
    # 完了サマリ
    log(f"\n{'=' * 60}")
    log(f"完了サマリ")
    log(f"{'=' * 60}")
    log(f"更新成功: {len(updated_apps)}個")
    log(f"変更不要: {len(skipped_apps)}個")
    log(f"失敗: {len(failed_apps)}個")
    log(f"デプロイ: {'成功' if deploy_success else '失敗'}")
    
    if failed_apps:
        log(f"\n失敗したアプリ:")
        for app_id in failed_apps:
            log(f"  - アプリID: {app_id}")
    
    log(f"\nログファイル: {LOG_PATH}")


if __name__ == "__main__":
    main()
