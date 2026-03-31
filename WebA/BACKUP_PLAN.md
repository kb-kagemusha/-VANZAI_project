# バックアップ機能 計画書

> 作成日: 2026-03-11  
> 最終更新: 2026-03-11（レビュー反映）  
> 目的: 他の AI アシスタントに相談する際の参考資料として利用

---

## 1. 現在のシステム構成

### サーバー
| 項目 | 値 |
|---|---|
| VPS | `220.158.19.143`（Linux） |
| ディスク | 48GB（使用 4.2GB / 空き 44GB） |
| アプリパス | `/opt/mykey/` |
| サービス | `mykey.service`（systemd） |
| Web サーバー | Nginx → app_server.py（Python 3.12.3, ポート8080） |
| ドメイン | `bookstore-hopping.com`（HTTPS, Let's Encrypt） |
| SSH鍵 | ローカル PC の `$env:USERPROFILE\.ssh\vps_key` |
| cron | 現在なし（未設定） |
| タイムゾーン | `Asia/Tokyo`（JST）— cron で直接 JST 時刻を指定可能 |
| Python 依存 | 標準ライブラリのみ（外部パッケージなし） |
| SQLite journal_mode | `delete`（WAL ではない。WAL/SHM ファイルの考慮は不要） |

### バックアップ対象

| 対象 | パス | 現在のサイズ | 説明 |
|---|---|---|---|
| **SQLite DB** | `/opt/mykey/shared_reports.db` | **396KB** | 全データの本体。最重要 |
| **レシート画像** | `/opt/mykey/uploads/` | **37MB（115ファイル）** | ユーザーがアップロードしたJPG |
| **アプリコード** | `/opt/mykey/app_server.py` 等 | 数百KB | ローカル PC にも同一コピーあり |
| **サーバー設定** | systemd / Nginx / SSL | — | VPS 再構築時に必要（後述） |

### DB テーブル一覧とレコード数（2026-03-11 時点）

| テーブル | レコード数 | 内容 |
|---|---|---|
| `reports` | 160 | 報告データ（最重要） |
| `audit_logs` | 732 | 操作ログ |
| `member_schedules` | 460 | メンバー予定 |
| `leader_assignments` | 124 | リーダー指名 |
| `members` | 56 | メンバー情報 |
| `assignment_notes` | 40 | 指名メモ |
| `member_profiles` | 20 | プロフィール |
| `teams` | 5 | チーム |

### 既存の安全装置
- `reports` テーブルにはソフトデリート機能あり（`deleted_at` カラム）
- 削除操作は `deletions` テーブルに履歴を保存し、undo（巻き戻し）可能
- ただし **DB ファイル自体の破損・誤操作** には対処できない

### VPS 再構築時に必要なサーバー設定

週次フルバックアップに含めるか、別途記録として保管する。

| 対象 | パス / 内容 |
|---|---|
| systemd ユニット | `/etc/systemd/system/mykey.service` |
| Nginx サイト設定 | `/etc/nginx/sites-enabled/bookstore-hopping.com` |
| SSL 証明書管理 | Let's Encrypt（Certbot で自動更新） |
| Python バージョン | 3.12.3（標準ライブラリのみ、requirements.txt 不要） |
| 環境変数 | `LEADER_PASS` — mykey.service 内で設定 |

> **注**: `.env` ファイルは存在しない。秘密情報は systemd の `Environment=` で管理。

---

## 2. バックアップで守りたいリスク

| リスク | 深刻度 | 現在の対策 |
|---|---|---|
| 報告データの誤削除（一括削除など） | **高** | ソフトデリート＋undo あり |
| DB ファイル自体の破損・消失 | **致命的** | **なし** |
| uploads/ 画像の消失 | **高** | **なし** |
| コードの誤デプロイで動かなくなる | 中 | ローカルにコピーあり |
| VPS ごと障害（ディスク障害等） | 致命的 | **なし** |

---

## 3. 提案するバックアップ方式

### 方針
- **シンプルに**：追加の外部サービスやツールは最小限にする
- **自動で**：cron で定期実行し、人間が忘れても動く
- **二重に**：VPS 内ローカルバックアップ ＋ VPS 外への自動退避
- **検証付き**：ファイルがあるだけでなく、SQLite の整合性まで確認して成功とする

