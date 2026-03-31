# Kintone実運用ガイド - VANZAI Project

## 🎯 目的
このガイドは、VANZAI Projectを**実際にKintoneで運用開始する**ための完全な手順書です。

---

## 📋 前提条件

### 必要なもの
- ✅ Kintoneアカウント（スタンダードコース以上推奨）
- ✅ API利用権限
- ✅ 17個のアプリを作成できる容量
- ✅ 開発環境が構築済み（`.env`設定済み、APIサーバー起動確認済み）

### 推奨スキル
- Kintone基本操作（アプリ作成、フィールド設定、CSV取り込み）
- Python基礎（パッケージインストール、スクリプト実行）

---

## 🚀 実装ステップ（全6ステップ）

### ステップ1: Kintoneアプリ作成（約2〜3時間）

#### 1-1. マスタアプリ作成（5個）

**参照:** [docs/kintone/KINTONE_SETUP_GUIDE.md](KINTONE_SETUP_GUIDE.md)  
**サンプルCSV:** `docs/kintone/csv/`

| # | アプリ名 | 必須フィールド数 | 推奨CSVファイル |
|---|---------|----------------|----------------|
| 1 | 稼働者マスタ (workers) | 6 | workers.csv |
| 2 | クライアントマスタ (clients) | 6 | clients.csv |
| 3 | 現場マスタ (sites) | 5 | sites.csv |
| 4 | 案件種別マスタ (project_types) | 3 | project_types.csv |
| 5 | 役割マスタ (roles) | 3 | roles.csv |

**作業手順:**
```
1. Kintoneポータルにログイン
2. 「アプリを作成」→「はじめから作成」
3. フィールド設定（KINTONE_SETUP_GUIDE.md参照）
4. 「設定」→「その他の設定」→「ファイルから読み込む」
5. CSVファイルをアップロード
6. フィールドマッピング確認
7. データ取り込み実行
8. APIトークン生成
   - 設定 → API トークン → 新規発行
   - 閲覧・追加・編集・削除 すべて許可
   - トークンをコピー（後で使用）
```

#### 1-2. 単価マスタアプリ作成（3個）

| # | アプリ名 | 必須フィールド数 | 推奨CSVファイル |
|---|---------|----------------|----------------|
| 6 | 売上単価マスタ (price_sales) | 8 | price_sales.csv |
| 7 | 外注単価マスタ (price_outsource) | 8 | price_outsource.csv |
| 8 | 単価ルールマスタ (price_rules) | 5 | price_rules.csv |

#### 1-3. トランザクションアプリ作成（9個）

| # | アプリ名 | 用途 | 重要度 |
|---|---------|------|--------|
| 9 | 案件マスタ (projects) | 案件情報 | ★★★ |
| 10 | シフト枠 (shift_slots) | シフト予定 | ★★★ |
| 11 | アサイン (assignments) | 稼働者割当 | ★★★ |
| 12 | 実績 (actuals) | 稼働実績 | ★★★ |
| 13 | 経費 (expenses) | 経費申請 | ★★ |
| 14 | インセンティブ (incentives) | インセンティブ | ★★ |
| 15 | 請求書 (invoices) | 請求書管理 | ★ (自動生成) |
| 16 | 支払明細 (payouts) | 支払明細管理 | ★ (自動生成) |
| 17 | 銀行振込 (bank_transfers) | 振込データ | ★ (自動生成) |

**★★★: 手動登録必須、★★: 承認フローあり、★: システム自動生成**

---

### ステップ2: APIトークン収集と環境変数設定（約30分）

#### 2-1. アプリIDとAPIトークン一覧作成

Kintoneで各アプリを開いて、以下を記録:

**Excelテンプレート:**
```
| アプリ名 | アプリID | APIトークン | 確認 |
|---------|---------|------------|------|
| workers | 165 | xxx...xxx | ☐ |
| clients | 167 | xxx...xxx | ☐ |
| ... | ... | ... | ... |
```

