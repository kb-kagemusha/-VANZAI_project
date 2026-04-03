# 実装状況（STATUS）

最終更新: 2026-04-03

---

## ブラウザキャッシュ問題 — 三段対応計画

### 追記（2026-04-03）

- nginx 修正を適用済み
  - `index.html`: `Cache-Control: no-cache, no-store, must-revalidate`
  - `sw.js`: `Cache-Control: no-cache, no-store, must-revalidate`
- フロントの版番号表示を semantic version に統一
  - 表示: `Ver.0.6.3`
  - 更新検知: `buildId` ベースで `/version.json` を比較
- スタッフ画面はヘッダー左上に `STAFF MOBILE Ver.0.6.3` を表示
- 通知拒否時は個人設定ページにブラウザ別の解除手順を表示
- プッシュ通知の設定・障害切り分け Runbook を追加
  - [PUSH_NOTIFICATION_RUNBOOK.md](./PUSH_NOTIFICATION_RUNBOOK.md)

**現象：** デプロイ後もユーザーが旧 JS をブラウザキャッシュ（1年 immutable）から実行し、  
新しい修正が当たらない。nginx が `index.html` に `Cache-Control` を付けていないため  
heuristic caching が発動する。

---

### フェーズ1：今すぐの応急処置（コード変更不要・即実施可能）

**ユーザーへの案内（Android Chrome）**

> `https://staff.vanzai-portal.com/?v=20260403-01` をブラウザで開いてください。  
> `?v=...` が付くと別キャッシュキーになり、古い `index.html` を踏まずに済みます。

または Chrome で「シークレットモード」→ `https://staff.vanzai-portal.com`

---

### フェーズ2：次回以降のデプロイから（実装済み・次回 git push + デプロイで有効）

**実装内容：**

| ファイル | 変更内容 |
|---|---|
| [tools/vite-plugin-version-check.ts](../../tools/vite-plugin-version-check.ts) | 新規作成。ビルドハッシュを埋め込み、起動時に `/version.json` と突合する |
| [apps/staff-mobile/vite.config.ts](../../apps/staff-mobile/vite.config.ts) | `versionCheckPlugin()` 追加 |
| [apps/admin-web/vite.config.ts](../../apps/admin-web/vite.config.ts) | `versionCheckPlugin()` 追加 |
| [scripts/deploy/02_app_deploy.sh](../../scripts/deploy/02_app_deploy.sh) | 旧 JS/CSS を 7日間保持する `build_with_asset_retention()` 関数 |

**動作フロー：**

```
ビルド時
  → dist/version.json  生成 ({"version":"1743xxx-a1b2c3d","buildTime":"..."})
  → index.html に <script> インライン埋め込み
       CURRENT = "1743xxx-a1b2c3d"
       fetch("/version.json?_t=...", {cache:"no-store"})
       → 不一致なら location.replace("/?_v=1743yyy-e4f5g6h")
       → 別URL = ブラウザが新 index.html をサーバーから取得してキャッシュ

ユーザー救済の時系列
  初回デプロイ後: このプラグイン入り index.html をまだ持っていないユーザー → フェーズ1で案内
  2回目以降:      version.json 不一致を自動検知 → 自動リダイレクト → 即時反映 ✅
```

**旧アセット保持（deploy スクリプト）：**

- ビルド前に `dist/assets/*.{js,css}` を `/var/www/vanzai/.asset-archive/<app>/` に退避
- ビルド後に退避ファイルを `dist/assets/` に復元（`cp -n`：新ファイル優先）
- 7日超えたアーカイブは自動削除
- 効果：古い `index.html` を持つユーザーが旧 JS を参照しても 404 にならない

---

### フェーズ3：root 取得後の本来解（nginx 最小変更・1回限り）

```nginx
# /etc/nginx/sites-available/vanzai の
# admin-web / staff-mobile 両 server ブロック内に追加

    location = /index.html {
        add_header Cache-Control "no-cache";
    }
```

適用コマンド（root で1回実行）：

```bash
# 追加箇所の確認
sudo grep -n "location = /index.html" /etc/nginx/sites-available/vanzai

# まだなければ sedで挿入（全 server ブロックの "location / {" 直前に追加）
sudo sed -i 's|^\(    location / {\)$|    location = /index.html {\n        add_header Cache-Control "no-cache";\n    }\n\n\1|' /etc/nginx/sites-available/vanzai

sudo nginx -t && sudo systemctl reload nginx
```

適用後の役割分担：

| 対象 | Cache-Control | 意味 |
|---|---|---|
| `index.html` | `no-cache` | 毎回バリデーション（ETag一致なら 304、差分なければ転送なし） |
| `*.js` `*.css`（ハッシュ付き） | `public, immutable` (1年) | 変更不要なら永久キャッシュ ✅ |

---



## 🗺️ 全機能早見表（2026-04-02 時点）

### バックエンド API（FastAPI / Python 3.12）

| カテゴリ | エンドポイント | 概要 |
|---|---|---|
| 認証 | `POST /api/auth/token` | ログイン（JWT発行） |
| 認証 | `GET /api/auth/me` | 自分のユーザー情報 |
| ダッシュボード | `GET /api/dashboard` | 未処理件数・アラート・pending応答監視 |
| 実績 | `GET /api/actuals` | 実績一覧（CSV import結果） |
| アサイン | `GET/POST /api/assignments` | アサイン一覧・新規作成 |
| アサイン | `PUT /api/assignments/{id}` | 編集（枠・スタッフ・役割・ロック単価） |
| アサイン | `POST /api/assignments/{id}/status` | 状態変更（tentative/confirmed/canceled） |
| アサイン | `POST /api/assignments/{id}/worker-response` | スタッフ予定返信（参加可/辞退） |
| アサイン | `POST /api/assignments/reminders/send` | 予定確認メール手動再送 |
| アサイン | `POST /api/assignments/reminders/escalate` | 要エスカレーション通知 |
| アサイン | `POST /api/assignments/reminders/history` | 催促履歴取得 |
| アサイン | `POST /api/assignments/reminders/escalations/history` | エスカレーション履歴取得 |
| 選択セット | `GET/POST/DELETE /api/assignment-selection-sets` | 一括状態更新用の選択セット保存・共有 |
| 打刻 | `POST /api/assignments/{id}/check-in` | 出勤打刻（スタッフ用） |
| 打刻 | `POST /api/assignments/{id}/check-out` | 退勤打刻（スタッフ用） |
| 稼働可否 | `GET/POST /api/worker-availability` | 日別稼働可否登録（スタッフ用） |
| 稼働設定 | `GET/PUT /api/worker-availability/preferences` | 曜日デフォルト可否設定（スタッフ用） |
| 経費 | `GET /api/expenses` | 経費一覧 |
| 経費 | `POST /api/expenses` | 経費申請（multipart、領収書添付可） |
| 経費 | `POST /api/expenses/{id}/approve` | 経費承認 |
| 経費 | `POST /api/expenses/{id}/reject` | 経費却下 |
| 経費 | `GET /api/expenses/{id}/receipt` | 領収書ダウンロード |
| 案件 | `GET/POST /api/projects` | 案件一覧・新規作成 |
| 案件 | `PUT /api/projects/{id}` | 案件更新 |
| シフト枠 | `GET/POST /api/shift-slots` | シフト枠一覧・新規作成 |
| シフト枠 | `PUT /api/shift-slots/{id}` | シフト枠更新 |
| CSV取込 | `POST /api/csv-import` | CSV取込（洗い替えモード対応） |
| 取込履歴 | `GET /api/import-batches` | 取込バッチ履歴一覧 |
| 請求書 | `GET/POST /api/invoices` | 請求書一覧・生成 |
| 請求書 | `POST /api/invoices/{id}/issue` | 請求書発行 |
| 請求書 | `GET /api/invoices/{id}/pdf` | 請求書PDFダウンロード |
| 支払明細 | `GET/POST /api/payouts` | 支払明細一覧・生成 |
| 支払明細 | `POST /api/payouts/{id}/approve` | 支払確定 |
| 支払明細 | `POST /api/payouts/{id}/mark-paid` | 支払済み更新 |
| 支払明細 | `GET /api/payouts/{id}/pdf` | 支払明細PDFダウンロード |
| 支払明細 | `POST /api/payouts/{id}/deliver` | 支払明細メール送信 |
| 送信履歴 | `GET /api/payout-deliveries` | 送信履歴一覧 |
| 締め | `POST /api/closings/soft` | 仮締め |
| 締め | `POST /api/closings/hard` | 本締め（二者承認） |
| 締め解除 | `POST /api/closings/{id}/release` | 締め解除（回数上限・ガードレール付き） |
| マスタ | `GET/POST /api/workers` | 稼働者一覧・新規登録 |
| マスタ | `PUT /api/workers/{id}` | 稼働者更新 |
| マスタ | `GET/POST /api/clients` | 取引先一覧・新規登録 |
| マスタ | `GET/POST /api/sites` | 現場一覧・新規登録 |
| マスタ | `GET/POST /api/project-types` | 案件種別一覧・新規登録 |
| マスタ | `GET/POST /api/roles` | 役割一覧・新規登録 |
| マスタ | `GET/POST /api/suppliers` | 下請け一覧・新規登録 |
| マスタ | `PUT /api/suppliers/{id}` | 下請け更新 |
| 単価 | `GET/POST /api/price-rules` | 単価ルール一覧・登録 |
| 単価 | `PUT /api/price-rules/{id}` | 単価ルール更新 |
| 単価 | `GET/POST /api/price-sales` | 売上単価一覧・登録 |
| 単価 | `PUT /api/price-sales/{id}` | 売上単価更新 |
| 単価 | `GET/POST /api/price-outsource` | 外注単価一覧・登録 |
| 単価 | `PUT /api/price-outsource/{id}` | 外注単価更新 |
| 監査ログ | `GET /api/audit-logs` | 監査ログ一覧（全変更履歴） |
| ヘルス | `GET /api/health` | サービス稼働状態確認 |

