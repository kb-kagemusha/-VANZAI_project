# user_mypage_pattern.md

## 1. 目的
本書は、このプロジェクトで確立された「マイページ設計パターン」を抽出し、別案件へ同品質で移植するための再利用ガイドである。

対象は主に staff-mobile（worker向け）だが、admin-web の運用画面パターンも併せて参照する。

## 2. 画面構成パターン
### 2.1 ルート構成
- login
- today（当日アサイン）
- schedule（予定確認）
- availability（稼働可否）
- settings（個人設定）
- actuals（実績確認）
- expenses（経費申請/確認）
- notices（通知）

### 2.2 ガード構成
- ProtectedRoute: 未認証を login へリダイレクト
- WorkerOnlyRoute: role != worker を 403 へリダイレクト

設計意図:
- 「認証」と「業務ロール制約」を分離し、責務を単純化する

## 3. データ取得方法
### 3.1 APIクライアント統一
- 各アプリごとに lib/api/client.ts を持つ
- apiFetch で共通化する要素
  - Authorizationヘッダ
  - JSON/Multipart切替
  - 401時の強制サインアウトイベント

### 3.2 状態管理
- サーバー状態: TanStack Query
- 認証状態: auth-context
- UI局所状態: useState

### 3.3 月次画面の取得規約
- month入力 -> period_key変換 -> APIクエリ
- 範囲計算はユーティリティ関数で統一（固定日付を埋め込まない）

## 4. 権限制御
- サーバー側が最終判定（Permission）
- フロントは補助的にガードを実施
- 重要設計:
  - UIで見えてもAPIで拒否される構造を許容する
  - UI側は403のフォールバック画面を必ず持つ

## 5. 一覧画面パターン
### 5.1 構成テンプレート
- PageHeader
- FilterBar
- DataTable（またはモバイルカード列）
- Pagination
- EmptyState/ErrorState

### 5.2 意図
- 一覧画面の心理モデルを揃え、教育コストを下げる
- 条件変更時はページを先頭に戻す
- エラー時は「業務で次に何を確認すべきか」を文言に含める

## 6. 詳細画面パターン
- staff-mobile はドロワー/カード展開型を採用
- 読み取り中心 + 必要最小限のアクションボタン
- 履歴情報（既読、応答、送信結果）を同画面で確認可能にする

## 7. 編集画面パターン
- 編集系は optimistic update を多用せず、成功後に query invalidate
- 理由入力必須の操作（却下、取消、復帰など）はUIで先に必須化
- 送信系は「対象・宛先・理由」の3点を明示

## 8. 共通コンポーネント
- AppShell / MobileShell
- DataTable
- FilterBar
- StatusBadge
- LoadingOverlay
- ErrorState / EmptyState
- PageHeader

再利用の勘所:
- 汎用コンポーネントは業務語彙を持ちすぎない
- 業務語彙はページ層で与える

## 9. 再利用可能な設計
- 1. route guard の二段構成（認証 + ロール）
- 2. app別APIクライアント分離（adminとworkerで責務分離）
- 3. month/period_key中心の一覧設計
- 4. 送信・返答フローの履歴一体型UI
- 5. 401イベント起点での横断ログアウト

## 10. 別プロジェクトへ移植する手順
1. 役割モデルを先に確定する（例: admin/ops/worker）
2. auth-context と api client の雛形を作る
3. ProtectedRoute + RoleRoute を実装する
4. 一覧テンプレート（header/filter/table/pager）を共通部品化する
5. 月次キー（period_key）の規約を決め、日付処理をユーティリティへ集約する
6. 送信系画面は履歴テーブルを同時に実装する
7. 403/401/ネットワーク失敗時の表示基準を先に決める
8. 最後に通知・プッシュなど周辺機能を追加する

## 11. 品質を揃えるためのチェックリスト
- ロール外ユーザーが画面に入れない
- API 401時に確実にログインへ戻る
- 月次フィルタが全月で正しく動作する
- 失敗時メッセージが運用者にとって具体的
- 履歴が残る操作は履歴UIで追跡可能

## 12. 要確認
- マイページで扱う個人情報項目の最小化方針（他案件の法務要件差分）
- push通知のブラウザ差分対応（iOS制約含む）の必須レベル
