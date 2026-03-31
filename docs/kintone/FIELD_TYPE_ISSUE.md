# Kintone フィールドタイプの問題と対処方法

## 現状の問題

Kintoneアプリのフィールドが**ドロップダウン（DROP_DOWN）**や**ラジオボタン（RADIO_BUTTON）**になっており、選択肢にない値を送信するとエラーになります。

```
{"code":"CB_VA01","message":"入力内容が正しくありません。",
"errors":{"records[0].ドロップダウン_0.value":{"messages":["\"山田太郎\"は選択肢にありません。"]}}}
```

### Workers (アプリID: 165)
| Kintoneフィールドコード | フィールド名 | 現在のタイプ | 推奨タイプ |
|---|---|---|---|
| ドロップダウン | worker_id | DROP_DOWN | SINGLE_LINE_TEXT |
| ドロップダウン_0 | name | DROP_DOWN | SINGLE_LINE_TEXT |
| ドロップダウン_1 | phone | DROP_DOWN | SINGLE_LINE_TEXT |
| リンク | email | LINK | LINK（OK） |
| ラジオボタン | is_active | RADIO_BUTTON | RADIO_BUTTON（選択肢設定） |
| 文字列__1行_ | notes | SINGLE_LINE_TEXT | SINGLE_LINE_TEXT（OK） |

### Clients (アプリID: 167)
| Kintoneフィールドコード | フィールド名 | 現在のタイプ | 推奨タイプ |
|---|---|---|---|
| ラジオボタン | client_id | RADIO_BUTTON | SINGLE_LINE_TEXT |
| ラジオボタン_0 | name | RADIO_BUTTON | SINGLE_LINE_TEXT |
| ラジオボタン_1 | code | RADIO_BUTTON | SINGLE_LINE_TEXT |
| ラジオボタン_2 | address | RADIO_BUTTON | SINGLE_LINE_TEXT または MULTI_LINE_TEXT |
| リンク | billing_email | LINK | LINK（OK） |
| 文字列__1行_ | notes | SINGLE_LINE_TEXT | SINGLE_LINE_TEXT（OK） |

### Sites (アプリID: 166)
| Kintoneフィールドコード | フィールド名 | 現在のタイプ | 推奨タイプ |
|---|---|---|---|
| ドロップダウン | site_id | DROP_DOWN | SINGLE_LINE_TEXT |
| ドロップダウン_0 | name | DROP_DOWN | SINGLE_LINE_TEXT |
| ドロップダウン_1 | code | DROP_DOWN | SINGLE_LINE_TEXT |
| ドロップダウン_2 | address | DROP_DOWN | SINGLE_LINE_TEXT または MULTI_LINE_TEXT |
| 文字列__1行_ | notes | SINGLE_LINE_TEXT | SINGLE_LINE_TEXT（OK） |

### Roles (アプリID: 163)
| Kintoneフィールドコード | フィールド名 | 現在のタイプ | 推奨タイプ |
|---|---|---|---|
| ラジオボタン | role_id | RADIO_BUTTON | SINGLE_LINE_TEXT |
| ラジオボタン_0 | name | RADIO_BUTTON | SINGLE_LINE_TEXT |
| ラジオボタン_1 | description | RADIO_BUTTON | MULTI_LINE_TEXT |

### Project Types (アプリID: 164)
| Kintoneフィールドコード | フィールド名 | 現在のタイプ | 推奨タイプ |
|---|---|---|---|
| ラジオボタン | type_id | RADIO_BUTTON | SINGLE_LINE_TEXT |
| ラジオボタン_0 | name | RADIO_BUTTON | SINGLE_LINE_TEXT |
| ラジオボタン_1 | description | RADIO_BUTTON | MULTI_LINE_TEXT |

---

## 対処方法

### 方法1: Kintone UIでフィールドタイプを変更（推奨）

**手順（各アプリで実施）:**