### フロントエンド

| アプリ | 画面 | 概要 |
|---|---|---|
| admin-web | ログイン | JWT認証ログイン |
| admin-web | ダッシュボード | 未処理アラート・締め状況・pending応答監視 |
| admin-web | 実績一覧 | CSV取込結果の実績参照 |
| admin-web | アサイン一覧 | アサイン管理・状態変更・一括操作・選択セット保存 |
| admin-web | 案件一覧 | 案件登録・編集 |
| admin-web | シフト枠一覧 | シフト枠作成・編集 |
| admin-web | 経費一覧 | 経費承認・却下・領収書確認 |
| admin-web | 請求一覧 | 請求書生成・発行・PDFダウンロード |
| admin-web | 支払一覧 | 支払明細生成・確定・送信・PDFダウンロード |
| admin-web | CSV取込 | CSVアップロード・洗い替え・履歴・差戻し文面作成 |
| admin-web | マスタ管理 | 稼働者・取引先・現場・役割・下請け・単価 登録・編集 |
| admin-web | 予定確認監視 | pending返信の監視・手動再送・エスカレーション通知 |
| admin-web | 稼働者管理 | 稼働者一覧・曜日デフォルト稼働可否設定表示 |
| admin-web | 監査ログ | 全操作変更履歴の参照 |
| staff-mobile | ログイン | JWT認証ログイン（worker専用） |
| staff-mobile | 当日ページ | 今日のアサイン確認・出勤/退勤打刻 |
| staff-mobile | 予定確認 | 月次予定一覧・参加可/辞退返信 |
| staff-mobile | 稼働可否登録 | 日別稼働可否の事前入力（4択） |
| staff-mobile | 個人設定 | 曜日デフォルト稼働可否の設定 |
| staff-mobile | 経費申請 | 経費申請（領収書添付）・今月の申請一覧 |
| staff-mobile | 実績確認 | 今月の実績一覧 |

### データベース（PostgreSQL 16）

| テーブル種別 | テーブル名 |
|---|---|
| マスタ | `workers`, `clients`, `sites`, `project_types`, `roles`, `suppliers` |
| マスタ | `price_sales`, `price_outsource`, `price_rules`, `incentive_rules` |
| 認証 | `users` |
| トランザクション | `projects`, `shift_slots`, `assignments`, `actuals` |
| トランザクション | `expenses`, `incentives` |
| トランザクション | `import_batches` |
| トランザクション | `invoices`, `invoice_lines` |
| トランザクション | `payouts`, `payout_lines`, `payout_deliveries` |
| トランザクション | `closings` |
| トランザクション | `assignment_selection_sets` |
| トランザクション | `worker_availability`, `worker_availability_preferences` |
| 監査 | `audit_logs` |

### 採用技術スタック

| レイヤー | 採用技術 |
|---|---|
| Backend | FastAPI 0.115, Python 3.12, SQLAlchemy 2, Alembic |
| Frontend | React 18, TypeScript, Vite 6.4, TanStack Query |
| DB | PostgreSQL 16 |
| Auth | JWT（python-jose）|
| PDF | ReportLab（日本語フォント: ipaexg.ttf）|
| Email | aiosmtplib + Jinja2テンプレート |
| Storage | ローカル `storage/` ディレクトリ（Cloudflare R2 切替対応の抽象層あり）|
| Infra | Xserver VPS（Ubuntu）, nginx, systemd |
| CI/Test | pytest 302件、Playwright E2E smoke |
| Kintone連携 | Kintone REST API（マスタ同期スクリプト群）|

---

## 🔑 本番環境アクセス情報

| 項目 | 値 |
|---|---|
| VPS IP | `220.158.28.35` |
| SSH | `ssh -i $HOME/.ssh/vanzai_vps vanzai@220.158.28.35` |
| admin-web | `https://vanzai-portal.com` |
| staff-mobile | `https://staff.vanzai-portal.com` |
| API | `https://api.vanzai-portal.com` |
| API ヘルス | `https://api.vanzai-portal.com/api/health` |
| app dir（VPS） | `/var/www/vanzai` |
| .env（VPS） | `/var/www/vanzai/.env` |
| systemd unit | `vanzai-api.service`（`Restart=always`）|
| APIプロセス管理 | `pkill -f 'uvicorn.*src.api.main:app'` → systemdが自動再起動 |

---

## 📋 デプロイ手順（更新時）

### Windows（ローカル PC）で実行

```powershell
# 1. 変更をコミット・プッシュ
cd c:/VANZAI_project
git add -A
git commit -m "feat: ..."
git push origin feature/2026-03-31-next-work
```

### VPS へ反映（Windows PowerShell から SSH で一括実行）

```powershell
# 2. git pull + pip + Alembic migrate + npm build（02_app_deploy.sh が全部やる）
ssh -i "$env:USERPROFILE\.ssh\vanzai_vps" vanzai@220.158.28.35 `
  "cd /var/www/vanzai && git fetch origin && git checkout feature/2026-03-31-next-work && git pull origin feature/2026-03-31-next-work && bash scripts/deploy/02_app_deploy.sh"
```

> **注意**: フロントビルドは `02_app_deploy.sh` に含まれていないことがある。  
> 含まれていない場合は以下を追加実行：
> ```powershell
> ssh -i "$env:USERPROFILE\.ssh\vanzai_vps" vanzai@220.158.28.35 `
>   "cd /var/www/vanzai && VITE_API_BASE_URL=https://api.vanzai-portal.com npm --prefix apps/admin-web run build && VITE_API_BASE_URL=https://api.vanzai-portal.com npm --prefix apps/staff-mobile run build"
> ```

```powershell
# 3. API プロセス再起動（旧プロセスを kill → systemd が Restart=always で自動再起動）
ssh -i "$env:USERPROFILE\.ssh\vanzai_vps" vanzai@220.158.28.35 `
  "pkill -f 'uvicorn.*src.api.main:app' || true"

