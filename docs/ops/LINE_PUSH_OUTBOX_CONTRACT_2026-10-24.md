# LINE送信予定表の登録契約 v0.1（③-B、2026-10-24）

状態: 実装前の共有契約。0.52.2ではまだ呼び出せない。中止/除外/受付通知の共通部品として、次の変更で実装する。
D-10は採用済み。D-11は未決で、この契約で一部中止の操作を確定しない。

## 登録関数

配置: `src.services.line_push_outbox.enqueue_worker_notice`

```python
enqueue_worker_notice(
    db, *, kind, worker_id, unique_key, text, expires_at,
    context, actor, not_before=None,
) -> EnqueuedNotice
# EnqueuedNotice: id: str, created: bool, status: str
```

- db: 呼出し元のSQLAlchemy Session。中止や回答と同じトランザクションで登録する。関数はcommit/rollbackせず、LINEへ送信しない。業務更新がロールバックされたら登録も残らない。
- kind: 初期対応は `order_cancelled` / `recipient_removed` / `reply_receipt`。通知の停止・再検証・確認要否は種類ごとの共通処理で決める。呼出し元から任意の停止ロジックを渡さない。
- worker_id: 稼働者ID。LINEの宛先IDを業務側で指定しない。送信側が有効な紐付けを検証し、解除・別の紐付けへの変更時は意図しない宛先へ送らない。
- unique_key: 同じ論理通知を識別する文字列。重複制約はkind×worker_id×unique_key。同一内容の再登録は同じid/created=Falseを返し、再送回数や確認状態を初期化しない。同じキーで別内容の登録はエラーにする。
- text: 通知文の保存用コピー。保存後に依頼書を読み直して、別の内容の通知に変えない。
- expires_at: 業務上の送信期限。タイムゾーン付き日時を必須としUTCへ正規化。LINEの再試行キーの有効期間と混同しない。具体的な期限は通知の種類の業務仕様で定める。
- not_before: 最初に送れる日時。省略時は今から。期限後になる指定は拒否する。
- context: 下表の業務参照。送信直前・再試行時の再確認に使う。対象本人/系列/送付行の所属を登録時にも検証する。
- actor: 監査用の実行者。登録と送信試行/結果/確認を監査記録に残す。

| kind | context | 確認ボタン |
|---|---|---|
| order_cancelled | series_id, version_id, event_key | あり。中止済みを理由に通知を止めない |
| recipient_removed | series_id, version_id, event_key | あり。送付先から外れた状態を伝える |
| reply_receipt | delivery_id, outcome | なし。受諾/辞退の受付結果を伝えるだけ |

不明なkind/不足context/所属不整合/期限不正/同一キーの別内容は登録を拒否し、業務更新とともにロールバックする。

## ③-Cの呼出し

```python
from src.services.line_push_outbox import enqueue_worker_notice
from src.services.line_worker import reply_notice_key

notice = enqueue_worker_notice(
    db,
    kind="reply_receipt",
    worker_id=worker.id,
    unique_key=reply_notice_key(delivery.id, outcome),
    text=receipt_text,
    expires_at=receipt_expires_at,
    context={"delivery_id": delivery.id, "outcome": outcome},
    actor="line-web",
)
# 受諾/辞退と同じdb.commit()で保存する。通知失敗で回答を戻さない。
```

直接送信とoutboxの両方を実行しない。切替は新しく確定する回答から行い、移行前の回答をまとめて再登録しない。
既存 `reply_notice_key(送付行ID, 結果)` のUUID5をそのまま維持する。送信側の再試行でも同じUUIDを使用する。
登録した事実、送信が受け付けられた事実、本人の「確認しました」は別に保存する。確認は新条件への受諾を起こさない。

## 共通基盤の公開条件

- 永続化→送信→再試行で、同じ論理通知を二重生成しない。
- 種類ごとに期限・停止条件を毎回再確認する。受付通知は後日の依頼変更だけを理由に別の結果へ変えない。
- 失敗/結果不明/期限切れ/紐付けなし等を、未処理のまま隠さず運営へ表示する。
- LINEへの送信失敗で業務結果は戻さない。送信側はDBロック・試行状態・同じ再試行キーで複数実行の重複を防ぐ。
- 中止/除外通知の未確認者を運営が確認できる。本人以外の確認操作と、再度押したときの重複記録を防ぐ。
- 運営宛て通知（③-D/④）は同じoutbox基盤を使う宛先アダプターを追加する。稼働者IDと運営IDを混同せず、別の送信予定表を作らない。