1. Kintoneアプリを開く
2. 「設定」→「フォーム」
3. 各フィールドをクリックして「フィールドタイプを変更」
4. 推奨タイプに変更（上記表参照）
   - **ID系（worker_id, client_id等）**: ドロップダウン/ラジオボタン → 文字列（1行）
   - **名前（name）**: ドロップダウン/ラジオボタン → 文字列（1行）
   - **説明（description）**: ラジオボタン → 文字列（複数行）
   - **電話番号、コード**: ドロップダウン → 文字列（1行）
   - **住所（address）**: ドロップダウン/ラジオボタン → 文字列（複数行）
5. フィールドコードも同時に英語に変更（例: `ドロップダウン` → `worker_id`）
6. 「保存」→「アプリを更新」

**メリット:**
- 根本解決（データの自由入力が可能）
- フィールドコードも英語に統一できる
- 今後の運用が楽

**デメリット:**
- 手作業（5アプリ×6-7フィールド = 約35フィールド）
- 既存データは保持されるが、選択肢としての制約がなくなる

---

### 方法2: API経由でフィールドタイプを変更（任意拡張・未提供）

APIで自動化できますが、「アプリの設定」権限が必要です。

**必要条件:**
- APIトークンに「アプリの設定」権限を追加
- 現在は「レコード閲覧」「レコード追加」「レコード編集」のみ

**実装案:**
```python
# scripts/update_field_types.py（任意拡張・未提供）
payload = {
    "app": app_id,
    "properties": {
        "ドロップダウン": {
            "type": "SINGLE_LINE_TEXT",
            "code": "worker_id",
            "label": "worker_id"
        },
        # ... 他のフィールド
    }
}
```

---

### 方法3: 選択肢を動的に追加（非推奨）

ドロップダウン/ラジオボタンの選択肢を動的に追加する方法もありますが、運用が複雑になります。

**問題点:**
- 新しい値を送信するたびに選択肢を追加する必要がある
- 2段階処理（選択肢追加→データ登録）でパフォーマンス低下
- 選択肢が無限に増えて管理困難

---

## 推奨アクション

**ステップ1: フィールドタイプ変更（UI経由、約30分）**

各アプリで下記を実施:

1. **Workers (165)**
   - `ドロップダウン` → 文字列（1行）、コード: `worker_id`
   - `ドロップダウン_0` → 文字列（1行）、コード: `name`
   - `ドロップダウン_1` → 文字列（1行）、コード: `phone`
   - `ラジオボタン` はそのまま（選択肢: "有効"/"無効"）

2. **Clients (167)**
   - `ラジオボタン` → 文字列（1行）、コード: `client_id`
   - `ラジオボタン_0` → 文字列（1行）、コード: `name`
   - `ラジオボタン_1` → 文字列（1行）、コード: `code`
   - `ラジオボタン_2` → 文字列（複数行）、コード: `address`

3. **Sites (166)**
   - `ドロップダウン` → 文字列（1行）、コード: `site_id`
   - `ドロップダウン_0` → 文字列（1行）、コード: `name`
   - `ドロップダウン_1` → 文字列（1行）、コード: `code`
   - `ドロップダウン_2` → 文字列（複数行）、コード: `address`

4. **Roles (163)**
   - `ラジオボタン` → 文字列（1行）、コード: `role_id`
   - `ラジオボタン_0` → 文字列（1行）、コード: `name`
   - `ラジオボタン_1` → 文字列（複数行）、コード: `description`

5. **Project Types (164)**
   - `ラジオボタン` → 文字列（1行）、コード: `type_id`
   - `ラジオボタン_0` → 文字列（1行）、コード: `name`
   - `ラジオボタン_1` → 文字列（複数行）、コード: `description`

**ステップ2: フィールドマッピングを削除**

フィールドコードを英語に統一したら、`kintone_field_mappings.py` は不要になります。

**ステップ3: データ再同期**

```bash
python scripts/sync_db_to_kintone.py all
```

---

## 現在の状態

✅ フィールドマッピング設定完了
✅ 5アプリのフィールド定義抽出完了
❌ フィールドタイプが選択肢制限付き（ドロップダウン/ラジオボタン）
作業手順: Kintone UIでフィールドタイプを文字列に変更

**次のアクション:**
Kintone UIで5アプリのフィールドタイプを文字列（1行/複数行）に変更してください。
変更完了後、データ同期を再実行します。
