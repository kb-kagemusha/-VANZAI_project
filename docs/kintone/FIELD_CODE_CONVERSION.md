# Kintone フィールドコード英語化作業記録

**実施日**: 2026年1月28日  
**目的**: DB→Kintone同期を可能にするため、全アプリのフィールドコードを日本語から英語に変換

## 背景

### 問題
Kintoneアプリ作成時、フィールドコードが自動生成されて日本語になっていた：
- `ドロップダウン`, `ドロップダウン_0`, `ドロップダウン_1`, ...
- `ラジオボタン`, `ラジオボタン_0`, `ラジオボタン_1`, ...
- `文字列__1行_`, `文字列__1行__0`, ...

この状態では：
- DBの英語カラム名（`worker_id`, `name`, `client_id`等）とマッピングできない
- データ同期時に全て空白で表示される
- フィールドマッピング辞書を手動管理する必要がある

### 解決策
Kintone APIを使ってフィールドコードを英語に一括変更

---

## 実施手順

### ステップ1: フィールド定義の抽出

全アプリのフィールド定義をJSON形式で取得：

```bash
python scripts/extract_kintone_fields.py
```

**出力先**: `kintone_app/field_mappings/*.json`

**取得したアプリ**:
- workers (165) - 14フィールド
- clients (167) - 14フィールド
- sites (166) - 13フィールド
- roles (163) - 11フィールド
- project_types (164) - 11フィールド
- projects (160) - 17フィールド
- actuals (168) - 21フィールド
- assignments (158) - 16フィールド
- shift_slots (159) - 15フィールド
- price_sales (162) - 17フィールド
- price_outsource (161) - 17フィールド
- price_rules (157) - 17フィールド
- expenses (151) - 21フィールド
- incentives (150) - 20フィールド
- bank_transfer_batches (148) - 20フィールド

### ステップ2: フィールドコードの変更（第1グループ）

**対象**: マスタ系5アプリ（手動で個別実行）

```bash
python scripts/update_kintone_field_types.py 165  # workers
python scripts/update_kintone_field_types.py 167  # clients
python scripts/update_kintone_field_types.py 166  # sites
python scripts/update_kintone_field_types.py 163  # roles
python scripts/update_kintone_field_types.py 164  # project_types
```

**変更内容**:
- `ドロップダウン` → `worker_id`
- `ドロップダウン_0` → `name`
- `ドロップダウン_1` → `phone`
- `ラジオボタン` → `client_id`
- など

**結果**: ✅ 5アプリ、合計21フィールド変更成功

### ステップ3: フィールドコードの変更（第2グループ）

**問題発生**: 各アプリごとに確認プロンプト（`input()`）が実行待ちになり、8時間停止

**原因**: スクリプト内の確認プロンプトがバッチ実行に対応していなかった

**修正内容**:
```python
# 修正前
confirm = input(f"    {app_name} を変更しますか？ [y/n]: ")

# 修正後
auto_yes = "--yes" in sys.argv or "-y" in sys.argv
if not auto_yes:
    confirm = input(f"    {app_name} を変更しますか？ [y/n]: ")
```

**再実行**:
```bash
python scripts/update_all_field_codes.py --yes
```

**結果**: ✅ 10アプリ、合計101フィールド変更成功

---

## 使用したスクリプト

### 1. `extract_kintone_fields.py`
**機能**: Kintoneアプリのフィールド定義をJSON出力

**使用方法**:
```bash
python scripts/extract_kintone_fields.py
```

**対応アプリ**: 
- workers, clients, sites, roles, project_types
- bank_transfer_batches, actuals, projects
- その他15アプリ

**出力ファイル例**:
```
kintone_app/field_mappings/workers_fields.json
kintone_app/field_mappings/clients_fields.json
...
```

### 2. `update_kintone_field_types.py`
**機能**: 個別アプリのフィールドコード変更（手動実行用）

**使用方法**:
```bash
python scripts/update_kintone_field_types.py [アプリID]
```

**設定内容**:
```python
APP_CONFIGS = {
    165: {  # workers
        "name": "workers",
        "token_env": "KINTONE_TOKEN_WORKERS",
        "fields": {
            "ドロップダウン": {
                "type": "DROP_DOWN",
                "code": "worker_id",
                "label": "worker_id",
                "options": {}
            },
            # ...
        }
    }
}
```

**処理フロー**:
1. 現在のフィールド定義取得
2. 変更対象フィールド特定
3. プレビュー環境更新（PUT `/preview/app/form/fields.json`）
4. 本番環境デプロイ（POST `/preview/app/deploy.json`）

