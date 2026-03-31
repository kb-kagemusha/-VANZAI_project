# テスト送信時の確認チェックリスト（1回検収用）

更新日: 2026-02-13
対象:
- ① 振込情報登録【個人】 -> App312
- ② 振込情報登録【法人】 -> App311
- ③ 身分証情報登録【個人】 -> App312

---

## 0. 事前準備（5分）
- [ ] App311 / App312 のアプリ更新が完了している
- [ ] App312 に `app312_approval.js` が適用済み
- [ ] App174 に `front_dashboard.js` が適用済み（任意）
- [ ] テスト用の一意なメールアドレスを用意（例: test+yyyymmddhhmm@...）

---

## 1. 送信テスト（3フォーム）
### A. 個人フォーム①（振込情報）
- [ ] フォーム送信を実施
- [ ] App312 に新規レコードが1件作成される

### B. 法人フォーム②（法人用）
- [ ] フォーム送信を実施
- [ ] App311 に新規レコードが1件作成される

### C. 個人フォーム③（身分証）
- [ ] フォーム送信を実施
- [ ] App312 の対象レコードへ身分証情報が反映（新規 or 更新）される

---

## 2. 項目マッピング確認（個人: App312）
以下を1レコードで照合。左=フォーム項目、右=App312フィールドコード

- [ ] 有効・無効 -> `is_active`（初期は無効）
- [ ] 稼働者ID -> `worker_id`（承諾までは空または既存値でも可）
- [ ] 氏名(姓) -> `last_name`
- [ ] 氏名(名) -> `first_name`
- [ ] 姓(フリガナ) -> `lastname_furigana`
- [ ] 名(フリガナ) -> `firstname_furigana`
- [ ] 個人事業主屋号 -> `bussiness_name`
- [ ] 性別 -> `sex`
- [ ] 経由先 -> `group`
- [ ] 紹介者/下請け -> `introducer_supplier`
- [ ] メールアドレス -> `email`
- [ ] 郵便番号 -> `zipcode`
- [ ] 都道府県 -> `pref`
- [ ] 市区町村以下 -> `city_etc`
- [ ] 建物名･部屋番号 -> `name_of_building`
- [ ] 携帯電話番号 -> `phone`
- [ ] 緊急連絡先氏名(カナ) -> `emergency_contact_name`
- [ ] 緊急連絡先 -> `emergency_contact_phone`
- [ ] 振込口座(銀行名) -> `bank_name`
- [ ] 振込口座(支店名) -> `bank_branch`
- [ ] 振込口座(支店番号) -> `bank_branch_number`
- [ ] 振込口座(口座種別) -> `bank_account_type`
- [ ] 振込口座(口座番号7桁) -> `bank_account_number`
- [ ] 振込口座(名義) -> `bank_account_holder`
- [ ] 備考 -> `memos`
- [ ] 身分証提出 -> `id_document`
- [ ] 適格請求書発行事業者の登録番号_取得有無 -> `invoice_registration_status`
- [ ] 適格請求書発行事業者の登録番号（T+13桁） -> `invoice_registration_number`
- [ ] 住所（都道府県～市区町村） -> `address_line1`
- [ ] 住所（建物名・部屋番号） -> `address_line2`

---

## 3. 項目マッピング確認（法人: App311）
- [ ] 会社名 -> `company_name`
- [ ] 会社名（フリガナ） -> `company_name_furigana`
- [ ] 代表者名（漢字） -> `representative_name`
- [ ] 代表者名（フリガナ） -> `representative_name_furigana`
- [ ] メールアドレス -> `email`
- [ ] 電話番号 -> `phone`
- [ ] 郵便番号 -> `zipcode`
- [ ] 都道府県 -> `pref`
- [ ] 市区町村以下 -> `city_etc`
- [ ] 建物名・部屋番号 -> `name_of_building`
- [ ] 振込口座(銀行名) -> `bank_name`
- [ ] 振込口座(支店名) -> `bank_branch`
- [ ] 振込口座(支店番号) -> `bank_branch_number`
- [ ] 振込口座(口座種別) -> `bank_account_type`
- [ ] 振込口座(口座番号7桁) -> `bank_account_number`
- [ ] 振込口座(カタカナ) -> `bank_account_holder_kana`
- [ ] インボイス登録有無 -> `invoice_registration_status`
- [ ] インボイス番号 -> `invoice_registration_number`
- [ ] 住所（都道府県～市区町村） -> `address_line1`
- [ ] 住所（建物名・部屋番号） -> `address_line2`
- [ ] 有効・無効 -> `is_active`
- [ ] 備考 -> `memos`

---

## 4. 承諾フロー検収（App312）
- [ ] App312で対象レコードを開く
- [ ] プロセス操作「承諾」を実行
- [ ] 経由先入力ダイアログが出る
- [ ] 経由先=VANZAI の場合、紹介者/下請けを空欄でも承諾できる
- [ ] 経由先がVANZAI以外の場合、紹介者/下請けが必須になる
- [ ] 承諾後 `is_active=有効` になる
- [ ] 承諾後 `worker_id` が `WRK`+4桁で採番される

---

## 5. データ品質チェック（App312）
- [ ] `worker_id` の重複がない（同一ID 1件）
- [ ] 必須項目（姓・名・電話）の欠損がない
- [ ] 口座種別が選択肢外になっていない
- [ ] 改行入り項目が単一行として保持されている

---

## 6. 検収合格条件（1回でOKとする条件）
- [ ] 3フォームともKintone反映を確認
- [ ] App312/311の主要マッピング項目が一致
- [ ] App312の承諾フロー（必須条件・採番・有効化）が期待どおり
- [ ] App312の重複レコードなし