# 4. ヘルス確認
curl https://api.vanzai-portal.com/api/health
```

### Alembic マイグレーションだけ手動で当てたい場合

```powershell
ssh -i "$env:USERPROFILE\.ssh\vanzai_vps" vanzai@220.158.28.35 `
  "cd /var/www/vanzai && .venv/bin/python -m alembic upgrade head"
```

> **SQLite 固有の注意**:
> - `ALTER TABLE ADD CONSTRAINT` は非対応。`UniqueConstraint` は `create_table` 内に書くこと
> - マイグレーションが途中で失敗してテーブルが中途半端に作られた場合は `alembic stamp <revision>` でバージョンを合わせてから再実行

### SSH 接続情報（テスト環境）

| 項目 | 値 |
|---|---|
| 秘密鍵（Windows） | `%USERPROFILE%\.ssh\vanzai_vps` |
| 接続コマンド | `ssh -i "$env:USERPROFILE\.ssh\vanzai_vps" vanzai@220.158.28.35` |
| VPS パスワード | `Mykey0304@kb333`（sudo 不可ユーザー。現状 systemd 操作は root 権限が必要） |
| systemd 再起動 | vanzai ユーザーは sudo 不可のため `pkill` で旧プロセスを落とし systemd 自動再起動を利用する |

> ⚠️ 本番運用時はパスワード認証を廃止し、公開鍵のみに切り替えること

---

## 📅 デプロイ履歴

| 日付 | 内容 | コミット |
|---|---|---|
| 2026-04-03 | 管理者→スタッフ通知機能（StaffNotice）実装・本番デプロイ | `60b2e92` |
| 2026-04-02 | worker availability preferences 実装・本番デプロイ | `cd2dde4` |
| 2026-04-02 | CORS設定追加・両アプリ再ビルド・本番ログイン確認 | — |
| 2026-04-01 | Phase5 staff-mobile 完成・admin-web 予定確認監視実装 | `5f8352f` |
| 2026-03-31 | セキュリティ強化（JWT必須化・CORS修正） | `8607eb1` |
| 2026-01-27 | Sprint 4 完了（126 tests passing） | — |
| 2026-01-27 | Sprint 3 完了（権限管理・再計算・経費） | — |
| 2026-01-27 | 本番VPS初期構築（nginx / systemd / PostgreSQL） | — |

---

### 2026-04-02 本番デプロイ要約
- 完了: Xserver VPS (220.158.28.35) に本番環境を構築し、nginx / systemd / PostgreSQL を設定
- 完了: `vanzai-portal.com`、`www.vanzai-portal.com`、`api.vanzai-portal.com`、`staff.vanzai-portal.com` のHTTPS化
- 完了: admin-web / staff-mobile の production build 配置、API の常駐化、`/api/health` で healthy 応答を確認
- 完了: `pyproject.toml` に認証依存関係を追加し、`scripts/deploy/02_app_deploy.sh` を現在ブランチ追従へ修正
- 注意: NordVPN 有効時は DNS 解決が不安定だったため、Windows 側 hosts に4ドメインを固定して回避した

---

## React 管理画面の進捗

### Phase 1: 参照系
- 完了: ログイン、ダッシュボード、実績一覧、アサイン一覧、案件一覧、シフト枠一覧、経費一覧、請求一覧、支払一覧、監査ログ一覧
- 完了: 単価一覧、マスタ一覧
- 完了: 権限制御（nav 非表示 + ルートガード）

### Phase 2: 月次運用
- 完了: CSV取込画面
  - 案件選択、対象月、取込モード、洗い替え範囲、結果表示、取込履歴、差戻し文面作成
- 完了: 請求生成 UI
  - 請求書生成、請求書発行、請求書PDFダウンロード
- 完了: 支払生成 UI
  - 支払明細生成、支払確定、支払済み更新、支払明細PDFダウンロード、支払明細メール送信
  - 支払一覧で最終送信ステータス、送信日時、送信先メールアドレスを参照可能
- 完了: 締め・締め解除 UI
  - ダッシュボードの締め状況セクションで仮締め、本締め、解除、監査ログ導線を実装
- 完了: 差戻し支援 UI
  - 取込履歴からエラー概要を差戻し文面へ整形し、コピーできる
- 一部実装: PDFの保存先管理 UI
  - 請求一覧と支払一覧で保存済み PDF の storage key を参照可能
  - 請求発行時と支払確定時に PDF を storage/pdfs 配下へ保存し、ダウンロード時は保存済みファイルを優先して返す
  - Cloudflare R2 への本保存切替は未実装で、現状はローカル保存を暫定運用とする
- 一部実装: 支払明細送信履歴管理
  - API では送信履歴を payout_deliveries に保存し、監査ログへ送信成功/失敗を記録する
  - 管理画面では支払一覧に最終送信結果を表示し、各支払から送信履歴パネルを開いて再送状況を確認できる
  - 履歴パネルから宛先メールアドレスを上書きして再送でき、空欄なら既定宛先を使用する
  - 履歴パネルには既定送信先を明示し、未設定時は送信前に不足が分かる
  - 履歴パネルには既定送信先と過去送信先から組み立てた送信候補を表示し、候補クリックで宛先入力へ反映できる
  - 支払一覧では既定送信先未設定の支払だけを抽出でき、一覧上でも未設定警告を表示する
  - 支払一覧では未送信のみ、送信失敗のみの絞り込みができ、再送が必要な明細を先に洗い出せる
  - 送信履歴には送信理由メモと内部メモを保持し、再送判断の文脈を追跡できる
  - ダッシュボードと支払一覧上部サマリーで、既定送信先未設定の支払件数を確認できる
  - 監査ログ一覧の概要欄でも、支払明細送信の宛先・送信理由メモ・内部メモを確認できる

### ローカル検証メモ
- 管理画面のブラウザスモークは Playwright で再実行できる
- 事前に `alembic upgrade head` でローカル DB を最新スキーマへ上げる
- API は `c:/VANZAI_project/.venv/Scripts/python.exe -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000` で起動する
- admin-web は `Set-Location apps/admin-web; npm run dev -- --host 127.0.0.1 --port 3000` で起動する
- スモークは `Set-Location apps/admin-web; $env:ADMIN_WEB_SMOKE_USERNAME='確認管理者'; $env:ADMIN_WEB_SMOKE_PASSWORD='SmokeTest123!'; $env:ADMIN_WEB_SMOKE_MONTH='2026-01'; $env:ADMIN_WEB_BASE_URL='http://127.0.0.1:3000'; npm run smoke:e2e` で実行する
- `apps/admin-web/e2e/phase1-smoke.spec.ts` は実行前に `scripts/ensure_local_admin.py` と `scripts/ensure_browser_smoke_data.py` を呼び、最低限のログインユーザーと確認用データをローカル DB に投入する
- 2026-04-01 時点で、支払送信先未設定サマリーと支払送信監査ログ要約を含むブラウザスモークは成功している

### Phase 3: マスタ管理
- 着手: 基本マスタの新規登録 UI
  - マスタ一覧画面でクライアント、現場、案件種別、役割の新規登録が可能
  - 新規登録は MASTER_WRITE 権限に合わせて admin のみ表示・実行可能
  - API では `/api/clients`、`/api/sites`、`/api/project-types`、`/api/roles` の POST を追加し、作成時に監査ログを記録する
- 進展: 稼働者・下請けの登録 / 編集 UI
  - マスタ一覧画面で稼働者、下請けの新規登録と既存行の編集が可能
  - API では `/api/workers`、`/api/workers/{id}`、`/api/suppliers`、`/api/suppliers/{id}` を追加し、更新時も監査ログを記録する