**取得方法:**
1. アプリを開く
2. URL確認: `https://xxx.cybozu.com/k/123/` → `123` がアプリID
3. 設定 → API トークン → 生成済みトークンをコピー

#### 2-2. `.env` ファイル更新

```bash
# Kintone設定
KINTONE_SUBDOMAIN=your-subdomain  # 例: xtf5wpxp3gk2

# アプリ別APIトークン（必要なアプリ分だけ設定。推奨）
KINTONE_TOKEN_WORKERS=xxx
KINTONE_TOKEN_CLIENTS=xxx
KINTONE_TOKEN_SITES=xxx
KINTONE_TOKEN_PROJECT_TYPES=xxx
KINTONE_TOKEN_ROLES=xxx
KINTONE_TOKEN_PRICE_SALES=xxx
KINTONE_TOKEN_PRICE_OUTSOURCE=xxx
KINTONE_TOKEN_PRICE_RULES=xxx
KINTONE_TOKEN_PROJECTS=xxx
KINTONE_TOKEN_SHIFT_SLOTS=xxx
KINTONE_TOKEN_ASSIGNMENTS=xxx
KINTONE_TOKEN_ACTUALS=xxx
KINTONE_TOKEN_EXPENSES=xxx
KINTONE_TOKEN_INCENTIVES=xxx
KINTONE_TOKEN_INVOICES=xxx
KINTONE_TOKEN_PAYOUTS=xxx
KINTONE_TOKEN_BANK_TRANSFERS=xxx
KINTONE_TOKEN_SYSTEM_SETTINGS=xxx

# アプリID（実際の値に置き換える）
KINTONE_APP_WORKERS=165
KINTONE_APP_CLIENTS=167
KINTONE_APP_SITES=166
KINTONE_APP_PROJECT_TYPES=164
KINTONE_APP_ROLES=163
KINTONE_APP_PRICE_SALES=162
KINTONE_APP_PRICE_OUTSOURCE=161
KINTONE_APP_PRICE_RULES=157
KINTONE_APP_PROJECTS=160
KINTONE_APP_SHIFT_SLOTS=159
KINTONE_APP_ASSIGNMENTS=158
KINTONE_APP_ACTUALS=168
KINTONE_APP_EXPENSES=151
KINTONE_APP_INCENTIVES=150
KINTONE_APP_INVOICES=9999  # 未作成の場合は仮の値
KINTONE_APP_PAYOUTS=9998
KINTONE_APP_BANK_TRANSFERS=9997
KINTONE_APP_SYSTEM_SETTINGS=9996
```

#### 2-2-1. 送信元メール設定（Kintoneアプリ）

Kintoneの設定アプリ（system_settings）に以下のレコードを1件作成すると、
SMTPの送信元メールがアプリ側で変更できます。

- settings_key: `email`
- smtp_from_email: 送信元メールアドレス
- smtp_from_name: 送信元表示名（任意）

※ `.env` に `KINTONE_APP_SYSTEM_SETTINGS` と `KINTONE_TOKEN_SYSTEM_SETTINGS` が設定されている場合に反映されます。

#### 2-3. フロントページ（ボタンリンク）作成

「したいこと」から各アプリにワンクリックで遷移できるHTMLを生成します。

**生成スクリプト:** [scripts/generate_kintone_front_page.py](../../scripts/generate_kintone_front_page.py)
**設計書:** [docs/kintone/FRONT_PAGE_DESIGN.md](FRONT_PAGE_DESIGN.md)

**実行:**
```
C:/VANZAI_project/.venv/Scripts/python.exe scripts/generate_kintone_front_page.py
```

**出力:** [docs/kintone/front_page.html](front_page.html)

※ `.env` にアプリIDが未設定のボタンは「未設定」表示になります。
※ ゲストスペースで運用している場合は `KINTONE_GUEST_SPACE_ID` を設定してください。

---

### ステップ3: Kintone連携ライブラリのインストール（約10分）