### 3-A. VPS 内の自動バックアップ（cron）

```
/opt/mykey/backups/
├── daily/
│   ├── shared_reports_2026-03-11.db
│   ├── shared_reports_2026-03-10.db
│   ├── ...（直近7日分を保持、古いものは自動削除）
│   └── uploads_2026-03-11.tar.gz
└── weekly/
    ├── full_backup_2026-03-09.tar.gz （DB + uploads + コード + サーバー設定）
    └── ...（直近4週分を保持）
```

| 項目 | 内容 |
|---|---|
| **頻度** | 日次（毎日 AM 3:00 JST） ＋ 週次（毎週日曜 AM 4:00 JST） |
| **日次** | SQLite の `.backup` コマンドで安全にコピー ＋ `PRAGMA quick_check` で検証 ＋ uploads の tar.gz |
| **週次** | DB + uploads + コード + サーバー設定一式をフルバックアップ ＋ `PRAGMA integrity_check` |
| **保持期間** | 日次: 7日 / 週次: 4週間 |
| **推定容量** | 日次 7日分 ≒ 約 300MB / 週次 4週分 ≒ 約 200MB / 合計 約 500MB |

#### なぜ SQLite の `.backup` を使うか
- `cp` でコピーすると、書き込み中のDBが不整合状態でコピーされる恐れがある
- `sqlite3 ... ".backup ..."` はライブ DB に対しても実行でき、ソース DB は読み取り時だけロックされるため安全

#### バックアップ成功条件

「ファイルが存在する」だけでは成功とみなさない。以下すべてを満たして成功とする。

| 条件 | 日次 | 週次 |
|---|---|---|
| DB バックアップファイルが生成された | ✅ | ✅ |
| `PRAGMA quick_check` が `ok` を返す | ✅ | — |
| `PRAGMA integrity_check` が `ok` を返す | — | ✅ |
| 主要テーブルの `SELECT COUNT(*)` が 0 ではない | ✅ | ✅ |
| uploads tar.gz が生成され、サイズが 0 でない | ✅ | ✅ |
| フルバックアップ tar.gz にコード・設定が含まれる | — | ✅ |
| いずれかの条件が失敗した場合は exit 1 | ✅ | ✅ |

#### バックアップスクリプト案（VPS 上 `/opt/mykey/backup.sh`）