- 進展: 単価管理の編集 UI
  - 単価一覧画面で売上単価、外注単価、単価ルールの新規登録と既存行の編集が可能
  - API では `/api/price-rules`、`/api/price-rules/{id}`、`/api/price-sales`、`/api/price-sales/{id}`、`/api/price-outsource`、`/api/price-outsource/{id}` を追加し、PRICE_WRITE 権限で保護する
- 完了: Phase 3 ブラウザスモーク拡張
  - Playwright で下請け、単価ルール、売上単価、外注単価の作成 / 更新を自動確認できる
  - 既存ローカル DB でも作成系 API が通るよう、`TimestampMixin` に Python 側の created_at / updated_at default を追加した
- 完了: Phase 4 ブラウザスモーク拡張
  - Playwright で案件、シフト枠の作成 / 更新を自動確認できる
  - locator は card / row / label 単位にスコープし、`案件` と `ソート` のような部分一致衝突を回避した

### Phase 4: 案件・シフト運用
- 完了: 案件登録 / 編集 UI
  - 案件一覧画面から案件の新規作成と既存案件の主要項目更新が可能
  - API では `/api/projects` と `/api/projects/{id}` を利用し、取引先・現場・担当・期間・notes・稼働状態を一括更新できる
- 完了: シフト枠作成 / 編集 UI
  - シフト枠一覧画面から案件・日付・時間帯・シフトラベル・必要人数・notes を登録 / 更新可能
  - API では `/api/shift-slots` と `/api/shift-slots/{id}` を利用し、アサイン済み枠の案件変更禁止と必要人数下限制約をガードする
- 完了: アサイン作成 / 状態変更 UI
  - アサイン一覧画面からシフト枠・スタッフ・役割・ステータスを指定して新規登録が可能
  - confirmed / tentative / canceled への状態変更と、取消時の理由入力を実装
  - 実績が有効なアサインは canceled へ変更できないよう API でガード
- 完了: アサイン編集 UI
  - アサイン一覧画面からシフト枠・スタッフ・役割・ロック単価の更新が可能
  - active な実績が残るアサインは、枠・スタッフ・役割の差し替えを API でブロック
- 完了: 予定 / 確定の状態管理 UI
  - アサイン単位の tentative / confirmed / canceled 更新は可能
  - 一覧画面でページ・ステータス切替をまたいで選択を保持しつつ、一括 tentative / confirmed / canceled 更新が可能
  - 対象月ごとに保存済み選択セットをサーバー保存し、再読み込みできる
  - 個人用セットは ASSIGNMENT_READ 権限で保存でき、共有セットは admin / ops が保存可能
  - 一括更新は all-or-nothing で、1件でも取消不可条件に当たると全件を更新しない
  - 選択セットの削除は作成者または admin のみ可能
- 完了: 取消理由管理 UI
  - canceled 更新時の理由入力は可能
  - 状態変更パネルで対象アサインの監査ログを参照でき、取消・状態変更の履歴を確認可能
  - canceled 行には再開導線を表示し、tentative / confirmed への復帰操作が可能
  - 対象月の取消履歴専用一覧を表示し、現在も canceled のアサインは一覧から再開可能
  - canceled から tentative / confirmed へ復帰する際は復帰理由が必須
  - 復帰理由は監査ログに記録され、取消履歴一覧でも復帰日時・実行者・理由を参照可能
  - 単件復帰と一括状態更新の両方で復帰理由入力に対応
  - admin-web の phase1 smoke にアサイン運用フローを追加し、編集・取消・復帰・選択セット保存/再読込/削除・一括状態更新を通しで検証済み
- 完了: 運用メモ管理 UI
  - 案件一覧とシフト枠一覧の編集カードから、notes を他項目と一緒に更新できる
  - Focused pytest 13件と admin-web build で Phase 4 の追加 PUT フローを検証済み

### Phase 5: スタッフ向けモバイル
- 完了: `apps/staff-mobile` 初期実装
  - worker ロール専用のログイン、当日アサイン確認、今月の実績確認を React + Vite で追加
  - 既存 API の `/api/auth/me`、`/api/assignments`、`/api/actuals` をそのまま利用し、worker スコープで read-only 導線を切り出した
  - `apps/staff-mobile` の production build を通し、次段の出勤 / 退勤、稼働可否、経費申請の土台を用意した
- 完了: 出勤 / 退勤、経費申請
  - worker ロールに自分スコープの `actual_write`、`expense_read`、`expense_submit` を追加し、勤怠打刻と経費一覧 / 申請を許可した
  - `POST /api/assignments/{id}/check-in` と `POST /api/assignments/{id}/check-out` を追加し、assignment 起点で actual を作成 / 更新する mobile 打刻導線を追加した
  - `POST /api/expenses` を multipart 対応で追加し、領収書はローカル `storage/receipts` 配下へ object key 形式で保存する
  - `apps/staff-mobile` に今日の打刻 UI と経費申請 / 今月の申請一覧を追加し、focused pytest 8件と staff-mobile build で検証済み
- 完了: 予定確認、稼働可否、expense 承認導線
  - `worker_availability` テーブルと `GET/POST /api/worker-availability` を追加し、worker ロールに `availability_read` / `availability_write` を付与した
  - `apps/staff-mobile` に月次予定確認画面、日別の事前予定入力画面、経費一覧からの領収書参照導線を追加した
  - 2026-04-01 に事前予定の選択肢を `稼働OK（1日）` / `稼働OK（15時〜）` / `稼働不可` / `稼働はできなくはないので事前相談して` の4択へ更新し、旧 `available` は `available_all_day` に互換マッピング、旧 `undecided` は未登録表示で扱うようにした
  - `POST /api/expenses/{id}/approve`、`POST /api/expenses/{id}/reject`、`GET /api/expenses/{id}/receipt` を追加し、admin-web 経費一覧から承認 / 却下 / 領収書ダウンロードを実行できるようにした
  - 受領ファイル保存は `ObjectStorage` 抽象に寄せ、Cloudflare R2 切替時に object key 契約を維持できるよう整理した
  - focused pytest 13件、admin-web build、staff-mobile build で検証済み
- 完了: 予定確認返信と通知導線
  - `assignments` に worker 向けの応答状態、依頼日時、回答日時、連絡メモを追加し、worker ロールに `assignment_response` 権限を付与した
  - `POST /api/assignments/{id}/worker-response` と `GET /api/assignments?response_status=...` を追加し、予定確認の返信と未回答件数の抽出を API で扱えるようにした
  - `apps/staff-mobile` の予定画面に参加可 / 辞退の返信 UI、下部ナビの確認待ちバッジ、確認依頼 / 回答時刻表示を追加した
  - scheduler の週次催促を worker 向け未回答予定確認メールへ接続し、対象期間内の pending assignment を worker ごとに集約して送信できるようにした
  - `GET /api/dashboard` に pending assignment response 監視を追加し、admin-web で未回答件数、要エスカレーション件数、依頼経過・稼働日接近・メール未設定を一覧できるようにした
  - `GET /api/assignments` に monitoring_status / missing_email_only filter と監視メタデータを追加し、admin-web の `/operations/assignment-responses` で専用の予定確認監視ページを開けるようにした
  - `POST /api/assignments/reminders/send` を追加し、予定確認監視ページから選択中の pending assignment を worker ごとに束ねて手動再送できるようにした
  - `POST /api/assignments/reminders/history` を追加し、予定確認監視ページで表示中 assignment に紐づく recipient 単位の直近催促履歴を確認できるようにした
  - `POST /api/assignments/reminders/escalate` と `assignment_response_escalation_summary` メールを追加し、要エスカレーション assignment を admin / ops / accounting 向けに要約通知できるようにした
  - `POST /api/assignments/reminders/escalations/history` を追加し、予定確認監視ページで管理者通知の直近エスカレーション履歴も確認できるようにした
  - 予定確認監視ページでは要エスカレーション行の単件通知と複数選択通知の両方に対応し、通知結果を sent / failed / recipient 数で即時確認できる
  - Playwright の phase1 スモークに予定確認監視ページの再送 / 通知フローを追加し、2026-04-01 時点で 4 件すべて成功している
  - staff-mobile に Playwright の phase5 smoke を追加し、当日打刻・予定返信・可否登録・経費申請・実績確認を通しで検証済み
  - focused pytest 40件、admin-web build、staff-mobile build、admin-web smoke 5件、staff-mobile smoke 1件がすべて成功
  - `scripts/scheduler_runner.py --run-once weekly_reminder` を追加し、`EMAIL_DRY_RUN=true` の one-shot 検証で scheduler/SMTP 設定を本番相当に寄せた確認ができるようにした
  - ローカルでは `alembic upgrade head` を適用済みで、focused pytest 36件、assignment API pytest 27件、admin-web build、Playwright smoke 4件で予定確認監視の履歴 / エスカレーション通知まで検証済み
  - 2026-04-01 の追加回帰で backend pytest 302件、admin-web build、staff-mobile build、admin-web smoke 5件、staff-mobile smoke 1件を再実行し、すべて成功した
  - 追加回帰で admin 権限マッピングの手動列挙漏れにより `assignment_response` が欠落していたため、admin は `set(Permission)` を使う形へ修正した
  - admin-web の master 取得系 API で URL を二重構築していた箇所を修正し、backend ログに出ていた不正な query string を解消した
  - アサイン一覧の edit 用 shift-slot 取得で `limit=300` が backend 上限 `MAX_PAGE_LIMIT=200` を超えていたため 200 に合わせ、再スモーク後の backend ログから 422 を解消した
  - admin-web の project 作成スモークは即時一覧表示前提で不安定だったため、検索ベースの検証へ寄せて再実行時のページング依存を除去した