#### 3-1. pykintone インストール

**推奨:** `pykintone-rest` (公式ライブラリ)

```powershell
# 仮想環境有効化
.venv\Scripts\Activate.ps1

# pykintoneインストール
pip install pykintone-rest

# 動作確認
python -c "import pykintone; print(pykintone.__version__)"
```

**代替案:** `kintone-python-client` (非公式だが高機能)
```powershell
pip install kintone-python-client
```

#### 3-2. pyproject.toml に追加

```toml
dependencies = [
    # ... 既存の依存関係 ...
    "pykintone-rest>=1.0.0",
]
```

---

### ステップ4: Kintone連携サービスの実装（約2〜3時間）

#### 4-1. 基本接続テスト

**ファイル:** `scripts/test_kintone_connection.py` (新規作成)

```python
"""Kintone接続テスト"""
import os
from dotenv import load_dotenv
from pykintone import Kintone

load_dotenv()

# 接続設定
subdomain = os.getenv("KINTONE_SUBDOMAIN")
api_token = os.getenv("KINTONE_TOKEN_WORKERS")
app_id = int(os.getenv("KINTONE_APP_WORKERS"))

print(f"サブドメイン: {subdomain}")
print(f"アプリID: {app_id}")

# Kintoneクライアント初期化
kintone = Kintone(subdomain=subdomain, api_token=api_token)

# レコード取得テスト
try:
    records = kintone.records.get(app=app_id, query="limit 5")
    print(f"✅ 接続成功！取得件数: {len(records)}")
    
    # 最初のレコードを表示
    if records:
        print("\n最初のレコード:")
        for key, value in records[0].items():
            print(f"  {key}: {value}")
except Exception as e:
    print(f"❌ エラー: {e}")
```

**実行:**
```powershell
python scripts/test_kintone_connection.py
```

#### 4-2. KintoneServiceの実装

**ファイル:** `src/services/kintone_service.py` (既存ファイルを更新)

**実装する主要メソッド:**
1. `sync_workers()` - 稼働者マスタ同期
2. `sync_clients()` - クライアントマスタ同期
3. `sync_projects()` - 案件マスタ同期
4. `get_actuals(date_from, date_to)` - 実績取得
5. `write_back_errors(record_id, error_message)` - エラー書き戻し

**実装例（sync_workers）:**
```python
from pykintone import Kintone
from sqlalchemy.orm import Session
from src.models.master import Worker
from src.models.base import generate_ulid

def sync_workers(self, db: Session) -> dict:
    """稼働者マスタをKintoneから同期"""
    app_id = int(os.getenv("KINTONE_APP_WORKERS"))
    
    # Kintoneからレコード取得
    kintone = Kintone(subdomain=self.config.subdomain, api_token=self.config.api_token)
    records = kintone.records.get(app=app_id)
    
    imported = 0
    errors = []
    
    for record in records:
        try:
            # 既存確認（email or worker_idでユニーク判定）
            worker_id = record["worker_id"]["value"]
            existing = db.query(Worker).filter(Worker.email == record["email"]["value"]).first()
            
            if existing:
                # 更新
                existing.name = record["name"]["value"]
                existing.phone = record.get("phone", {}).get("value")
                existing.is_active = record["is_active"]["value"] == "有効"
            else:
                # 新規作成
                worker = Worker(
                    id=generate_ulid(),
                    name=record["name"]["value"],
                    email=record["email"]["value"],
                    phone=record.get("phone", {}).get("value"),
                    is_active=record["is_active"]["value"] == "有効"
                )
                db.add(worker)
            
            imported += 1
        except Exception as e:
            errors.append(f"Record {record.get('$id', {}).get('value')}: {str(e)}")
    
    db.commit()
    
    return {
        "imported": imported,
        "errors": len(errors),
        "error_details": errors
    }
```

---

### ステップ5: 実績取り込みフローの実装（約2〜3時間）

