# Cursor / Codex 開発フォルダ統合記録（2026-10-21）

## 目的と結果

CursorでのKintone資産整理・開発ルール更新を保全し、通常の開発場所である `C:\AI_Projects\VANZAI_project` に本番最新版のアプリを取り込んだ。ユーザーは作業前にCursorを閉じ、統合と引き継ぎ記録の作成を依頼した。

- 通常使うフォルダ: `C:\AI_Projects\VANZAI_project`
- ブランチ: `feature/2026-03-31-next-work`
- 両アプリの版番号: **0.46.6**（新たな版上げなし）
- 統合前: `a40e201` / 0.39.2。正規originより37コミット遅れていた。
- 取り込んだ本番の起点: `10b00cd`（監査履歴の日本語表示、0.46.6）。
- Cursor整理の保全コミット: `f391b76`。
- 統合コミット: `5957783`（両方の履歴を保持するmerge）。
- `src/` と `apps/` の追跡済みファイルは、取り込んだ `10b00cd` と差分なし。

今回の作業は開発フォルダと文書の統合であり、新たなアプリ改修ではない。DBマイグレーション・本番デプロイ・API再起動は実施しない。本番は前回反映した0.46.6のまま。

## 別worktreeを使用した経緯

監査表示の修正時、元フォルダには多数の未コミット変更・削除と未追跡ファイルがあった。内容を上書きしないため、本番最新版から別worktreeを作成して修正・テスト・push・デプロイした。

その作業場所は `C:\Users\bunya\.codex\worktrees\audit-japanese\VANZAI_project`、ブランチは `codex/audit-japanese`、コミットは `10b00cd`。元フォルダは自動更新されなかった。監査修正の完了報告で、この状態を明示しなかったため、開発場所と本番の版に食い違いが残った。

未コミット変更があることは、更新不能を意味しない。今回は既存変更の内容を確認して先にコミットし、通常のmergeで最新版を取り込んだ。強制リセット、作業の破棄、秘密情報ファイルの上書きは行っていない。

## 保全したCursor側の作業

- 削除扱いのKintone関連64ファイルは全件 `.old/` に存在した。63ファイルは改行を正規化した比較で移動前と内容が一致。残る1ファイルは `.old/kintone/README.md` の案内更新だった。
- `.old/README.md` を含めて追跡し、旧ファイルを復元せずに移動として保存した。アーカイブは現在未使用であり、実行しない。
- README、QUICK_REFERENCE、ファイル一覧、Kintone説明、STATUS、設計書の参照先更新を保持した。
- `scripts/create_3project_test_data.py` は末尾の案内からKintone同期を外した変更だけを保持。今回このスクリプトは実行していない。
- 版番号の分類ルール、入力画面ルール、秘密情報保護ルール、Cursorワークスペースの起動パス修正を保持した。
- DEC-032/033を、後続決定の前に元の内容で復元した。当時の「未適用」「未実施」等は過去の記録であり、現在の状態は後続決定・現行コード・RUNBOOKと合わせて確認する。

## 競合と解消理由

| ファイル | 解消内容 | 理由 |
| --- | --- | --- |
| `.gitignore` | Cursor側の秘密情報保護コメント・`.env`系列除外と、最新版の `line-registration-config.json` 除外を両立 | どちらの保護対象も失わないため |
| `AGENTS.md` | 最新版の作成ボタン色・フォームのポップアップ規則を保持し、Cursor側の秘密情報保護も保持 | 最新版の画面ルールは従来の3項目を包含しているため |
| `docs/decisions/DECISION_LOG.md` | DEC-032/033と、検証入口設定・DEC-034〜061の双方を時系列で接続 | 古い決定を捨てず、後続の変更理由も残すため |

リリースルールと設計書は自動統合された。DEC-032〜061はそれぞれ1件ずつ存在することを確認した。

## 今回コミットに含めなかったもの

以下は既存の内容を保持し、整理コミット・引き継ぎコミットに追加していない。

- `docs/ops/LINE_INTEGRATION_IMPLEMENTATION_PLAN_2026-09-30.md`
- `docs/ops/LINE_WORKER_REGISTRATION_PLAN_2026-10-11.md`
- `artifacts/` の画面確認画像（最新版のignore規則により通常のstatusでは表示されなくなる）
- `output/` の契約書等、`tmp/` の作業成果物、`.work/` の作業ファイル
- `apps/admin-web/src/components/SideNav [conflicted 15].tsx`（エディタの競合コピー。本体のSideNav.tsxと混同しない）

このため、完了後も未追跡ファイルの表示は残る。不要と決めつけて削除したり、`git add -A` で一括追加したりしない。

`.env` と `.env20261006` は存在確認のみ行い、中身の読み取り・変更・Git追加を行っていない。その他の認証設定も今回の統合対象にしていない。

## 保全先と検証

- 元のHEADを指すローカルブランチ: `codex/backup-before-workspace-sync-20261021`
- Cursor整理確定時のローカルブランチ: `codex/cursor-cleanup-preserved-20261021`
- ローカル補助記録: `.work/workspace-sync-20261021/`。元の追跡済み差分パッチ、開始時のstatus/HEAD、秘密情報ファイルを対象外にした未追跡ファイルのハッシュ一覧を保存。外部共有しない。
- 元の未追跡ファイル122件の内容が変わっていないことをハッシュ比較で確認。
- 管理画面・スタッフ画面: 両方 `npm run build` 成功。管理画面には既存のバンドルサイズ警告があるが、ビルドは成功。
- 監査日本語化: `npx playwright test e2e/audit-localization.spec.ts --reporter=line`、3件合格。
- Python関連テスト: `python -m pytest tests/test_audit_search.py tests/test_api_audit_logs.py tests/test_access_management.py tests/test_financial_review_fixes.py tests/test_code_review_regressions.py -q`、72件合格（インメモリSQLite）。
- サンドボックス内では既存venvの起動とTestClient実行が進まなかったため、プロセス制限の外で起動確認・関連テストを実施した。既存venvはPython 3.13.14で起動できた。環境の作り直しは行っていない。
- 競合マーカーなし、`git diff --check` 成功。旧Kintoneスクリプトは実行していない。全テスト・PostgreSQL競合試験・実LINE通信は今回の検証範囲外。

## Cursorで再開するとき

1. `C:\AI_Projects\VANZAI_project` を開き、最初にこの記録と `AGENTS.md`、`.cursor/rules/no-overwrite-secrets.mdc` を読む。
2. `git status --short`、`git log -3 --oneline` と両アプリのpackage.jsonで、統合済み状態を確認する。
3. 元の0.39.2を前提に実装・版番号を戻さない。監査修正のworktreeは今回の修正経緯を確認するための場所であり、通常の開発場所は元フォルダとする。
4. CursorとCodexで同じフォルダの編集・Git操作を同時実行しない。作業開始時にはユーザーと担当を合わせる。
5. 次の機能変更では、既存機能の変更はZ、独立した新業務だけYという現行規則で版を判定する。

### Cursorへ渡す文面

> 開発フォルダの統合が完了しました。`docs/ops/WORKSPACE_SYNC_HANDOVER_2026-10-21.md` を最初に読み、`git status` と `git log` を確認してください。あなたが行ったKintone資産の `.old/` への整理とルール更新は保全済みです。本番0.46.6までの37コミットを取り込み、アプリ実装は本番起点10b00cdと一致しています。未追跡の計画書・契約書・作業成果物・競合コピーは意図的に残しています。一括追加や削除はしないでください。秘密情報ファイルは読まず・上書きせず、次の作業はこの元フォルダで、Codexと同時編集しない状態で再開してください。