### 2026-04-01 引き継ぎメモ
- この時点の広め回帰は backend pytest 302件、admin-web build、staff-mobile build、admin-web smoke 5件、staff-mobile smoke 1件まで完了している
- broad regression の再実行時は共有ターミナルの cwd を必ず repo root に戻すこと。`apps/admin-web` 配下のままだと pytest discovery が 0 件に見える
- 未処理の機能不具合は現時点では残っておらず、残タスクは git 差分の commit 分割と PR 単位の整理が中心
- commit を切るなら backend schema/API、admin-web assignment response、staff-mobile phase5、docs/scripts の4塊に分けると追いやすい

---

## 🔗 Kintone連携（マスタ同期）

### 同期対象（6マスタ）
- workers
- clients
- sites
- roles
- project_types
- suppliers

同期スクリプト: `scripts/sync_db_to_kintone.py`

---

## 🚀 運用開始までのフェーズ（外部環境での作業・実行手順）

### Phase 0: セキュリティ衛生（Secrets）
- 完了: ドキュメント内のAPIトークン値を秘匿化（`<SET_IN_ENV>` へ置換）

### Phase 1: Kintone設定
- Workers アプリに `introducer_supplier_id` を追加
  - 自動化: `scripts/add_kintone_missing_fields.py`（suppliersの`supplier_id`型を参照して型合わせ）

完了: 2026-01-30

### Phase 2: データ移行
- 紹介者（workers.introducer_worker_id）→ suppliers 移行
  - dry-run: `python scripts/migrate_introducers_to_suppliers.py`
  - 実移行: `python scripts/migrate_introducers_to_suppliers.py --commit`

状況: dry-run 実行（対象0件）

### Phase 3: 同期・運用フロー
- suppliers のKintone同期（必要に応じて）: `python scripts/sync_db_to_kintone.py suppliers`
- バンドル価格の手入力運用フロー確立（仕様/決定: DEC-009）
- 紹介者登録フロー（Kintone→DB→支払）をRUNBOOKへ明文化

完了: suppliers同期（初回 add）

## ✅ Sprint 1 - 完了 (48/48 tests passing)

### 実装完了項目
- [x] データモデル (models/base.py, enums.py, master.py, transaction.py)
- [x] CSV取り込みサービス (services/csv_import.py)
  - [x] 洗い替えモード (REPLACE_SCOPE)
  - [x] 二重化防止 (file_hash検知)
  - [x] エラー処理と部分取り込み
  - [x] 監査ログ出力
- [x] 時間計算サービス (services/time_calc.py)
  - [x] 丸め処理（切り上げ/切り捨て/四捨五入）
  - [x] 休憩自動計算
  - [x] 深夜割増計算
- [x] テスト (tests/test_csv_import.py, tests/test_time_calc.py)
  - [x] 6 CSV importテスト
  - [x] 16 時間計算テスト

---

## ✅ Sprint 2 - 完了 (48/48 tests passing)

### 実装完了項目
- [x] 単価マスタ (models/master.py)
  - [x] PriceSales (売上単価)
  - [x] PriceOutsource (外注単価)
  - [x] PriceRule (条件ベース単価)
- [x] 請求書・支払明細モデル (models/transaction.py)
  - [x] Invoice, InvoiceLine
  - [x] Payout, PayoutLine
  - [x] 版管理フィールド (version, parent_id, superseded_by_id)
- [x] 単価解決サービス (services/price_resolver.py)
  - [x] 優先順位: locked_price → project_price → price_rule → default
- [x] 請求書生成サービス (services/invoice_service.py)
  - [x] generate_invoice()
  - [x] issue_invoice()
  - [x] correct_invoice()
  - [x] reissue_invoice()
- [x] 支払明細生成サービス (services/payout_service.py)
  - [x] generate_payout()
  - [x] approve_payout()
  - [x] mark_payout_paid()
  - [x] correct_payout()
- [x] 締め処理サービス (services/closing.py)
  - [x] soft_close() - 解除可能
  - [x] hard_close() - 二者承認必要
  - [x] release_soft_close() - ガードレール付き
  - [x] release_hard_close() - 二者承認
  - [x] 解除回数上限チェック
- [x] 集計サービス (services/aggregation.py)
  - [x] get_sales_summary()
  - [x] get_cost_summary()
  - [x] get_variance_alerts()
- [x] ダッシュボードサービス (services/dashboard.py)
  - [x] get_dashboard_summary()
  - [x] get_unprocessed_assignments()
  - [x] get_missing_price_alerts()
  - [x] get_unprocessed_invoices()
  - [x] get_unprocessed_payouts()
- [x] 監査ログサービス (services/audit.py)
- [x] テスト (tests/test_closing.py)
  - [x] 7 締め処理テスト

---

## ✅ Sprint 3 - 完了 (48/48 core tests passing)

### 完了項目（2026-01-27）
- [x] **Task 1: 権限管理実装** ✅
  - [x] User model with UserRole (ADMIN/OPS/ACCOUNTING/SITE_MANAGER/WORKER)
  - [x] Permission enum (30 permissions)
  - [x] ROLE_PERMISSIONS mapping
  - [x] @require_permission decorator
  - [x] AuthService with has_permission(), check_permission()
  - [x] Migration 003_add_users.py
  - [x] 13 tests (全てPASS)

- [x] **Task 2: 単価スナップショット統合** ✅
  - [x] csv_import.py と price_resolver.py を統合
  - [x] Assignment.shift_slot 経由で project_id を取得
  - [x] _resolve_assignment() が CANCELED を含めて取得
  - [x] Actual.applied_price_sales/outsource に単価を保存

- [x] **Task 4: 再計算サービス実装** ✅
  - [x] RecalcPreview dataclass（影響件数、差分表示）
  - [x] RecalcResult dataclass（成功/スキップ/エラー件数）
  - [x] preview_recalculation()（プレビュー機能）
  - [x] recalculate()（再計算実行）
  - [x] Hard Close後の再計算拒否（forceモード除く）
  - [x] 請求書/支払明細発行済み実績のスキップ
  - [x] RecalculationService統合
  - [x] 6 tests (全てPASS)