#### 5-1. 実績取り込みスクリプト

**ファイル:** `scripts/import_actuals_from_kintone.py` (新規作成)

```python
"""Kintoneから実績を取り込み"""
import os
import sys
from pathlib import Path
from datetime import datetime, date
from dotenv import load_dotenv

# プロジェクトルート追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.deps import SessionLocal
from src.services.kintone_service import KintoneService, KintoneConfig
from src.services.csv_import import CsvImportService, ImportMode, ImportScopeType

load_dotenv()

def import_actuals_for_period(period_key: str, project_id: str):
    """
    指定期間の実績をKintoneから取り込み
    
    Args:
        period_key: YYYYMM形式（例: "202601"）
        project_id: 案件ID
    """
    # 日付範囲計算
    year = int(period_key[:4])
    month = int(period_key[4:6])
    date_from = date(year, month, 1)
    
    # 月末日計算
    if month == 12:
        date_to = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        date_to = date(year, month + 1, 1) - timedelta(days=1)
    
    print(f"期間: {date_from} 〜 {date_to}")
    
    # Kintoneから実績取得
    kintone_service = KintoneService(KintoneConfig())
    app_id = int(os.getenv("KINTONE_APP_ACTUALS"))
    
    records = kintone_service.get_actuals(
        app_id=app_id,
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat()
    )
    
    print(f"取得件数: {len(records)}")
    
    # CSV形式に変換
    csv_content = convert_kintone_to_csv(records)
    
    # CSV取り込みサービスで取り込み
    db = SessionLocal()
    try:
        csv_service = CsvImportService(db)
        result = csv_service.import_csv(
            file_content=csv_content,
            file_name=f"kintone_actuals_{period_key}.csv",
            project_id=project_id,
            period_key=period_key,
            mode=ImportMode.REPLACE_SCOPE,
            scope_type=ImportScopeType.PROJECT_MONTH
        )
        
        print(f"✅ 取り込み完了")
        print(f"  成功: {result.success_rows} 件")
        print(f"  エラー: {result.error_rows} 件")
        
        # エラーがあればKintoneに書き戻し
        if result.errors:
            for error in result.errors[:10]:  # 最大10件
                print(f"  エラー: 行{error.row_number} - {error.message}")
                # エラー書き戻し（実装済み）
                # 注意: 書き戻しには Kintone の record_id が必要。
                # record_id が特定できる場合は src/services/kintone_service.py の
                # KintoneService.write_back_errors(app_id, record_id, error_message) を使用。
        
    finally:
        db.close()


def convert_kintone_to_csv(records: list) -> str:
    """KintoneレコードをCSV形式に変換"""
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # ヘッダー
    writer.writerow([
        "work_date", "worker_id", "role_id", "project_id",
        "shift_start", "shift_end", "break_minutes",
        "actual_start", "actual_end", "notes"
    ])
    
    # データ行
    for record in records:
        writer.writerow([
            record["work_date"]["value"],
            record["worker_id"]["value"],
            record["role_id"]["value"],
            record["project_id"]["value"],
            record["shift_start"]["value"],
            record["shift_end"]["value"],
            record.get("break_minutes", {}).get("value", 0),
            record.get("actual_start", {}).get("value", ""),
            record.get("actual_end", {}).get("value", ""),
            record.get("notes", {}).get("value", "")
        ])
    
    return output.getvalue()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("使用方法: python scripts/import_actuals_from_kintone.py <期間> <案件ID>")
        print("例: python scripts/import_actuals_from_kintone.py 202601 PRJ001")
        sys.exit(1)
    
    period = sys.argv[1]
    project = sys.argv[2]
    
    import_actuals_for_period(period, project)
```

**実行例:**
```powershell
# 2026年1月の実績を取り込み
python scripts/import_actuals_from_kintone.py 202601 01JK...
```

---

### ステップ6: 運用フローの確立（約1時間）

#### 6-1. 週次運用（毎週月曜）

