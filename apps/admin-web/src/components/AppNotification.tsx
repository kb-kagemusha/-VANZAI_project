import { useEffect, useId, useRef, type CSSProperties } from "react";
import { createPortal } from "react-dom";

export type AppNotificationTone = "error" | "warning" | "success" | "info";

export type AppNotificationState = {
  tone: AppNotificationTone;
  title: string;
  message: string;
  detail?: string;
  confirmLabel?: string;
};

type AppNotificationProps = AppNotificationState & {
  open: boolean;
  onClose: () => void;
};

const TONE_META: Record<
  AppNotificationTone,
  { label: string; icon: JSX.Element; accent: string; soft: string }
> = {
  error: {
    label: "エラー",
    accent: "#b42318",
    soft: "rgba(180, 35, 24, 0.12)",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="M12 8.25v4.5m0 3h.008M10.29 3.86 1.82 18a1.5 1.5 0 0 0 1.29 2.25h17.78a1.5 1.5 0 0 0 1.29-2.25L13.71 3.86a1.5 1.5 0 0 0-2.58 0Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  warning: {
    label: "注意",
    accent: "#b54708",
    soft: "rgba(181, 71, 8, 0.12)",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="M12 7.5v5.25M12 16.8h.007M10.29 3.86 1.82 18a1.5 1.5 0 0 0 1.29 2.25h17.78a1.5 1.5 0 0 0 1.29-2.25L13.71 3.86a1.5 1.5 0 0 0-2.58 0Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  success: {
    label: "完了",
    accent: "#2f6b3f",
    soft: "rgba(47, 107, 63, 0.12)",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="m8.8 12.45 2.2 2.2 4.8-5.1M12 3.5a8.5 8.5 0 1 1 0 17 8.5 8.5 0 0 1 0-17Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  info: {
    label: "お知らせ",
    accent: "#1d4ed8",
    soft: "rgba(29, 78, 216, 0.12)",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="M12 8.25h.008v.008H12V8.25Zm0 3.75V17m8.25-4.25a8.25 8.25 0 1 1-16.5 0 8.25 8.25 0 0 1 16.5 0Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
};

export function AppNotification({
  open,
  tone,
  title,
  message,
  detail,
  confirmLabel = "閉じる",
  onClose,
}: AppNotificationProps) {
  const titleId = useId();
  const messageId = useId();
  const confirmButtonRef = useRef<HTMLButtonElement>(null);
  const meta = TONE_META[tone];

  useEffect(() => {
    if (!open) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    confirmButtonRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return createPortal(
    <div className="app-notification-backdrop" role="presentation" onClick={onClose}>
      <div
        className={`app-notification-card app-notification-card--${tone}`}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={messageId}
        style={
          {
            "--notification-accent": meta.accent,
            "--notification-soft": meta.soft,
          } as CSSProperties
        }
        onClick={(event) => event.stopPropagation()}
      >
        <div className="app-notification-icon" aria-hidden="true">
          {meta.icon}
        </div>
        <div className="app-notification-body">
          <p className="app-notification-eyebrow">{meta.label}</p>
          <h2 id={titleId} className="app-notification-title">
            {title}
          </h2>
          <p id={messageId} className="app-notification-message">
            {message}
          </p>
          {detail ? <p className="app-notification-detail">{detail}</p> : null}
        </div>
        <div className="app-notification-actions">
          <button
            ref={confirmButtonRef}
            type="button"
            className="primary-button app-notification-button"
            onClick={onClose}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