- [x] **Task 5: 経費精算・インセンティブ管理実装** ✅
  - [x] Expense model (project_id, worker_id, amount, status, approved_by)
  - [x] Incentive model (rule_id, worker_id, period_key, amount, status)
  - [x] IncentiveRule model (condition_type, condition_json, amount)
  - [x] InvoiceLine/PayoutLine に line_type, expense_id, incentive_id 追加
  - [x] ExpenseService (create, approve, reject, get_for_period)

---

## ✅ Sprint 4 - 完了 (126/126 tests passing)

### 実装完了項目（2026-01-27）
- [x] **Task 8: 経費・インセンティブ統合** ✅
  - [x] Expense/Incentive に target_invoice_id, target_payout_id 追加
  - [x] invoice_service.py: 経費・インセンティブ行を自動追加
  - [x] payout_service.py: 経費・インセンティブ行を自動追加
  - [x] aggregation.py: 経費・インセンティブを含む集計
  - [x] Migration 005_expense_incentive_targets.py
  - [x] 4 tests (expense) + 4 tests (incentive) - 全てPASS

- [x] **Task 11: ダッシュボードテスト拡張** ✅
  - [x] test_dashboard_unprocessed_items_details(): 詳細バリデーション
  - [x] test_dashboard_variance_threshold(): 4時間差異検出
  - [x] test_dashboard_multiple_periods(): 複数期間集計
  - [x] 3 tests 追加 (5 → 8 tests)

- [x] **Task 12: PDF生成機能実装** ✅
  - [x] PDFGeneratorService (src/services/pdf_generator.py)
  - [x] generate_invoice_pdf(): 請求書PDF生成
  - [x] generate_payout_pdf(): 支払明細PDF生成
  - [x] reportlab ライブラリ統合
  - [x] 日本語フォント対応 (ipaexg.ttf)
  - [x] 3 tests (PDF生成、ファイル保存)

- [x] **Task 13: メールテンプレート実装** ✅
  - [x] EmailTemplateService (src/services/email_template.py)
  - [x] 7種類のテンプレート:
    - shift_unconfirmed_reminder()
    - csv_unsubmitted_reminder()
    - csv_error_rejection() - エラー最大5件表示
    - invoice_approval_request()
    - payout_approval_request()
    - escalation_notification()
  - [x] カスタマイズ可能な署名
  - [x] 8 tests (テンプレート生成、エラー切り捨て、署名)

- [x] **Task 14: 統合テスト拡張** ✅
  - [x] test_csv_error_recovery_workflow():
    - PARTIAL_ERROR ステータス検証
    - SUPERSEDED actual ステータス検証
    - 洗い替えメカニズム検証
  - [x] test_multiple_projects_parallel_workflow():
    - 2案件の独立処理
    - 並行Soft Close処理
  - [x] 2 tests 追加 (2 → 4 tests)

### テスト統計
- Sprint 1-2: 48 tests
- Sprint 3: 19 tests (auth + recalc)
- Sprint 4: 59 tests (expense + incentive + PDF + email + dashboard + integration)
- **合計: 126 tests PASSED**

### 追加ファイル (Sprint 4)
| ファイル | 行数 | 目的 |
|---------|------|------|
| src/services/pdf_generator.py | 320 | PDF生成サービス |
| src/services/email_template.py | 310 | メールテンプレートサービス |
| tests/test_pdf_simple.py | 180 | PDF生成テスト |
| tests/test_email_template.py | 130 | メールテンプレートテスト |
| alembic/versions/005_expense_incentive_targets.py | 65 | 経費・インセンティブ統合 |
| **合計** | **1,005行** | **5ファイル新規作成** |

### 変更ファイル (Sprint 4)
| ファイル | 変更内容 |
|---------|----------|
| src/services/invoice_service.py | 経費・インセンティブ行自動追加 |
| src/services/payout_service.py | 経費・インセンティブ行自動追加 |
| src/services/aggregation.py | 経費・インセンティブ集計統合 |
| src/models/transaction.py | Expense/Incentiveにtarget_invoice_id, target_payout_id追加 |
| tests/test_dashboard.py | 3テスト追加 (5 → 8) |
| tests/test_integration.py | 2テスト追加 (2 → 4) |
  - [x] IncentiveService (create, approve, reject, match_attendance)
  - [x] Migration 004_add_expense_incentive.py
  - [x] ExpenseStatus, IncentiveStatus enum追加
  - [x] Permission 6種追加 (EXPENSE_*, INCENTIVE_*)

- [x] **Task 6: RUNBOOK詳細化** ✅
  - [x] RUNBOOK_MONTHLY.md に具体的なコマンド例を追加
  - [x] チェックリスト、エラー対応表、トラブルシューティングを追加

- [x] **Task 8: 請求書・支払明細への経費・インセンティブ統合** ✅
  - [x] invoice_service.py: Expense/Incentive行追加ロジック実装
  - [x] payout_service.py: Expense/Incentive行追加ロジック実装
  - [x] Expense model に target_invoice_id, target_payout_id 追加
  - [x] target_X_id is None チェックで二重追加防止
  - [x] Migration 005_add_expense_invoice_payout_ids.py
  - [x] 4 tests (test_invoice_payout.py 全てPASS)

- [x] **Task 9: 集計サービス完全書き換え** ✅
  - [x] aggregation.py 完全リファクタリング
  - [x] canceled assignment と invalid actual を集計から除外
  - [x] 予定/確定の集計を区別（planned/confirmed フラグ）
  - [x] 11 tests 追加（全てPASS）
  - [x] ゼロ除算対策（profit_rate計算）

- [x] **Task 10: ドキュメント整備** ✅
  - [x] README.md 作成（概要、セットアップ、使い方、テスト状況）
  - [x] アーキテクチャ図、権限管理、トラブルシューティングを追加
  - [x] IMPLEMENTATION_LOG.md 作成（全タスクの実装記録）
  - [x] FILE_INDEX.md 作成（全ファイルの役割と依存関係）

- [x] **Task 11: STATUS.md更新** ✅
  - [x] 実装状況、テストカバレッジ、新機能を記録

- [x] **Task 12: PDF生成機能実装** ✅
  - [x] src/services/pdf_generator.py 作成
  - [x] generate_invoice_pdf() 実装（請求書PDF生成）
  - [x] generate_payout_pdf() 実装（支払明細PDF生成）
  - [x] 日本語フォント対応（MSゴシック）
  - [x] 版管理対応（version表示）
  - [x] LineType enum追加（WORK/EXPENSE/INCENTIVE）
  - [x] test_pdf_simple.py 作成（3 tests）

### 外部運用・任意拡張（環境依存）
以下は環境依存または運用設計の項目であり、実装タスクではありません。

- ダッシュボード詳細バリデーションの運用観点での強化（必要に応じて）
- エラー復旧フローの運用確認（CSV差戻し→修正→再取込）
- 複数案件並行処理フローの運用確認
- Kintone API認証/連携の本番設定（トークン/権限/アプリ構成）

---

## 📊 テストカバレッジ

### 現在の状況（2026-01-27）
```
✅ 113/113 tests passing (全コア機能完成)
- test_csv_import.py: 6 tests (PASSED)
- test_time_calc.py: 16 tests (PASSED)
- test_closing.py: 7 tests (PASSED)
- test_auth.py: 13 tests (PASSED)
- test_recalculation.py: 6 tests (PASSED)
- test_aggregation.py: 11 tests (PASSED)
- test_invoice_payout.py: 4 tests (PASSED)
- test_expense.py: 4 tests (PASSED)
- test_incentive.py: 4 tests (PASSED)
- test_integration.py: 2 tests (PASSED)
- test_dashboard.py: 5 tests (PASSED)
- test_audit_search.py: 7 tests (PASSED)
- test_exceptions.py: 17 tests (PASSED)
- test_price_resolver.py: 8 tests (PASSED)
- test_pdf_simple.py: 3 tests (PASSED) ✨ NEW
```