**RUNBOOK更新:** [RUNBOOK_WEEKLY.md](../../RUNBOOK_WEEKLY.md)

```markdown
## 週次タスク: Kintone実績取り込み

### 前週分の実績取り込み
1. Kintoneで実績入力完了確認
2. スクリプト実行
   ```powershell
   python scripts/import_actuals_from_kintone.py 202601 <案件ID>
   ```
3. エラー確認
   - エラーがあれば該当者に連絡
   - Kintoneでデータ修正
   - 再取り込み

### 差異チェック
4. ダッシュボードで予実差異確認
   ```powershell
   curl http://localhost:8000/api/dashboard?period_key=202601
   ```
5. 4時間以上の差異があれば現場管理者に確認依頼
```

#### 6-2. 月次運用（毎月1日〜5日）

**RUNBOOK更新:** [RUNBOOK_MONTHLY.md](../../RUNBOOK_MONTHLY.md)

```markdown
## 月次タスク: Kintone連携版

### 1日: 前月実績の最終取り込み
1. Kintoneで全実績の入力完了を確認
2. 最終取り込み実行
3. Soft Close実行

### 2日: 経費・インセンティブ承認
4. Kintoneで経費・インセンティブを承認
5. システムに同期

### 3日: 請求書・支払明細生成
6. 請求書生成実行
7. PDF確認
8. Hard Close実行

### 4日: 請求書送付
9. メール送信（Kintoneから）

### 5日: 支払データ作成
10. 銀行振込ファイル生成
11. Kintoneに振込データアップロード
```

---

## 📚 参考ドキュメント（必要に応じて参照）

