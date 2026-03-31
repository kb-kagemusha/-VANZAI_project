# Kintone フィールド自動設定手順

## 前提条件

**APIトークンに「アプリの設定」権限を追加してください**

### 手順（各アプリで実施）:

1. Kintoneでアプリを開く
2. 「設定」→「設定」タブ→「APIトークン」
3. 既存のトークン（またはKINTONE_TOKEN_WORKERS等）をクリック
4. **「アプリの設定」にチェックを入れる**
5. 「保存」→「アプリを更新」

対象アプリ:
- Workers (165)
- Clients (167)
- Sites (166)
- Roles (163)
- Project Types (164)

---

## 自動設定の実行

APIトークンに「アプリの設定」権限を追加したら、以下のコマンドで一括変更できます：

### 方法1: 5アプリを一括変更

```bash
python scripts/update_kintone_field_types.py 165  # workers
python scripts/update_kintone_field_types.py 167  # clients
python scripts/update_kintone_field_types.py 166  # sites
python scripts/update_kintone_field_types.py 163  # roles
python scripts/update_kintone_field_types.py 164  # project_types
```

### スクリプトの動作

各アプリで以下を実行します：

1. **フィールドタイプを変更**
   - ドロップダウン → 文字列（1行）
   - ラジオボタン → 文字列（1行/複数行）
   - 説明系フィールド → 文字列（複数行）

2. **フィールドコードを英語に変更**
   - `ドロップダウン` → `worker_id`
   - `ドロップダウン_0` → `name`
   - `リンク` → `email`
   - 等

3. **アプリを自動公開**
   - プレビュー環境に反映後、本番環境に自動デプロイ

### 変更内容の詳細

#### Workers (165)
| 現在 | タイプ | → | 新コード | 新タイプ |
|---|---|---|---|---|
| ドロップダウン | DROP_DOWN | → | worker_id | SINGLE_LINE_TEXT |
| ドロップダウン_0 | DROP_DOWN | → | name | SINGLE_LINE_TEXT |
| ドロップダウン_1 | DROP_DOWN | → | phone | SINGLE_LINE_TEXT |
| リンク | LINK | → | email | LINK |
| ラジオボタン | RADIO_BUTTON | → | is_active | RADIO_BUTTON |
| 文字列__1行_ | SINGLE_LINE_TEXT | → | notes | SINGLE_LINE_TEXT |

#### Clients (167)
| 現在 | タイプ | → | 新コード | 新タイプ |
|---|---|---|---|---|
| ラジオボタン | RADIO_BUTTON | → | client_id | SINGLE_LINE_TEXT |
| ラジオボタン_0 | RADIO_BUTTON | → | name | SINGLE_LINE_TEXT |
| ラジオボタン_1 | RADIO_BUTTON | → | code | SINGLE_LINE_TEXT |
| ラジオボタン_2 | RADIO_BUTTON | → | address | MULTI_LINE_TEXT |
| リンク | LINK | → | billing_email | LINK |
| 文字列__1行_ | SINGLE_LINE_TEXT | → | notes | SINGLE_LINE_TEXT |

#### Sites (166)
| 現在 | タイプ | → | 新コード | 新タイプ |
|---|---|---|---|---|
| ドロップダウン | DROP_DOWN | → | site_id | SINGLE_LINE_TEXT |
| ドロップダウン_0 | DROP_DOWN | → | name | SINGLE_LINE_TEXT |
| ドロップダウン_1 | DROP_DOWN | → | code | SINGLE_LINE_TEXT |
| ドロップダウン_2 | DROP_DOWN | → | address | MULTI_LINE_TEXT |
| 文字列__1行_ | SINGLE_LINE_TEXT | → | notes | SINGLE_LINE_TEXT |

#### Roles (163)
| 現在 | タイプ | → | 新コード | 新タイプ |
|---|---|---|---|---|
| ラジオボタン | RADIO_BUTTON | → | role_id | SINGLE_LINE_TEXT |
| ラジオボタン_0 | RADIO_BUTTON | → | name | SINGLE_LINE_TEXT |
| ラジオボタン_1 | RADIO_BUTTON | → | description | MULTI_LINE_TEXT |

