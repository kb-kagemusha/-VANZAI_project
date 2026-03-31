# セキュリティ診断・修正ログ

## 実施日: 2026-03-03

### 診断対象ファイル

| ファイル | 種別 |
|---------|------|
| `app_server.py` | Python APIサーバー |
| `mobile-report-app.html` | フロントエンド（Vanilla JS/CSS） |
| `leader.html` | リーダー用ダッシュボード（Basic Auth保護） |

---

## 検出した問題と対処

### [S1] リクエストボディサイズ無制限 — **高** 🔴 → 修正済み

**問題**  
`_read_json()` で `Content-Length` ヘッダをそのまま信頼し、最大サイズ制限がなかった。  
攻撃者が数GBの `Content-Length` を送信することでサーバーのメモリを枯渇させる可能性があった。

**修正内容** (`app_server.py`)  
- リクエストボディの最大サイズを **1MB** に制限 (`_MAX_BODY_BYTES = 1 * 1024 * 1024`)
- `Content-Length` ヘッダが不正な値（非数値等）の場合、`ValueError` を catch し `length = 0` にフォールバック

```python
_MAX_BODY_BYTES = 1 * 1024 * 1024

def _read_json(self):
    try:
        length = int(self.headers.get("Content-Length", "0"))
    except (ValueError, TypeError):
        length = 0
    if length > self._MAX_BODY_BYTES:
        raise ValueError(f"Request body too large ({length} bytes, max {self._MAX_BODY_BYTES})")
    ...
```

---

### [S2] 例外内部情報のクライアント漏洩 — **高** 🔴 → 修正済み

**問題**  
全 POST/DELETE ハンドラで `except Exception as ex: str(ex)` を使い、生の例外メッセージをクライアントにそのまま返していた。  
スタックトレース・ファイルパス・DBスキーマ情報等が漏洩するリスクがあった。

**修正内容** (`app_server.py`)  
- `POST /api/teams`、`POST /api/reports`、`POST /api/reports/delete`、`POST /api/deletions/undo` の全ハンドラで汎用メッセージに変更

```python
# 修正前
except Exception as ex:
    return self._send_json(500, {"error": str(ex)})

# 修正後
except Exception:
    return self._send_json(500, {"error": "internal server error"})
```

---

### [S3] セキュリティレスポンスヘッダの欠如 — **中** 🟠 → 修正済み

**問題**  
JSONレスポンスに以下のセキュリティヘッダが含まれていなかった。

| ヘッダ | リスク（欠如時） |
|--------|----------------|
| `X-Content-Type-Options: nosniff` | ブラウザのMIMEスニッフィングによるコンテンツタイプ偽装 |
| `X-Frame-Options: DENY` | Clickjacking（クリックジャッキング） |
| `Cache-Control: no-store` | プロキシ・ブラウザキャッシュへの機密データ残存 |
| `Referrer-Policy: no-referrer` | リファラ経由の情報漏洩 |

**修正内容** (`app_server.py` — `_send_json` メソッド)  
全APIレスポンスに上記4ヘッダを追加。

---

### [S4] X-Actor ヘッダの無制限受け入れ — **中** 🟠 → 修正済み

**問題**  
`X-Actor` ヘッダの値をそのままDBに保存しており、最大長・制御文字の制限がなかった。  
非常に長い文字列や制御文字を含む値がDBに保存され得た。

**修正内容** (`app_server.py` — `_actor` メソッド)
- 制御文字（非printable文字）を除去
- 最大 **64文字** に切り捨て

```python
_ACTOR_MAX_LEN = 64

def _actor(self):
    raw = (self.headers.get("X-Actor", "") or "").strip()
    raw = "".join(c for c in raw if c.isprintable())
    actor = raw[:self._ACTOR_MAX_LEN]
    return actor if actor else "unknown"
```

---

### [S5] フィールド長バリデーションの欠如 — **中** 🟠 → 修正済み

**問題**  
`POST /api/reports` でフィールドの最大長チェックがなく、例えば `comment` に数MBのテキストを送信してDBに保存できた。

**修正内容** (`app_server.py` — `POST /api/reports` ハンドラ)  
各フィールドに最大長を設定し、超過時は `400` を返す。

| フィールド | 最大長 |
|-----------|--------|
| id | 128 |
| createdAt / purchaseAt | 40 |
| team | 60 |
| resultType | 80 |
| reportNo | 20 |
| storeName | 200 |
| storeAddress | 400 |
| receiptFileName | 256 |
| comment | 1,000 |

また `POST /api/teams` でチーム名の最大 **60文字** 制限を追加。  
`POST /api/reports/delete` で一度に削除できるIDを最大 **500件** に制限。  
`POST /api/deletions/undo` で `opId` を最大 **128文字** に切り捨て。

---

### [S6] CSP `script-src 'unsafe-inline'` — **低** 🟡 → 対処方針を決定

**問題**  
`mobile-report-app.html` の CSP メタタグで `script-src 'unsafe-inline'` を許可している。  
インラインスクリプトは XSS の主要な攻撃経路であり、理想的には無効化すべきである。