### カバー済み機能
- CSV取り込み（洗い替え、二重化防止、CANCELED除外）
- 時間計算（丸め、休憩、深夜割増）
- 締め処理（Soft/Hard Close、解除ガードレール）
- 権限管理（ロール、Permission、デコレータ）
- 再計算サービス（プレビュー、Hard Closeガード、forceモード）
- 集計サービス（予定/確定の区別、CANCELED/invalid除外）
- 請求書生成（経費・インセンティブ統合）
- 支払明細生成（経費・インセンティブ統合）
- 経費精算（承認フロー、期間絞り込み）
- インセンティブ管理（出勤連続日数マッチング）
- **PDF生成（請求書・支払明細のPDF出力）** ✨ NEW

### 未カバー
- メールテンプレート（実装必要）
- 統合テスト（エラー復旧フロー等の追加）
- Kintone API連携（未着手）

---

## 🗂️ データベース

### マイグレーション
- [x] 001_initial.py - 基本テーブル
- [x] 002_pricing_billing.py - 単価・請求・支払テーブル
- [x] 003_add_users.py - ユーザー・権限テーブル
- [x] 004_add_expense_incentive.py - 経費・インセンティブテーブル
- [x] 005_add_expense_invoice_payout_ids.py - 経費の請求書/支払明細紐づけ ✨ NEW
- [x] ff166af0ba6d_add_performance_indexes.py - パフォーマンスインデックス

### テーブル一覧
#### マスタ
- workers, clients, sites, project_types, roles
- price_sales, price_outsource, price_rules
- **users** ✨ NEW
- **incentive_rules** ✨ NEW

#### トランザクション
- projects, shift_slots, assignments, actuals
- import_batches
- invoices, invoice_lines (拡張: line_type, expense_id, incentive_id) ✨ UPDATED
- payouts, payout_lines (拡張: line_type, expense_id, incentive_id) ✨ UPDATED
- closings
- audit_logs
- **expenses** ✨ NEW
- **incentives** ✨ NEW

---

## 🔧 未決事項（DECISION_LOGに記録予定）

### DEC-004: 再計算のスコープ（✅ 解決済み）
- **決定**: actual単位で再計算、Hard Close期間はスキップ（forceモード除く）
- **実装**: RecalculationService.recalculate()

### DEC-005: 締め解除の通知
- 検討中: 締め解除時に関係者へ自動通知するか
- 影響: ガバナンス強化

### DEC-006: PDF保管先
- 検討中: ファイルシステム vs オブジェクトストレージ
- 影響: invoice.storage_key の実装

### DEC-007: インセンティブルールの優先順位
- 検討中: 複数ルールがマッチした場合の適用優先順位
- 影響: IncentiveService.match_XXX() の実装

---

## 🚨 既知の課題

### Issue-001: test_invoice_payout.py の4テスト失敗
- **原因**: テストが期待するAPIと実装のAPIが異なる
  - Actual.break_minutes → break_minutes_input
  - InvoiceService() → invoice_service.generate_invoice()
  - PayoutStatus.CONFIRMED → PayoutStatus.XXX（enum要確認）
- **対応**: Task 3で修正予定

### Issue-002: price_resolver.py の locked_price 参照（✅ 解決済み）
- **原因**: Assignment.locked_price が存在しない可能性
- **対応**: Task 2で修正済み（locked_price_sales/outsource に変更）
- **状態**: ✅ 解決済み

### Issue-003: test_expense.py, test_incentive.py のモデルフィールド不一致
- **原因**: テストコードが想定するフィールド名とモデルが不一致
  - Client.billing_name → 存在しない（nameのみ）
  - Site.client_id → Projectで管理
  - Worker.worker_code → 存在しない
  - Project.status, start_date, end_date → 必須ではない
- **対応**: Task 7で修正予定

---

## 📅 次のマイルストーン

### Sprint 3 完了条件（2026-01-27時点）
- [x] 単価スナップショット統合 ✅
- [x] RUNBOOK詳細化 ✅
- [x] ドキュメント整備 ✅
- [x] STATUS.md更新 ✅
- [x] 再計算サービス実装 ✅
- [x] 権限管理実装 ✅
- [x] 経費精算・インセンティブ管理実装 ✅
- [x] 全コアテスト PASS (48/48) ✅
- ダッシュボードテスト追加（現在はテスト済み）
- 請求書・支払明細への経費・インセンティブ統合（実装済み）

**Sprint 3 達成度: 85%** ✅ MVP機能ほぼ完成

### Sprint 4 計画（当時のメモ）
- test_expense.py, test_incentive.py の完成（実装済み）
- invoice_service/payout_service への経費・インセンティブ統合（実装済み）
- REST API実装 (FastAPI)（実装済み）
- フロントエンド（管理画面）（任意拡張）
- PDF生成機能（実装済み）
- メール送信機能（実装済み）
- Kintone API連携（環境依存）

---

## 🔗 関連ドキュメント

- [DESIGN_SPEC_v0.3.md](../spec/DESIGN_SPEC_v0.3.md) - 仕様書（正本）
- [REVIEW_MERGE_v0.3.md](../spec/REVIEW_MERGE_v0.3.md) - レビュー反映記録
- [DECISION_LOG.md](../decisions/DECISION_LOG.md) - 決定ログ
- [AGENTS.md](../../AGENTS.md) - AI Agent向けルール
- [RUNBOOK_MONTHLY.md](../../RUNBOOK_MONTHLY.md) - 月次運用手順
- [README.md](../../README.md) - プロジェクト概要
- **[IMPLEMENTATION_LOG.md](../IMPLEMENTATION_LOG.md) - 実装ログ** ✨ NEW
- **[FILE_INDEX.md](../FILE_INDEX.md) - ファイルインデックス** ✨ NEW

---

## 📝 実装メモ

### Sprint 3 実装の要点（2026-01-27）
- **権限管理**: @require_permissionデコレータで関数レベルのアクセス制御
- **再計算サービス**: preview → execute の2ステップ、Hard Closeガード実装
- **経費・インセンティブ**: InvoiceLine/PayoutLine拡張で3種類の行タイプ対応（actual/expense/incentive）
- **マイグレーション**: SQLite batch mode対応でFK制約追加
- **テスト**: 48テスト全てPASS、リグレッションなし
- **price_resolver.py**: Assignment.shift_slot.project_id 経由で取得するように修正
- **csv_import.py**: price_resolver統合、AssignmentStatus import追加、CANCELED チェックを _process_row() に移動
- **_resolve_assignment()**: CANCELED も含めて取得し、呼び出し側でチェック

### 破綻防止チェックリスト
- [x] CSV再取り込み二重化防止 (file_hash)
- [x] canceled assignment の除外 (status=INVALID)
- [x] 締め後の改変防止 (Hard Close)
- [x] 締め解除のガードレール (回数上限、二者承認)
- [x] 監査ログ（全変更を記録）

---

## ✅ Sprint 4 - 完了 (126/126 tests passing)

### 完了項目（2026-01-29）
- [x] **Task 19: TODO実装完了（残タスク一掃）** ✅
  - [x] kintone_service.py
    - [x] write_back_errors（エラーログ追加）
    - [x] export_to_csv（CSV出力、shift-jis対応）
  - [x] scheduler.py
    - [x] _run_weekly_reminder（週次催促メール、EmailTemplateService統合）
    - [x] _run_daily_update（ダッシュボードキャッシュ更新）
    - [x] _run_monthly_invoice（月次請求書生成・発行、InvoiceService統合）
  - [x] auth.py
    - [x] can_access_project（Site Manager権限チェック強化、ShiftSlot.site_manager_id照合）
  - [x] main.py
    - [x] actor="api_system"（認証未導入の暫定値、将来JWT/OAuth2実装）
  - [x] 126 tests (全てPASS)
  - [x] COMPLETION_REPORT_2026-01-29.md 作成
  - [x] IMPLEMENTATION_LOG.md 更新（Task 19追加）

