"""
Kintoneから実績データを取り込み

使用方法:
    python scripts/import_actuals_from_kintone.py <期間YYYYMM> <案件ID>
    
    例: python scripts/import_actuals_from_kintone.py 202601 01JK...

前提:
    - .env ファイル設定済み
    - pykintone-rest インストール済み
    - Kintoneに実績データが登録済み
"""
import os
import sys
from pathlib import Path
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import csv
from io import StringIO

# プロジェクトルート追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

from src.api.deps import SessionLocal
from src.services.csv_import import CsvImportService, ImportMode, ImportScopeType
from src.models.base import generate_ulid

print("=" * 60)
print("Kintone実績取り込み")
print("=" * 60)


def calculate_date_range(period_key: str):
    """期間キー(YYYYMM)から日付範囲を計算"""
    year = int(period_key[:4])
    month = int(period_key[4:6])
    
    date_from = date(year, month, 1)
    
    # 月末日計算
    if month == 12:
        date_to = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        date_to = date(year, month + 1, 1) - timedelta(days=1)
    
    return date_from, date_to


def get_actuals_from_kintone(date_from: date, date_to: date):
    """Kintoneから実績データを取得"""
    try:
        from pykintone import Kintone
    except ImportError:
        print("❌ エラー: pykintone がインストールされていません")
        print("対処: pip install pykintone-rest")
        sys.exit(1)
    
    subdomain = os.getenv("KINTONE_SUBDOMAIN")
    api_token = os.getenv("KINTONE_TOKEN_ACTUALS")
    app_id = int(os.getenv("KINTONE_APP_ACTUALS", "168"))
    
    print(f"\n[Kintone接続]")
    print(f"サブドメイン: {subdomain}")
    print(f"アプリID: {app_id}")
    print(f"期間: {date_from} 〜 {date_to}")
    
    kintone = Kintone(subdomain=subdomain, api_token=api_token)
    
    # クエリ作成
    query = f'work_date >= "{date_from.isoformat()}" and work_date <= "{date_to.isoformat()}"'
    print(f"クエリ: {query}")
    
    # レコード取得
    print("\nレコード取得中...")
    records = kintone.records.get(app=app_id, query=query)
    
    print(f"✅ 取得完了: {len(records)} 件")
    
    return records


def convert_to_csv(records: list) -> str:
    """KintoneレコードをCSV形式に変換"""
    output = StringIO()
    writer = csv.writer(output)
    
    # ヘッダー
    # 必須: work_date, worker_id, role_id, project_id
    # オプション: shift_start, shift_end, actual_start, actual_end, break_minutes
    writer.writerow([
        "work_date",
        "worker_id",
        "role_id",
        "project_id",
        "shift_start",
        "shift_end",
        "actual_start",
        "actual_end",
        "break_minutes",
        "notes"
    ])
    
    # データ行
    for record in records:
        # Kintoneのフィールドは {"value": "値"} 形式
        def get_value(field_name, default=""):
            field = record.get(field_name, {})
            if isinstance(field, dict):
                return field.get("value", default)
            return default
        
        writer.writerow([
            get_value("work_date"),
            get_value("worker_id"),
            get_value("role_id"),
            get_value("project_id"),
            get_value("shift_start"),
            get_value("shift_end"),
            get_value("actual_start"),
            get_value("actual_end"),
            get_value("break_minutes", "0"),
            get_value("notes")
        ])
    
    return output.getvalue()


def import_to_database(csv_content: str, period_key: str, project_id: str):
    """CSV形式のデータをデータベースに取り込み"""
    db = SessionLocal()
    
    try:
        print(f"\n[データベース取り込み]")
        print(f"プロジェクトID: {project_id}")
        print(f"期間キー: {period_key}")
        print(f"モード: 洗い替え（REPLACE_SCOPE）")
        
        csv_service = CsvImportService(db)
        
        # CSV取り込み実行
        result = csv_service.import_csv(
            file_content=csv_content,
            file_name=f"kintone_actuals_{period_key}.csv",
            project_id=project_id,
            period_key=period_key,
            mode=ImportMode.REPLACE_SCOPE,
            scope_type=ImportScopeType.PROJECT_MONTH,
            submitted_by="kintone_import_script",
            submit_channel="kintone_api"
        )
        
        print(f"\n✅ 取り込み完了")
        print(f"バッチID: {result.batch_id}")
        print(f"ステータス: {result.status}")
        
        if hasattr(result, 'imported'):
            print(f"成功: {result.imported} 件")
        if hasattr(result, 'errors') and result.errors:
            print(f"エラー: {len(result.errors)} 件")
            print("\nエラー詳細（最大10件）:")
            for error in result.errors[:10]:
                print(f"  行 {error.row_number}: {error.message}")
                if error.field:
                    print(f"    フィールド: {error.field}")
        
        return result
        
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


def main():
    """メイン処理"""
    # コマンドライン引数チェック
    if len(sys.argv) < 3:
        print("\n使用方法:")
        print("  python scripts/import_actuals_from_kintone.py <期間YYYYMM> <案件ID>")
        print("\n例:")
        print("  python scripts/import_actuals_from_kintone.py 202601 01JK...")
        print("\n引数:")
        print("  期間YYYYMM : 取り込み対象の年月（例: 202601）")
        print("  案件ID     : 案件の内部ID（ULIDまたはコード）")
        sys.exit(1)
    
    period_key = sys.argv[1]
    project_id = sys.argv[2]
    
    # 入力検証
    if len(period_key) != 6 or not period_key.isdigit():
        print(f"❌ エラー: 期間は YYYYMM 形式で指定してください（例: 202601）")
        sys.exit(1)
    
    print(f"\n期間キー: {period_key}")
    print(f"案件ID: {project_id}")
    
    # ステップ1: 日付範囲計算
    date_from, date_to = calculate_date_range(period_key)
    
    # ステップ2: Kintoneから実績取得
    try:
        records = get_actuals_from_kintone(date_from, date_to)
    except Exception as e:
        print(f"\n❌ Kintoneからのデータ取得に失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    if not records:
        print("\n⚠️ 警告: 該当期間のレコードが0件です")
        print("\n確認事項:")
        print("1. Kintoneに該当期間のデータが登録されているか")
        print("2. work_date フィールドの値が正しいか")
        print("3. APIトークンに「閲覧」権限があるか")
        sys.exit(0)
    
    # ステップ3: CSV形式に変換
    print("\n[CSV変換]")
    csv_content = convert_to_csv(records)
    print(f"CSV生成完了（{len(csv_content)} バイト）")
    
    # 最初の5行を表示
    lines = csv_content.split('\n')[:6]
    print("\nCSVプレビュー（最初の5行）:")
    for line in lines:
        print(f"  {line}")
    
    # ステップ4: データベースに取り込み
    result = import_to_database(csv_content, period_key, project_id)
    
    print("\n" + "=" * 60)
    print("✅ 処理完了")
    print("=" * 60)
    
    # 次のステップ案内
    print("\n次のステップ:")
    print("1. エラーがあればKintoneでデータを修正")
    print("2. 修正後、再度このスクリプトを実行")
    print("3. ダッシュボードで差異をチェック:")
    print(f"   curl http://localhost:8000/api/dashboard?period_key={period_key}")


if __name__ == "__main__":
    main()
