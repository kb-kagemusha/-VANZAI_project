# development_rules.md

## 1. 方針
本書は「コードから推測できる現在の開発ルール」を整理したもの。
明文化済みルールと、実装慣習から読み取れる暗黙ルールを分けて扱う。

## 2. 命名規則
### 2.1 バックエンド
- テーブル名: 複数形スネークケース
- 主キー: id (ULID文字列)
- 月次キー: period_key (YYYYMM)
- 状態値: Enumのvalue文字列（lower_snake）

### 2.2 フロント
- コンポーネント: PascalCase
- ページ: XxxPage.tsx
- API型: XxxListItem, XxxResponse, PageResponse

## 3. ディレクトリ規則
- src/models: 永続化モデル
- src/services: 業務ルール
- src/api: エンドポイントとスキーマ
- apps/admin-web/src/pages: 管理画面単位の機能
- apps/staff-mobile/src/pages: スタッフ画面単位の機能

## 4. コンポーネント設計
- 画面は pages に寄せ、共通UIは components に抽出
- DataTable/FilterBarのような枠組みは再利用
- ページごとの業務文言・列定義は pages 側で保持

## 5. 型定義方針
- Pydantic schema をAPI契約の正本にする
- フロント側は types/api.ts にAPI応答型を集約
- enum文字列をそのまま受け渡し、フロントで過剰変換しない

## 6. エラーハンドリング
### 6.1 バックエンド
- ドメイン例外: VANZAIException 系
- HTTP返却: error_code/message/detail のJSON
- 認可失敗: 403

### 6.2 フロント
- ApiErrorで status/detail を保持
- 401を横断イベント化して再ログインへ遷移
- 403は専用画面（/403）へ誘導

## 7. API実装方針
- 依存性注入でDBセッションをリクエスト単位管理
- 一覧APIの応答を可能な範囲で統一（items/total/offset/limit）
- sort/filter/pagination をクエリで受ける
- 表示に必要な関連名はAPI側で解決する

## 8. DBアクセス方針
- SQLAlchemy ORMを中心に利用
- サービス層で業務ルールを適用し、API層に生SQLを散らさない
- 監査ログはサービスの重要操作点で明示記録
- SoftDelete + status + version の複合運用

## 9. 実装時の暗黙ルール（推測）
- 月次業務は period_key 起点で必ずスコープを絞る
- 請求/支払は再生成より版管理を優先する
- 送信系処理は履歴保存まで含めて1機能とする
- 「失敗を隠さない」ため、silent catch を避ける方向に改善されている

## 10. テスト/品質
- バックエンド: pytest中心
- フロント: build + smoke（Playwright）
- 回帰時は対象機能のfocused testを先に実行し、最後に広め回帰

## 11. 移植時に保持すべき規則
- 1. period_key中心の設計
- 2. API契約の共通化
- 3. 権限のサーバー側強制
- 4. 監査ログのイベント記録
- 5. 明細正本・合計派生の会計設計

## 12. 要確認
- lint/formatの厳密ルール（ruff設定の運用範囲）
- commit/PRテンプレートの必須項目（運用ドキュメントとの差分）