### 完了項目（2026-01-30）
- [x] **Task 20: 残タスク完全制覇（EmailSender/PDF/JWT/Manager統合）** ✅
  - [x] EmailSender完全統合
    - [x] scheduler._run_weekly_reminder（send_bulk_emails統合、環境変数制御）
    - [x] scheduler._run_monthly_invoice（承認依頼メール送信）
  - [x] PDF生成完全統合
    - [x] scheduler._run_monthly_invoice（PDFGenerator統合、./invoices/）
  - [x] JWT/OAuth2認証実装
    - [x] jwt_auth.py（access/refresh token、bcrypt、jose）
    - [x] main.py（/api/auth/token, /api/auth/me）
    - [x] パッケージ追加（python-jose[cryptography], passlib[bcrypt], python-multipart）
  - [x] Project Manager実装
    - [x] マイグレーション（a9c940728ad0）
    - [x] Project.primary_manager_id/secondary_manager_id追加
    - [x] auth.py（can_access_project実装）
  - [x] 126 tests (全てPASS)
  - [x] COMPLETION_REPORT_2026-01-30.md 作成
  - [x] IMPLEMENTATION_LOG.md 更新（Task 20追加）

- [x] **Task 21: 低優先度タスク完全制覇（ドキュメント整備＋drv案件確定）** ✅
  - [x] DEPLOYMENT_GUIDE.md更新
    - [x] JWT認証設定追加（JWT_SECRET_KEY生成方法）
    - [x] メール送信設定更新（EMAIL_DRY_RUN, EMAIL_PROVIDER）
    - [x] スケジューラー設定追加（SCHEDULER_WEEKLY_DAY, SCHEDULER_WEEKLY_HOUR等）
    - [x] 認証エンドポイント追加（POST /api/auth/token, GET /api/auth/me）
    - [x] スケジューラー自動実行ジョブ一覧追加
    - [x] チェックリスト更新（JWT認証テスト、PDF生成テスト）
  - [x] drv案件の未決事項確定
    - [x] DRV_PAYOUT_RULES.md: 暫定決定と実装優先順位を明記
    - [x] 6項目の暫定決定（1人工の数え方、Wヘッダー単価、日額単価、下請けマスタ、統括8%、現場管理報酬）
    - [x] 運用開始前に確定が必要な項目を列挙
  - [x] Kintoneフィールドマッピング整備確認
    - [x] sync_db_to_kintone.py: 既に field_mappings/*.json を使用していない
    - [x] 直接フィールドコード（英語）で送信しているため、追加整備は不要
  - [x] RUNBOOK更新
    - [x] RUNBOOK_MONTHLY.md: スケジューラー自動実行情報追加
    - [x] RUNBOOK_WEEKLY.md: 週次催促メール情報追加
  - [x] FINAL_SUMMARY_2026-01-30.md 更新（全タスク完了）
  - [x] COMPLETION_REPORT_2026-01-30_FINAL.md 作成
  - [x] IMPLEMENTATION_LOG.md 更新（Task 21追加）

- [x] **Task 22: suppliersマスタ実装（下請け・紹介者マスタ）** ✅
  - [x] Supplier モデル追加（src/models/master.py）
  - [x] Worker モデル拡張（introducer_supplier_id/introducer_worker_id）
  - [x] Payout モデル拡張（supplier_id追加、worker_id を nullable化）
  - [x] PayoutService 拡張（generate_supplier_payout追加）
  - [x] マイグレーション実行（e1f2a3b4c5d6）
  - [x] データ移行スクリプト作成（scripts/migrate_introducers_to_suppliers.py）
  - [x] 126 tests (全てPASS)
  - [x] IMPLEMENTATION_LOG.md 更新（Task 22追加）

- [x] **Task 23: Kintone連携（suppliersマスタ）** ✅
  - [x] suppliers_sjis.csv作成（kintone_app/）
  - [x] sync_db_to_kintone.py 拡張（sync_suppliers関数追加）
  - [x] .env.template 更新（KINTONE_TOKEN_SUPPLIERS追加）
  - [x] SUPPLIERS_KINTONE_APP_SETUP.md 作成（Kintoneアプリ作成手順）
  - [x] ドキュメント更新（STATUS.md）

- [x] **Task 24: Kintone連携完了（suppliersマスタ同期成功）** ✅
  - [x] Kintoneアプリ作成（アプリID: 187）
  - [x] .env ファイル更新（KINTONE_APP_SUPPLIERS=187, KINTONE_TOKEN_SUPPLIERS）
  - [x] サンプルデータ作成（3件）
  - [x] Kintone同期成功（3件追加）
  - [x] sync_db_to_kintone.py 構文エラー修正

### 残課題
**なし**（全タスク完了）

### 運用開始前の確認事項
- [x] Kintone紹介者マスタアプリ作成（アプリID: 187）✅ 2026-01-30完了
- [x] KINTONE_APP_SUPPLIERS, KINTONE_TOKEN_SUPPLIERS 設定 ✅ 2026-01-30完了
- [x] データ同期テスト成功（3件同期完了）✅ 2026-01-30完了
- Workers アプリに introducer_supplier_id フィールド追加
- データ移行実行（scripts/migrate_introducers_to_suppliers.py）
- バンドル価格の手入力運用フロー確立

---

## 🎯 完了した成果物

### Sprint 3 完了分
1. ✅ **単価スナップショット統合** - CSV取込時に単価を自動解決・保存
2. ✅ **RUNBOOK_MONTHLY.md** - 月次運用の具体的な手順書
3. ✅ **README.md** - プロジェクト全体の概要とセットアップガイド
4. ✅ **STATUS.md** - 実装状況と未決事項の一覧

### Sprint 4 完了分
1. ✅ **TODO実装完了** - コード内のTODO箇所を全て実装
2. ✅ **DRV_PAYOUT_RULES.md** - drv案件運用ルール整理
3. ✅ **DECISION_LOG.md（DEC-009）** - drv案件の「人工」「日額単価」「下請け支払」表現
4. ✅ **COMPLETION_REPORT_2026-01-29.md** - 完了報告（実装内容、テスト結果、残課題）
5. ✅ **EmailSender完全統合** - SMTP設定、週次催促、月次承認依頼
6. ✅ **PDF生成完全統合** - 請求書PDF自動生成、版管理
7. ✅ **JWT/OAuth2認証** - FastAPI Security、bcrypt、jose
8. ✅ **Project Manager実装** - primary/secondary manager、権限チェック
9. ✅ **COMPLETION_REPORT_2026-01-30.md** - 最終完了報告
10. ✅ **DEPLOYMENT_GUIDE.md更新** - 環境変数追加（JWT, EMAIL, SCHEDULER）
11. ✅ **RUNBOOK更新** - 月次/週次の自動実行情報追加
12. ✅ **drv案件の未決事項確定** - 暫定決定と実装優先順位を明記
13. ✅ **Kintoneフィールドマッピング整備確認** - 追加整備不要を確認
14. ✅ **FINAL_SUMMARY_2026-01-30.md** - 全タスク完了サマリー
15. ✅ **COMPLETION_REPORT_2026-01-30_FINAL.md** - 最終完了報告（全詳細）
17. ✅ **Kintone連携（suppliersマスタ）** - sync_db_to_kintone.py拡張、SUPPLIERS_KINTONE_APP_SETUP.md作成

### 今後のタスク
**なし**（全タスク完了）

### 次のステップ（運用開始準備）
- Kintone紹介者マスタアプリ作成（アプリIDは運用で設定）
- .env ファイル更新（KINTONE_APP_SUPPLIERS, KINTONE_TOKEN_SUPPLIERS）
- Workers アプリに introducer_supplier_id フィールド追加
- データ移行実行（scripts/migrate_introducers_to_suppliers.py）
- suppliers データを Kintone へ同期
- バンドル価格の手入力運用フロー確立

---

最終更新: 2026-01-30  
次回更新: drv案件の未決事項確定時