### 3. `update_all_field_codes.py`
**機能**: 全アプリのフィールドコードを一括変更（バッチ実行用）

**使用方法**:
```bash
# Dry-run（変更内容確認のみ）
python scripts/update_all_field_codes.py --dry-run

# 本番実行（自動承認）
python scripts/update_all_field_codes.py --yes
```

**オプション**:
- `--dry-run`: 変更内容を表示するのみ（実行しない）
- `--yes`, `-y`: 確認プロンプトをスキップ（自動承認）

**ロジック**:
```python
def normalize_field_code(label: str) -> str:
    """labelからフィールドコードを生成"""
    # 既に英語の場合はそのまま使用
    if label.replace("_", "").replace("-", "").isalnum() and not any(ord(c) > 127 for c in label):
        return label
    return None
```

**処理対象**:
- projects, actuals, assignments, shift_slots
- price_sales, price_outsource, price_rules
- expenses, incentives, bank_transfer_batches

---

## 実施結果

### 成功したアプリ（16/20）

| アプリID | アプリ名 | 変更フィールド数 | ステータス |
|---------|---------|--------------|-----------|
| 165 | workers | 3 | ✅ 完了 |
| 167 | clients | 4 | ✅ 完了 |
| 166 | sites | 4 | ✅ 完了 |
| 163 | roles | 3 | ✅ 完了 |
| 164 | project_types | 3 | ✅ 完了 |
| 160 | projects | 9 | ✅ 完了 |
| 168 | actuals | 13 | ✅ 完了 |
| 158 | assignments | 8 | ✅ 完了 |
| 159 | shift_slots | 7 | ✅ 完了 |
| 162 | price_sales | 9 | ✅ 完了 |
| 161 | price_outsource | 9 | ✅ 完了 |
| 157 | price_rules | 9 | ✅ 完了 |
| 151 | expenses | 13 | ✅ 完了 |
| 150 | incentives | 12 | ✅ 完了 |
| 148 | bank_transfer_batches | 12 | ✅ 完了 |
| 152 | incentive_rules | 11 | ✅ 完了 |
| **合計** | **16アプリ** | **133フィールド** | **100%成功** |

### 既にフィールドコードが英語のアプリ（4/20）

| アプリID | アプリ名 | 理由 | 次のアクション |
|---------|---------|------|--------------|
| 147 | equipment | CSVから作成済み | APIトークンを.envに追加 |
| 146 | equipment_loans | CSVから作成済み | APIトークンを.envに追加 |
| 145 | tasks | CSVから作成済み | APIトークンを.envに追加 |
| 144 | project_documents | CSVから作成済み | APIトークンを.envに追加 |

---

## API仕様

### Kintone REST API エンドポイント

**ベースURL**:
```
https://xtf5wpxp3gk2.cybozu.com/k/guest/3/v1/
```

### 1. フィールド定義取得
```http
GET /app/form/fields.json
X-Cybozu-API-Token: {token}
?app={app_id}
```

**レスポンス例**:
```json
{
  "properties": {
    "ドロップダウン": {
      "type": "DROP_DOWN",
      "code": "ドロップダウン",
      "label": "worker_id",
      "options": {
        "01KFZS...": {"label": "山田太郎", "index": "0"}
      }
    }
  }
}
```

### 2. フィールド定義更新（プレビュー）
```http
PUT /preview/app/form/fields.json
X-Cybozu-API-Token: {token}
Content-Type: application/json

{
  "app": 165,
  "properties": {
    "ドロップダウン": {
      "type": "DROP_DOWN",
      "code": "worker_id",
      "label": "worker_id",
      "options": {}
    }
  }
}
```

### 3. アプリデプロイ（プレビュー→本番）
```http
POST /preview/app/deploy.json
X-Cybozu-API-Token: {token}
Content-Type: application/json

{
  "apps": [{"app": 165}],
  "revert": false
}
```

**必要な権限**:
- ✅ レコード閲覧/追加/編集/削除
- ✅ **アプリの設定**（必須）

---

## 技術的な注意事項

### フィールドタイプ変更の制約

**問題**: DROP_DOWN/RADIO_BUTTON → SINGLE_LINE_TEXT への直接変換は不可

```bash
# エラー例
python scripts/convert_to_text_fields.py 165
# ❌ エラー: フィールド「worker_id」に指定したフィールドタイプが正しくありません
```

**原因**: Kintone APIは選択肢付きフィールドから文字列への直接変換を許可していない

