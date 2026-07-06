# デプロイ遅延・失敗の原因と対処（2026-07-02 整理）

本番反映が遅くなったり途中で止まったりした事象の正本メモ。次回セッションは **この文書を最初に読んでから** デプロイする。

関連: `scripts/deploy/DEPLOY_STEPS.md`（初回セットアップ）、`scripts/deploy/02_app_deploy.sh`（フルデプロイ）

---

## 1. 変更種別ごとの最短手順

| 変更内容 | 使うスクリプト | 目安時間 |
|---------|---------------|---------|
| admin-web / staff-mobile の UI のみ | `03_frontend_only_deploy.sh` | 3〜5分 |
| Python API のみ | `git pull` + `restart_uvicorn.sh` | 1〜2分 |
| DB マイグレーション含む | `02_app_deploy.sh` | 10〜20分（OCR 依存で長い） |

**原則**: favicon・CSS・React だけの変更で `02_app_deploy.sh`（pip install + alembic + 全ビルド）を回さない。

### フロントのみ（推奨コマンド）

```bash
# VPS（vanzai ユーザー）
cd /var/www/vanzai
git fetch origin && git reset --hard origin/feature/2026-03-31-next-work
bash scripts/deploy/03_frontend_only_deploy.sh
```

### API 再起動のみ

```bash
cd /var/www/vanzai
git pull origin feature/2026-03-31-next-work   # 必要なら
bash restart_uvicorn.sh
curl -sf https://api.vanzai-portal.com/api/health
```

---

## 2. 2026-07-02 セッションで実際に起きたこと

### 2.1 Windows ローカル: ファイル欠落・`[conflicted]` 大量発生

**症状**

- `package.json` / `index.html` / `SideNav.tsx` が消える、または `package [conflicted N].json` が大量発生
- `npm run build` が `ENOENT package.json` で即失敗
- コミット時に `index.html` が **削除としてステージ** され、本番に HTML が無い状態になる

**調査結果（2026-07-07）**

| 項目 | 状態 |
|------|------|
| プロジェクトパス | `C:\VANZAI_project`（**OneDrive フォルダ外**） |
| OneDrive 設定 | **あり** — デスクトップ・ドキュメントは `C:\Users\bunya\OneDrive` / `C:\OneDrive\OneDrive - OKS…` へリダイレクト（Microsoft 365 組織アカウント） |
| OneDrive プロセス | 調査時点では **未稼働**（常時同期しているわけではない可能性） |
| `[conflicted N]` の意味 | **OneDrive 固有**の競合ファイル名。別マシン／別同期コピーと同時編集した痕跡 |
| git 履歴 | `package.json` の **delete がコミットに含まれた** 記録が複数回あり（Cursor エージェント作業時）。その後 `package.jsonを復元` コミットが繰り返されている |

**結論（想定される複合原因）**

1. **主因**: Cursor エージェントの git 操作で正本ファイルが削除コミットされる
2. **副因**: OneDrive が PC に設定済みのため、同期対象に入っていたコピーや過去の同期状態で `[conflicted]` が発生

**対処**

1. 正本は git。`git show HEAD:apps/admin-web/package.json` で内容確認
2. 復元: `git checkout HEAD -- <path>`
3. **BOM なし UTF-8** で書き戻す（PowerShell `Set-Content` は BOM 付きになり vite が落ちる）
4. コミット前に `git status` で `D index.html` / `D package.json` が無いか必ず確認
5. リポジトリは **OneDrive 配下に置かない**（現状 `C:\VANZAI_project` で OK）。ドキュメント配下に clone しない
6. OneDrive の「バックアップ」設定は [OneDrive 設定] → [同期とバックアップ] で確認し、開発フォルダを含めない

### 2.2 package.json の UTF-8 BOM

**症状**

```
Failed to load PostCSS config: Unexpected token '', "{ "nam"... is not valid JSON
```

**対処**

- 先頭バイトが `EF BB BF` でないことを確認（`xxd package.json | head -1`）
- エディタで「UTF-8（BOM なし）」保存

### 2.3 フルデプロイが alembic で停止

**症状**

```
Can't locate revision identified by '20260616a001'
```

**原因**

- VPS の DB は当該リビジョンを head にしているが、作業ブランチに migration ファイルが無い／未マージ

**対処**

- UI 変更だけなら **alembic をスキップ**（`03_frontend_only_deploy.sh`）
- API 変更で migration が必要なら、先に migration ファイルをブランチに揃えてから `02_app_deploy.sh`

### 2.4 VPS にローカル変更が残り git pull 失敗

**症状**

```
Your local changes would be overwritten by merge
```

**対処**

```bash
git stash push -u -m "pre-deploy-$(date +%Y%m%d)"
git pull origin feature/2026-03-31-next-work
# または UI のみなら
git fetch origin && git reset --hard origin/feature/2026-03-31-next-work
```

stash は `.env` を含まないよう注意（通常 .env は git 管理外）。

### 2.5 API 停止 → ログイン「処理に失敗」

**症状**

- 管理画面ログインで「ログイン処理に失敗しました」
- `https://api.vanzai-portal.com/api/health` が 502

**原因（今回）**

1. `restart_uvicorn.sh` が `/var/www/vanzai/logs` 未作成のままログ追記し、起動ログが欠落
2. デプロイ途中で API プロセスが落ちたままフロントだけ更新された

**対処**

```bash
mkdir -p /var/www/vanzai/logs
bash /var/www/vanzai/restart_uvicorn.sh
curl -sf https://api.vanzai-portal.com/api/health
```

`restart_uvicorn.sh` は JWT 未設定検知と `/api/health` 確認を行うよう更新済み。

---

## 3. エージェント向けチェックリスト（デプロイ前）

- [ ] 変更は UI のみか / API か / DB かを分類した
- [ ] `package.json`（admin + staff）と `CHANGELOG.md` を更新した（ユーザー向け変更時）
- [ ] ローカルで `npm --prefix apps/admin-web run build` が通る
- [ ] `git status` に意図しない `D`（削除）が無い
- [ ] コミット → push 後、VPS で **適切なスクリプト** を選んだ
- [ ] 完了後 `curl https://api.vanzai-portal.com/api/health` と画面ログインを確認

---

## 4. ブランドマーク（候補B）の正本

**採用デザイン**: V と Z が重なるモノグラム（ゴールド V + クリーム Z、背景 `#1b2530`）

- 正本 SVG: `apps/admin-web/public/favicons/candidate-b-vz.svg`
- 本番 favicon: `apps/admin-web/public/favicon.svg`（同一パス）
- React: `apps/admin-web/src/components/BrandMark.tsx`

**注意**: 0.9.24 で一時的に「左右分離」レイアウトに変えたが、ユーザー選定の候補Bではない。0.9.25 で元の重なりデザインに戻す。

サイドナビで文字に滲む場合は **デザイン変更ではなく** `.brand-mark { overflow: hidden }` と SVG の `overflow="hidden"` で抑える。

---

## 5. デプロイ後の確認 URL

| 確認 | URL / コマンド |
|------|----------------|
| API | `curl -sf https://api.vanzai-portal.com/api/health` |
| admin favicon | `https://vanzai-portal.com/favicon.svg?v=3` |
| admin 版 | ログイン画面 `Ver.X.Y.Z` |
| staff | `https://staff.vanzai-portal.com/` |

ブラウザキャッシュが残る場合はスーパーリロード（Ctrl+Shift+R）。
