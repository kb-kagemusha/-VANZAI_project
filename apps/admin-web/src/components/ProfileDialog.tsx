import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

export function ProfileDialog({ title, onClose, children, className = "" }: { title: string; onClose: () => void; children: ReactNode; className?: string }) {
  const panel = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const titleId = useId();
  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.defaultPrevented || document.querySelector(".app-dialog-backdrop")) return;
      if (event.key === "Escape") { event.preventDefault(); closeRef.current(); }
      if (event.key !== "Tab") return;
      const items = Array.from(panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],[tabindex="0"]') ?? []).filter((el) => el.getClientRects().length > 0);
      const first = items[0], last = items[items.length - 1];
      if (!first) { event.preventDefault(); panel.current?.focus(); }
      else if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || document.activeElement === panel.current)) { event.preventDefault(); first.focus(); }
    }
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = overflow; if (previous?.isConnected) previous.focus(); };
  }, []);
  return createPortal(<div className="order-create-backdrop"><div className={`order-draft is-modal worker-profile-modal ${className}`} ref={panel} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby={titleId}>
    <header className="order-draft-head"><h3 id={titleId}>{title}</h3><button type="button" className="btn btn-ghost" onClick={onClose}>閉じる</button></header>
    <div className="order-draft-body">{children}</div>
  </div></div>, document.body);
}