```bash
#!/bin/bash
set -euo pipefail
umask 077

APP_DIR="/opt/mykey"
BACKUP_DIR="$APP_DIR/backups"
DAILY_DIR="$BACKUP_DIR/daily"
WEEKLY_DIR="$BACKUP_DIR/weekly"
LOCK_FILE="$BACKUP_DIR/backup.lock"
TODAY=$(date +%F)
NOW=$(date +%F_%H%M%S)
DOW=$(date +%u)  # 1=月〜7=日

mkdir -p "$DAILY_DIR" "$WEEKLY_DIR"

# ── 二重実行防止 ──
exec 9>"$LOCK_FILE"
flock -n 9 || { echo "[$(date)] ERROR: backup already running" >&2; exit 1; }

# ── 日次バックアップ ──

# DB（一時ファイルに .backup → 検証OK後に正式名へ mv）
DB_TMP="$DAILY_DIR/shared_reports_${TODAY}.db.tmp"
DB_FINAL="$DAILY_DIR/shared_reports_${TODAY}.db"

sqlite3 "$APP_DIR/shared_reports.db" <<EOF
.timeout 5000
.backup $DB_TMP
EOF

# 整合性チェック（日次: quick_check）
sqlite3 "$DB_TMP" "PRAGMA quick_check;" | grep -qx "ok" \
  || { echo "[$(date)] ERROR: quick_check failed" >&2; rm -f "$DB_TMP"; exit 1; }

# 主要テーブルの存在確認（reports が 0 件なら異常）
RCOUNT=$(sqlite3 "$DB_TMP" "SELECT COUNT(*) FROM reports;")
[ "$RCOUNT" -gt 0 ] \
  || { echo "[$(date)] ERROR: reports count is 0" >&2; rm -f "$DB_TMP"; exit 1; }

mv "$DB_TMP" "$DB_FINAL"

# uploads（tar.gz、一時ファイル→検証→mv）
UP_TMP="$DAILY_DIR/uploads_${TODAY}.tar.gz.tmp"
UP_FINAL="$DAILY_DIR/uploads_${TODAY}.tar.gz"

tar czf "$UP_TMP" -C "$APP_DIR" uploads/
test -s "$UP_TMP" \
  || { echo "[$(date)] ERROR: uploads tar is empty" >&2; rm -f "$UP_TMP"; exit 1; }
mv "$UP_TMP" "$UP_FINAL"

# 7日より古い日次バックアップを削除
find "$DAILY_DIR" -type f -name '*.db' -mtime +7 -delete
find "$DAILY_DIR" -type f -name '*.tar.gz' -mtime +7 -delete

# ── 週次バックアップ（日曜のみ） ──
if [ "$DOW" = "7" ]; then
  FULL_TMP="$WEEKLY_DIR/full_backup_${NOW}.tar.gz.tmp"
  FULL_FINAL="$WEEKLY_DIR/full_backup_${NOW}.tar.gz"

  # コード + DB + uploads + サーバー設定
  tar czf "$FULL_TMP" \
    -C "$APP_DIR" shared_reports.db uploads/ app_server.py \
    mobile-report-app.html leader.html flow-data.json \
    -C / etc/systemd/system/mykey.service \
    etc/nginx/sites-enabled/bookstore-hopping.com

  test -s "$FULL_TMP" \
    || { echo "[$(date)] ERROR: weekly tar is empty" >&2; rm -f "$FULL_TMP"; exit 1; }
  mv "$FULL_TMP" "$FULL_FINAL"

  # 週次は integrity_check（より厳密）
  sqlite3 "$DB_FINAL" "PRAGMA integrity_check;" | grep -qx "ok" \
    || echo "[$(date)] WARNING: integrity_check failed on daily DB" >&2

  # 28日より古い週次バックアップを削除
  find "$WEEKLY_DIR" -type f -name '*.tar.gz' -mtime +28 -delete
fi

echo "[$(date)] Backup completed: $TODAY (reports=$RCOUNT)"
```

**スクリプトの設計ポイント:**

| 対策 | 理由 |
|---|---|
| `umask 077` | バックアップファイルの権限を 600 に制限（個人情報保護） |
| `flock` | cron 実行と手動実行の競合を防止 |
| `.tmp` → `mv` | 書き込み途中の不完全ファイルを防ぐ（原子的リネーム） |
| `.timeout 5000` | DB ビジー時に 5 秒待機してリトライ |
| `PRAGMA quick_check` | バックアップ DB が読める＋整合性 OK であることを確認 |
| `SELECT COUNT(*)` | テーブルが空でないことを確認（空ファイル検知） |
| 失敗時 `exit 1` | 異常終了コードでエラーを明確に |

#### cron 登録

```bash
# VPS は Asia/Tokyo なので JST 時刻をそのまま指定
0 3 * * * /opt/mykey/backup.sh >> /opt/mykey/backups/backup.log 2>&1
```

> **補足**: 将来的に systemd timer への移行も可能（`Persistent=true` で停止中の取り逃し補完ができる等の利点がある）。  
> ただし現時点では cron で十分。バックアップ本体を `backup.sh` に分離しているため、実行器の差し替えは容易。

#### backup.log のローテーション

ログが無制限に肥大化しないよう、定期的に切り詰める。

```bash
# cron に追加（月初に実行）
0 4 1 * * tail -500 /opt/mykey/backups/backup.log > /opt/mykey/backups/backup.log.tmp && mv /opt/mykey/backups/backup.log.tmp /opt/mykey/backups/backup.log
```

### 3-B. VPS 外への自動退避（ローカル PC）

**VPS 内バックアップだけでは「本当のバックアップ」ではない。**  
同一ディスク上にあるため、ディスク障害・VPS 破損・乗っ取りで本番 DB と一緒に消える。

VPS 外にコピーを持つことで初めて、致命的障害に対する備えになる。

```powershell
# ローカル PC でバックアップを取得するスクリプト（手動 or タスクスケジューラ）
$date = Get-Date -Format "yyyy-MM-dd"
$dest = "C:\MykeyC\backups\$date"
New-Item -Path $dest -ItemType Directory -Force
scp -i "$env:USERPROFILE\.ssh\vps_key" `
  root@220.158.19.143:/opt/mykey/backups/daily/shared_reports_$date.db `
  root@220.158.19.143:/opt/mykey/backups/daily/uploads_$date.tar.gz `
  $dest/