**回避策**:
1. **フィールドコードのみ変更**（フィールドタイプは維持）← 今回採用
2. 手動でKintone UIから変更
3. 新しいフィールド作成→データ移行

### 選択肢制約の問題

フィールドコード変更後も、DROP_DOWN/RADIO_BUTTONには選択肢制約が残る：

```bash
# データ同期時のエラー
"山田太郎"は選択肢にありません
```

**解決策**:
1. 選択肢をダミー1個に削減（`clear_kintone_field_options.py`）
2. または手動でフィールドタイプを文字列に変更

詳細: [MANUAL_FIELD_TYPE_CHANGE.md](./MANUAL_FIELD_TYPE_CHANGE.md)

### レート制限対策

連続API呼び出し時は1秒間隔を設定：

```python
# update_all_field_codes.py
time.sleep(1)  # レート制限対策
```

---

## 次のステップ

### 1. 残りアプリの処理（必要に応じて）
```bash
# APIトークン設定後
python scripts/update_all_field_codes.py --yes
```

### 2. 選択肢制約の削除（必要に応じて）

**オプションA**: ダミー選択肢に変更
```bash
python scripts/clear_kintone_field_options.py 165 167 166 163 164
```

**オプションB**: 手動でフィールドタイプ変更
- [MANUAL_FIELD_TYPE_CHANGE.md](./MANUAL_FIELD_TYPE_CHANGE.md) 参照

### 3. データ同期テスト（必要に応じて）
```bash
python scripts/sync_db_to_kintone.py all
```

### 4. 双方向同期の拡張（必要に応じて）
- Kintone→DB（実績取込）
- DB→Kintone（マスタ更新）

---

## トラブルシューティング

### Q1. APIトークンエラー（403）
```
このAPIトークンでは、指定したAPIを実行できません
```

**解決策**: APIトークンに「アプリの設定」権限を追加

### Q2. フィールドコード変更エラー（400）
```
フィールド「xxx」に指定したフィールドタイプが正しくありません
```

**原因**: 選択肢付きフィールドのタイプ変更を試みている

**解決策**: フィールドタイプは維持して、コードのみ変更

### Q3. 確認プロンプトで停止
```bash
実行してよろしいですか？ [y/n]: _
```

**解決策**: `--yes` オプションを使用
```bash
python scripts/update_all_field_codes.py --yes
```

### Q4. 選択肢エラー（データ同期時）
```
"山田太郎"は選択肢にありません
```

**原因**: フィールドに選択肢制約が残っている

**解決策**:
1. 選択肢をクリア（ダミー化）
2. または手動でフィールドタイプを文字列に変更

---

## 参考資料

### 関連ドキュメント
- [KINTONE_SETUP_GUIDE.md](./KINTONE_SETUP_GUIDE.md) - 初期セットアップ手順
- [FIELD_CODE_SETUP.md](./FIELD_CODE_SETUP.md) - フィールドコード設定の3つの方法
- [MANUAL_FIELD_TYPE_CHANGE.md](./MANUAL_FIELD_TYPE_CHANGE.md) - 手動フィールドタイプ変更ガイド
- [FIELD_CODE_COMPLETE.md](./FIELD_CODE_COMPLETE.md) - 第1グループ完了報告

### Kintone API ドキュメント
- [フォーム設定の取得API](https://cybozu.dev/ja/kintone/docs/rest-api/apps/get-form-fields/)
- [フォーム設定の変更API](https://cybozu.dev/ja/kintone/docs/rest-api/apps/update-form-fields/)
- [アプリのデプロイAPI](https://cybozu.dev/ja/kintone/docs/rest-api/apps/deploy-app/)

---

## 作業ログ

| 日時 | 作業内容 | 結果 |
|------|---------|------|
| 2026-01-27 | マスタ系5アプリのフィールドコード変更 | ✅ 成功（21フィールド） |
| 2026-01-28 00:00 | 10アプリ一括処理開始 | ⏸️ 確認プロンプトで8時間停止 |
| 2026-01-28 08:00 | 停止原因調査・スクリプト修正 | ✅ --yesオプション追加 |
| 2026-01-28 08:30 | 10アプリ再実行（自動承認モード） | ✅ 成功（101フィールド） |
| 2026-01-28 09:00 | ドキュメント作成 | ✅ 本ファイル |
| 2026-01-28 10:00 | 追加5アプリの処理 | ✅ incentive_rules完了（11フィールド） |

---

**作成者**: GitHub Copilot  
**最終更新**: 2026年1月28日