#### Project Types (164)
| 現在 | タイプ | → | 新コード | 新タイプ |
|---|---|---|---|---|
| ラジオボタン | RADIO_BUTTON | → | type_id | SINGLE_LINE_TEXT |
| ラジオボタン_0 | RADIO_BUTTON | → | name | SINGLE_LINE_TEXT |
| ラジオボタン_1 | RADIO_BUTTON | → | description | MULTI_LINE_TEXT |

---

## データ同期の実行

フィールド変更完了後、データを同期します：

```bash
# フィールドマッピングは不要になったので、直接英語フィールドコードで同期
python scripts/sync_db_to_kintone.py all
```

---

## トラブルシューティング

### エラー: 403 "このAPIトークンでは、指定したAPIを実行できません。"

**原因**: APIトークンに「アプリの設定」権限がない

**解決方法**:
1. Kintoneアプリ→設定→APIトークン
2. トークンをクリック
3. 「アプリの設定」にチェック
4. 保存→アプリを更新

### エラー: 400 "不正なリクエストです。"

**原因**: フィールド定義が不正または競合

**解決方法**:
1. Kintoneでアプリを開き、フィールドを手動確認
2. 既に同じコードのフィールドが存在しないか確認
3. エラーメッセージの詳細を確認

### 既存データは消えますか？

**消えません**。フィールドタイプを変更しても、既存データは保持されます。

ただし:
- ドロップダウン→文字列: 選択肢の値がそのまま文字列として保存される
- ラジオボタン→文字列: 選択されていた値が文字列として保存される

---

## 実行例

```bash
$ python scripts/update_kintone_field_types.py 165
============================================================
Kintoneフィールドタイプ・コード一括変更
============================================================
アプリID: 165
アプリ名: workers

[ステップ1] 現在のフィールド定義を取得中...
✅ 取得成功: 14 フィールド

[ステップ2] 変更内容:
  ドロップダウン          (DROP_DOWN     ) → worker_id           (SINGLE_LINE_TEXT)
  ドロップダウン_0        (DROP_DOWN     ) → name               (SINGLE_LINE_TEXT)
  ドロップダウン_1        (DROP_DOWN     ) → phone              (SINGLE_LINE_TEXT)
  リンク                (LINK          ) → email              (LINK          )
  ラジオボタン            (RADIO_BUTTON  ) → is_active          (RADIO_BUTTON  )
  文字列__1行_          (SINGLE_LINE_TEXT) → notes              (SINGLE_LINE_TEXT)

============================================================
⚠️ 警告: フィールドタイプとコードを変更します
============================================================
アプリID: 165 (workers)
変更数: 6 フィールド

実行してよろしいですか？ [y/n]: y

[ステップ3] フィールド設定を更新中（プレビュー）...
✅ プレビュー更新成功

[ステップ4] アプリを公開（プレビュー→本番）...
✅ アプリ公開成功

============================================================
✅ 完了しました
============================================================

変更されたフィールド:
  ドロップダウン          (DROP_DOWN     ) → worker_id           (SINGLE_LINE_TEXT)
  ドロップダウン_0        (DROP_DOWN     ) → name               (SINGLE_LINE_TEXT)
  ドロップダウン_1        (DROP_DOWN     ) → phone              (SINGLE_LINE_TEXT)
  リンク                (LINK          ) → email              (LINK          )
  ラジオボタン            (RADIO_BUTTON  ) → is_active          (RADIO_BUTTON  )
  文字列__1行_          (SINGLE_LINE_TEXT) → notes              (SINGLE_LINE_TEXT)

次のステップ:
1. Kintoneでアプリを開いて確認
2. フィールドマッピングを削除（もう不要）:
   # src/services/kintone_field_mappings.py の 165 セクション
3. データ同期を再実行:
   python scripts/sync_db_to_kintone.py workers
```

---

## まとめ

### 手動作業（約10分）
✅ APIトークンに「アプリの設定」権限を追加（5アプリ）

### 自動実行（約5分）
✅ フィールドタイプ・コード一括変更（5アプリ）
```bash
for app_id in 165 167 166 163 164; do
    python scripts/update_kintone_field_types.py $app_id
done
```

### 完了後
✅ データ同期を実行
```bash
python scripts/sync_db_to_kintone.py all
```

これでKintoneアプリが正しく設定され、データが表示されるようになります。