Write-Host "Backup downloaded to $dest"
```

> **注**: 初回接続時に `known_hosts` への登録を行えば、以降は `-o StrictHostKeyChecking=no` を使う必要はない。接続先検証を飛ばすのはセキュリティ上望ましくない。

#### 自動化（Windows タスクスケジューラ）

上記スクリプトを `C:\MykeyC\scripts\download_backup.ps1` として保存し、タスクスケジューラで毎日実行すれば自動化できる。PC がオフの日はスキップされるが、VPS 側に 7 日分残っている。

### 3-C. リーダー画面からの手動バックアップ — Phase 2

> **この機能は Phase 2 とし、3-A・3-B が安定稼働してから着手する。**

理由：
- 手動バックアップは押し忘れる（自動に劣る）
- UI から叩けるとレート制限・認証不備時のリスクが増える
- cron の `flock` と競合する可能性がある

実装する場合の要件：
- API: `POST /api/backup`（リーダー認証 `_is_leader_authorized()` 必須）
- レート制限（1時間に1回まで）
- 実行中は再実行不可（`flock` と同じロックファイルを使用）
- 監査ログ記録
- まず「最新バックアップ一覧表示」を先に実装し、その後「手動実行」を追加する方がよい

---

## 4. 復旧手順（リストア）

### ケース1: 報告データの誤削除
→ 既存の undo 機能でソフトデリートを巻き戻す（現状で対応可能）

### ケース2: DB ファイルの破損・消失
```bash
# VPS上で実行
systemctl stop mykey.service

# 壊れた現行 DB を退避（原因調査に使える可能性あるため）
cp /opt/mykey/shared_reports.db /opt/mykey/shared_reports.db.broken_$(date +%F_%H%M%S) || true

# バックアップから復元
cp /opt/mykey/backups/daily/shared_reports_YYYY-MM-DD.db /opt/mykey/shared_reports.db