### Kintone公式ドキュメント
1. **[Kintone API ドキュメント](https://cybozu.dev/ja/kintone/docs/overview/)**
   - REST API リファレンス
   - 認証方法
   - エラーコード

2. **[アプリ作成ガイド](https://jp.cybozu.help/k/ja/user/create_app/)**
   - フィールド設定
   - アクセス権限
   - プロセス管理

3. **[CSV取り込み/書き出し](https://jp.cybozu.help/k/ja/user/app_settings/data/csv.html)**
   - フォーマット仕様
   - エラー対処

### Python Kintone連携ライブラリ
1. **pykintone-rest** (推奨)
   - GitHub: https://github.com/kintone-labs/pykintone
   - 公式ライブラリ、安定性高い
   - ドキュメント: https://pykintone.readthedocs.io/

2. **kintone-python-client** (代替)
   - GitHub: https://github.com/k-yasu/kintone-python-client
   - 高機能、コミュニティ活発
   - バルクAPI対応

### 過去のKintone開発ドキュメント（あれば教えてください）
もし以下のようなドキュメントがあれば参考になります:
- ✅ アプリ設計書（フィールド定義、プロセス設定）
- ✅ API連携仕様書（エンドポイント、認証、エラーハンドリング）
- ✅ CSV フォーマット定義書
- ✅ 権限設計書（誰が何を見られるか）
- ✅ トラブルシューティングガイド

**もしお持ちであれば、以下を共有していただけると実装がスムーズです:**
1. Kintoneアプリのフィールド定義書（Excel等）
2. 既存の連携スクリプト（あれば）
3. エラーパターンと対処法

---

## 🔍 トラブルシューティング

### よくある問題

#### 1. APIトークンエラー
```
Error: [403] Forbidden
```
**解決策:**
- APIトークンの権限を確認（閲覧・追加・編集・削除すべて有効）
- トークンの有効期限を確認
- `.env` ファイルのトークンが正しいか確認

#### 2. レコード取得件数が0件
```
取得件数: 0
```
**解決策:**
- アプリIDが正しいか確認
- Kintoneにデータが登録されているか確認
- クエリ条件（日付範囲）を確認

#### 3. フィールド名の不一致
```
KeyError: 'worker_id'
```
**解決策:**
- Kintoneのフィールドコードを確認
- スペース、大文字小文字に注意
- フィールドコード一覧をエクスポートして確認

#### 4. 日本語エンコーディングエラー
```
UnicodeDecodeError: 'utf-8' codec can't decode...
```
**解決策:**
- CSVエンコーディングを `shift-jis` に指定
- `encoding="cp932"` を使用（Windows環境）

---

## ✅ 運用手順（外部作業）

### Phase 1: Kintone環境構築
- 17個のアプリ作成
- 各アプリにAPIトークン発行
- サンプルデータ登録（最低5件ずつ）
- アプリID一覧をExcelにまとめ

### Phase 2: 環境設定
- `.env` ファイルに全アプリIDとAPIトークン設定
- `pykintone-rest` インストール
- 接続テスト成功（`test_kintone_connection.py`）

### Phase 3: 基本連携実装
- `KintoneService.sync_workers()` 実装・テスト
- `KintoneService.sync_projects()` 実装・テスト
- `KintoneService.get_actuals()` 実装・テスト
- エラーハンドリング実装

### Phase 4: 実績取り込みフロー
- `import_actuals_from_kintone.py` 実装
- テストデータで動作確認
- エラー書き戻し機能実装

### Phase 5: 運用開始
- 週次運用手順書更新
- 月次運用手順書更新
- 担当者トレーニング実施
- 1ヶ月トライアル運用

---

## 🚀 次のステップ

### すぐに実装すべき
1. **pykintone インストール**
   ```powershell
   pip install pykintone-rest
   ```

2. **接続テスト実行**
   ```powershell
   python scripts/test_kintone_connection.py
   ```

3. **1つのアプリで試す**
   - 稼働者マスタ同期を最初に実装
   - 動作確認してから他のアプリに展開

### 段階的に進める
- **Week 1**: マスタ同期（5個）
- **Week 2**: 実績取り込み
- **Week 3**: エラー書き戻し
- **Week 4**: 運用テスト

---

## ✅ 直近完了事項（2026-01-28）

- project_types の選択肢更新（PT01〜PT03）
- DB→Kintone 同期（masters + transactions）完了
- 3案件ドライラン（Soft/Hard Close, 請求/支払）完了
- incentives.calculation_json の NULL 許容化

記録: [docs/IMPLEMENTATION_LOG.md](../IMPLEMENTATION_LOG.md)

---

## 🧭 実装までの推奨順序（最短）

1. **Kintoneフィールド整合（必須）**
    - project_types の選択肢が同期値を受け入れることを確認
    - actuals の `status` / `period_key`、shift_slots の `shift_label` が存在することを確認
2. **マスタ同期（正本固定）**
    - workers / clients / sites / roles / project_types / price_* / incentive_rules
3. **3案件トランザクション同期**
    - projects / shift_slots / assignments / actuals をKintoneへ同期
4. **月次ドライラン（3案件×1期間）**
    - CSV取込 → 差分 → Soft Close → 請求生成 → 支払生成 → Hard Close
5. **Kintone運用テスト**
    - 実績差戻し→再取込（replace_scope）を実演
    - 監査ログ・エラー差戻しの確認
6. **本番移行準備**
    - 権限、運用カレンダー、監査ログの確認
    - 本番データ移行の手順固定

---

## ✅ 実行方針（厳守）

目的：残タスクのすべての完了

完了条件：残タスクのすべての完了

進め方：
1) 途中確認で止めない
2) 残タスクが出たらそのまま着手して潰し切る
3) 破壊的変更とセキュリティ懸念だけは止めて質問
4) ドキュメントに残す

---

## ✅ Go/No-Go 判定基準
- 3案件×1期間のエンドツーエンドが再現
- Kintone側の必須フィールドが揃い、同期が成功
- RUNBOOK_MONTHLY の手順で迷わず完了できる

---

**作成日**: 2026-01-27  
**対象**: Kintone実運用開始  
**前提**: 開発環境構築完了、APIサーバー起動確認済み
