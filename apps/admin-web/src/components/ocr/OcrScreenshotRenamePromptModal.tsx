import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import type { ScreenshotRenamePromptPayload } from "../../lib/ocr/paygateScreenshotImageRename";

export function OcrScreenshotRenamePromptModal({
  payload,
  busy,
  onApply,
  onLater,
}: {
  payload: ScreenshotRenamePromptPayload | null;
  busy?: boolean;
  onApply: (filename: string) => Promise<void> | void;
  onLater: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draftFilename, setDraftFilename] = useState("");

  useEffect(() => {
    if (!payload) {
      setEditing(false);
      setDraftFilename("");
      return;
    }
    setEditing(false);
    setDraftFilename(payload.suggestedFilename);
  }, [payload]);

  if (!payload) {
    return null;
  }

  const handleApply = async (filename: string) => {
    const next = filename.trim();
    if (!next) {
      return;
    }
    await onApply(next);
  };

  return createPortal(
    <div
      className="ocr-rename-prompt-backdrop"
      role="presentation"
      onClick={() => {
        if (!busy) {
          onLater();
        }
      }}
    >
      <div
        className="ocr-rename-prompt-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ocr-rename-prompt-title"
        onClick={(event) => event.stopPropagation()}
      >
        <h3 id="ocr-rename-prompt-title">ファイル名を整理しますか？</h3>
        <p className="ocr-rename-prompt-lead">同一画像の取引がすべて確定しました。</p>
        {payload.remainingCount > 0 ? (
          <p className="ocr-rename-prompt-meta">ほか {payload.remainingCount} 件の画像も名前整理が必要です。</p>
        ) : null}
        <dl className="ocr-rename-prompt-names">
          <div>
            <dt>現在の名前</dt>
            <dd title={payload.currentFilename}>{payload.currentFilename}</dd>
          </div>
          <div>
            <dt>推奨ファイル名</dt>
            <dd title={payload.suggestedFilename}>{payload.suggestedFilename}</dd>
          </div>
        </dl>
        {editing ? (
          <label className="ocr-rename-prompt-edit">
            <span>ファイル名</span>
            <input
              type="text"
              value={draftFilename}
              disabled={busy}
              onChange={(event) => setDraftFilename(event.target.value)}
            />
          </label>
        ) : null}
        <div className="ocr-rename-prompt-actions">
          {editing ? (
            <>
              <button
                type="button"
                className="ghost-button"
                disabled={busy}
                onClick={() => {
                  setDraftFilename(payload.suggestedFilename);
                  setEditing(false);
                }}
              >
                取消
              </button>
              <button
                type="button"
                className="primary-button"
                disabled={busy || !draftFilename.trim()}
                onClick={() => void handleApply(draftFilename)}
              >
                {busy ? "変更中..." : "この名前に変更"}
              </button>
            </>
          ) : (
            <>
              <button type="button" className="ghost-button" disabled={busy} onClick={onLater}>
                後で
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={busy}
                onClick={() => setEditing(true)}
              >
                名前を編集
              </button>
              <button
                type="button"
                className="primary-button"
                disabled={busy}
                onClick={() => void handleApply(payload.suggestedFilename)}
              >
                {busy ? "変更中..." : "この名前に変更"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