systemctl start mykey.service
```

> **補足**: 現在の journal_mode は `delete` であり、WAL モードではないため `-wal` / `-shm` ファイルの削除は不要。  
> もし将来 WAL モードに変更した場合は、復元後に `rm -f /opt/mykey/shared_reports.db-wal /opt/mykey/shared_reports.db-shm` も実行すること。

### ケース3: uploads/ 画像の消失
```bash
cd /opt/mykey
tar xzf /opt/mykey/backups/daily/uploads_YYYY-MM-DD.tar.gz
```

### ケース4: VPS 障害（全データ消失）
1. 新 VPS を契約し、OS セットアップ
2. Python 3.12 をインストール（外部パッケージ不要）
3. `/opt/mykey/` ディレクトリを作成
4. ローカル PC のバックアップから DB・uploads を配置
5. ローカル PC のコード（app_server.py 等）を scp でデプロイ
6. systemd ユニットファイルを設置し有効化:
   ```bash
   # /etc/systemd/system/mykey.service を作成（週次バックアップに含まれている）
   systemctl daemon-reload
   systemctl enable --now mykey.service
   ```
7. Nginx をインストールし、サイト設定を配置（週次バックアップに含まれている）
8. Certbot で SSL 証明書を再取得:
   ```bash
   certbot --nginx -d bookstore-hopping.com -d www.bookstore-hopping.com
   ```
9. DNS を新 VPS の IP に変更
10. cron（バックアップ）を再設定

---

## 5. 実装の優先順位

| 優先度 | 項目 | 工数感 | 備考 |
|---|---|---|---|
| **1（必須）** | VPS 内自動バックアップ（3-A: スクリプト + cron） | 小 | 誤削除・軽い破損への備え |
| **2（必須）** | VPS 外への自動退避（3-B: ローカル PC への取得） | 小 | VPS 自体の死亡への備え |
| **3（推奨）** | 復旧テストの実施 | 小 | 「戻せる」ことの確認 |
| 4（Phase 2） | リーダー画面からの手動バックアップ（3-C） | 中 | 3-A/B 安定後に着手 |

---

## 6. 技術的な注意点

1. **SQLite のバックアップは必ず `.backup` コマンドを使う**  
   `cp` は書き込み中にファイル不整合のリスクがある。`.backup` はライブ DB に対しても安全に実行できる。

2. **バックアップ成功 ≠ ファイルが存在する**  
   `PRAGMA quick_check` / `integrity_check` で整合性を確認し、主要テーブルの件数が 0 でないことも検証する。

3. **cron のタイムゾーン**  
   VPS は `Asia/Tokyo` なので JST 時刻をそのまま指定可能。UTC 変換は不要。

4. **ディスク容量**  
   現在空き 44GB あり、推定 500MB のバックアップでは問題なし。

5. **uploads/ は増え続ける**  
   現在 37MB / 1 週間ペースなので、月 150MB 程度。年間で約 2GB の見込み。

6. **uploads/ の書き込み方式**  
   現在 `app_server.py` は Base64 デコード済みの `file_bytes` を一括 `write()` で保存している（一時ファイル→rename 方式ではない）。1 回の `write()` でまとまった小さいデータ（最大 2MB）を書くため、バックアップ時に半端なファイルを掴むリスクは低い。

7. **セキュリティ**:
   - バックアップスクリプトは `umask 077` でファイル権限を 600 に制限
   - バックアップディレクトリは `700`
   - SSH 接続で `-o StrictHostKeyChecking=no` は使わない（初回接続時に `known_hosts` 登録する）

---

## 7. 復旧テスト計画

バックアップは **「取ること」より「戻せること」が本体**。  
以下のスケジュールで定期的に復旧テストを実施する。

| 頻度 | 内容 |
|---|---|
| **月1回** | DB バックアップを別名（`/tmp/test_restore.db`）で復元し、`PRAGMA integrity_check` ＋ `SELECT COUNT(*)` で件数確認 |
| **3か月に1回** | VPS 上の新規ディレクトリで app_server.py を起動し、バックアップ DB と uploads でアプリが正常動作するか確認 |
| **半年に1回** | VPS 再構築を想定した手順（ケース4）の読み合わせ・確認 |

---

## 8. 異常時の通知・監視

バックアップは失敗しても普段誰も気づかないのが最も危険。最低限の異常検知を入れる。

### 方式: ステータスファイル ＋ 翌朝確認

バックアップスクリプトの最後に成功フラグファイルを書く:

```bash
# backup.sh の最後に追加
echo "$TODAY OK reports=$RCOUNT" > "$BACKUP_DIR/last_success.txt"
```

確認方法:
- リーダー画面の「バックアップ最終成功日時」表示（Phase 2 でUIに組み込み可能）
- または SSH で `cat /opt/mykey/backups/last_success.txt` を確認

### 将来的な強化（必要に応じて）
- 失敗時のメール通知（`msmtp` や `sendmail` 等）
- 外部監視サービス（UptimeRobot の heartbeat 等）

---

## 9. 相談したいポイント

この計画書を持って他のAIに相談する際、以下のポイントについて意見を聞くとよい：

- [ ] バックアップ頻度（日次で十分か？半日ごとが必要か？）
- [ ] 保持日数（日次7日・週次4週で十分か？）
- [ ] VPS外バックアップの自動化をさらに強化すべきか（S3 等の外部ストレージ）
- [ ] 異常通知の方式（メール vs 外部監視 vs ステータスファイルで十分か）
- [ ] 復旧テスト頻度は適切か

---

## 10. レビューで検討済み・見送った項目

| 項目 | 判断 | 理由 |
|---|---|---|
| WAL/SHM ファイル対応 | 不要 | 現在 `journal_mode=delete`。WAL に変更した場合は復旧手順を更新する |
| バックアップ専用 SSH ユーザー | 見送り | 現在の規模（個人開発・少人数チーム）ではオーバー |
| systemd timer への移行 | 将来検討 | cron で十分。スクリプト分離済みのため移行は容易 |
| バックアップの暗号化 | 将来検討 | VPS 内保管は同一サーバーなので暗号化の効果が限定的。外部退避を暗号化する段階で再検討 |
| uploads の atomic rename 保存 | 記録のみ | 現状 2MB 以下の一括 write で実害は極めて低い。将来のリファクタ時に検討 |