**現状と判断**  
本アプリは全JS・CSSを単一HTMLファイルにインラインで記述する設計を採用しており、`'unsafe-inline'` を除去するには外部ファイル分離という大規模な再設計が必要となる。  
現バージョンでは以下の点で実質的なリスクを低減している:

- すべてのDOM操作は `textContent` / `createElement` ベースで、ユーザーデータを `innerHTML` に渡していない
- APIレスポンスは `JSON.parse` 後にDOM APIで描画しており、HTML挿入がない
- サーバーは社内LAN限定での運用を想定

**今後の対応策**（将来のリファクタリング時）  
JS を外部 `.js` ファイルに分離した上で `script-src 'self'` へ変更することを推奨する。

---

## 変更サマリー

| ID | 重大度 | 対象ファイル | 修正箇所 | ステータス |
|----|--------|-------------|---------|-----------|
| S1 | 高 | app_server.py | `_read_json()` | ✅ 修正済み |
| S2 | 高 | app_server.py | POST/DELETE 全ハンドラ | ✅ 修正済み |
| S3 | 中 | app_server.py | `_send_json()` | ✅ 修正済み |
| S4 | 中 | app_server.py | `_actor()` | ✅ 修正済み |
| S5 | 中 | app_server.py | POST /api/reports, /api/teams | ✅ 修正済み |
| S6 | 低 | mobile-report-app.html | CSP `script-src` | 📝 将来対応 |
| NEW-S7 | 中 | mobile-report-app.html | 書店検索結果 `btn.innerHTML` | ✅ 修正済み |
| NEW-S8 | 中 | leader.html | 集計/一覧 `innerHTML` (3箇所) | ✅ 修正済み |

---

## HTMLフロントエンドの評価（問題なし）

以下については診断の結果、**問題なし**と判断:

| 確認箇所 | 結果 |
|---------|------|
| `eval()` / `new Function()` / `document.write()` 使用 | なし |
| `safeText()` による入力サニタイズ | 全入力フィールドで適用済み |
| APIリクエストパラメータの `encodeURIComponent` 適用 | 全クエリパラメータで適用済み |
| `X-Actor` ヘッダへの `encodeURIComponent` 適用 | 適用済み（ISO-8859-1エラー対応で変更） |
| Google Maps URL のホスト/パス検証 | 実装済み (`ALLOWED_HOSTS` チェック) |

---

## 追加診断（2回目）— 実施日: 2026-03-04

新機能追加（書店検索・氏名欄表示等）を受けて、追加セキュリティ診断を実施。

### [NEW-S7] 書店検索結果の Reflected XSS — **中** 🟡 → 修正済み

**問題**  
`mobile-report-app.html` の書店名＋都道府県検索機能（Nominatim API使用）で、  
API レスポンスの店舗名をそのまま `btn.innerHTML` に代入していた。  
外部APIが悪意ある HTML を返した場合、XSS が成立する可能性があった。

**修正内容** (`mobile-report-app.html` L2052付近)

```javascript
// 修正前
btn.innerHTML = `<span class="store-name">${shortName}</span>...`;

// 修正後（textContent / DOM操作に変更）
const nameSpan = document.createElement('span');
nameSpan.className = 'store-name';
nameSpan.textContent = shortName;       // ← XSSの根本原因を排除
btn.appendChild(nameSpan);
// (以降の要素も同様に appendChild で構築)
```

---

### [NEW-S8] リーダー画面の Stored XSS — **中** 🟡 → 修正済み

**問題**  
`leader.html` で DB から取得したデータ（チーム名・氏名・報告番号・結果区分・店舗名・actorキー）を  
エスケープなしで `innerHTML` テンプレートリテラルに直接埋め込んでいた。  
悪意あるデータが DB に登録された場合、リーダー画面閲覧時に XSS が成立する可能性があった（Stored XSS）。

**該当箇所** (修正前):

| 行 | コード |
|----|--------|
| L288 | `box.innerHTML = \`<div class="num">${v}</div><div class="lbl">${k}</div>\`` (resultType集計) |
| L295 | 同パターン (actor集計) |
| L314 | `tr.innerHTML = \`<td>${safeText(r.team)}</td>...\`` (一覧テーブル全列) |

> ※ `safeText()` は `.trim()` のみで HTML エスケープを行わない関数だった。

**修正内容** (`leader.html`)

1. `escapeHtml()` 関数を追加（`safeText()` 直後に挿入）:

```javascript
function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
```

2. L288・L295 の `${k}` を `${escapeHtml(k)}` に変更  
3. L314 の全フィールドを `safeText()` → `escapeHtml()` に変更（`formatDateTime` の出力も `escapeHtml` でラップ）

---

## 動作確認

修正後の構文チェック: ✅ `python -m py_compile app_server.py` — エラーなし  
テスト実施日: 2026-03-03  
追加修正デプロイ: 2026-03-04（`mobile-report-app.html`、`leader.html`）
