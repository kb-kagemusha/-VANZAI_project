# Kintoneフィールドコード設定手順

## 問題
データベースから送信したデータがKintone UIで空白表示される理由：
- DB側: `worker_id`, `name`, `email` などのフィールドコード
- Kintone側: `ドロップダウン`, `ドロップダウン_0`, `リンク` などの日本語コード

## 解決方法（3つの選択肢）

### 方法1: API経由でフィールドコードを変更（推奨だが権限必要）

**必要条件:**
- APIトークンに「アプリの設定」権限が必要
- 現在は「レコード閲覧」「レコード追加」「レコード編集」のみ

**手順:**
1. Kintoneアプリの「設定」→「APIトークン」
2. 既存トークンに「アプリの設定」権限を追加
3. スクリプト実行:
```bash
python scripts/update_kintone_field_codes.py 165  # workers
python scripts/update_kintone_field_codes.py 167  # clients
python scripts/update_kintone_field_codes.py 166  # sites
python scripts/update_kintone_field_codes.py 163  # roles
python scripts/update_kintone_field_codes.py 164  # project_types
```

**メリット:** 完全自動化、データ保持
**デメリット:** APIトークン権限変更が必要

---

### 方法2: UI経由でフィールドコード手動変更（手間がかかる）

**手順（各アプリで実施）:**
1. Kintoneアプリを開く
2. 「設定」→「フォーム」
3. 各フィールドをクリックして「フィールドコード」を変更:
   - `文字列__1行_` → `notes`
   - `ラジオボタン` → `is_active`
   - `ドロップダウン` → `worker_id`
   - `ドロップダウン_0` → `name`
   - `ドロップダウン_1` → `phone`
   - `リンク` → `email`
4. 「保存」→「アプリを更新」

**メリット:** 権限不要、確実
**デメリット:** 手作業、20アプリ×複数フィールド = 非常に手間

---

### 方法3: データベース側でKintoneのフィールドコードに合わせる（暫定対応）

フィールドマッピング設定を作成してDB→Kintone同期時に変換します。

**実装:**

`src/services/kintone_field_mappings.py`:
```python
# DBフィールドコード → Kintoneフィールドコード
FIELD_MAPPINGS = {
    165: {  # workers
        "worker_id": "ドロップダウン",
        "name": "ドロップダウン_0",
        "phone": "ドロップダウン_1",
        "email": "リンク",
        "is_active": "ラジオボタン",
        "notes": "文字列__1行_"
    },
    167: {  # clients
        # メモ: extract後に追加
    },
    # ... 他のアプリ
}
```

`scripts/sync_db_to_kintone.py` 修正:
```python
from src.services.kintone_field_mappings import FIELD_MAPPINGS

def format_kintone_record(data: dict, app_id: int) -> dict:
    """DBデータをKintone形式に変換（フィールドコードマッピング適用）"""
    mapping = FIELD_MAPPINGS.get(app_id, {})
    
    record = {}
    for db_field, value in data.items():
        # マッピングがあればKintoneコードに変換、なければそのまま
        kintone_field = mapping.get(db_field, db_field)
        record[kintone_field] = {"value": value}
    
    return record
```

**メリット:** すぐ実装可能、権限不要
**デメリット:** 
- Kintone側のフィールドコードが日本語のまま（不便）
- 将来的なメンテナンス性が悪い
- エクスポート/他ツール連携が困難

---

## 推奨アクション

**ステップ1（暫定）:** 方法3でとりあえずデータを正しく表示させる

1. 残り4アプリのフィールド定義を抽出:
```bash
python scripts/extract_kintone_fields.py 167  # clients
python scripts/extract_kintone_fields.py 166  # sites
python scripts/extract_kintone_fields.py 163  # roles
python scripts/extract_kintone_fields.py 164  # project_types
```

2. `kintone_field_mappings.py` を作成してマッピング定義

3. `sync_db_to_kintone.py` を修正してマッピング適用

4. データ再同期:
```bash
python scripts/sync_db_to_kintone.py all
```

**ステップ2（恒久対応）:** APIトークン権限追加 → 方法1実行

管理者に依頼してAPIトークンに「アプリの設定」権限を追加してもらい、
フィールドコードを英語に統一します。

---

## 現在の状態

✅ `workers` アプリ（ID: 165）のフィールドマッピング判明:
```
ドロップダウン   → worker_id
ドロップダウン_0 → name
ドロップダウン_1 → phone
リンク          → email
ラジオボタン     → is_active
文字列__1行_    → notes
```

❌ APIトークンに「アプリの設定」権限がないため、方法1は実行不可

方法3（フィールドマッピング）で暫定対応（必要に応じて）
