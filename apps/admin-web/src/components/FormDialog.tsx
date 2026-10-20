import type { ReactNode } from "react";
import { ProfileDialog } from "./ProfileDialog";

/** Shared record form: the list only contains an action button, never a resident form. */
export function FormDialog({ open, title, busy = false, size = "wide", onClose, children }: {
  open: boolean; title: string; busy?: boolean; size?: "wide" | "compact"; onClose: () => void; children: ReactNode;
}) {
  if (!open) return null;
  return <ProfileDialog title={title} className={`record-dialog record-dialog--${size}`} onClose={() => { if (!busy) onClose(); }}>
    <div className="record-form-dialog page-stack" aria-busy={busy}>{children}</div>
  </ProfileDialog>;
}
