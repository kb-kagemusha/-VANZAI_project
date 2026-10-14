import {
  useEffect,
  useId,
  useRef,
  useState,
  useSyncExternalStore,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { createPortal } from "react-dom";

import "../styles/app-dialog.css";

export type AppDialogTone = "primary" | "danger";

export type ConfirmAppOptions = {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: AppDialogTone;
};

export type AlertAppOptions = {
  title: string;
  message: string;
  confirmLabel?: string;
};

export type PromptAppOptions = {
  title: string;
  message: string;
  defaultValue?: string;
  confirmLabel?: string;
  cancelLabel?: string;
};

type AlertRequest = {
  id: number;
  kind: "alert";
  title: string;
  message: string;
  confirmLabel: string;
  resolve: () => void;
};

type ConfirmRequest = {
  id: number;
  kind: "confirm";
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  tone: AppDialogTone;
  resolve: (value: boolean) => void;
};

type PromptRequest = {
  id: number;
  kind: "prompt";
  title: string;
  message: string;
  defaultValue: string;
  confirmLabel: string;
  cancelLabel: string;
  resolve: (value: string | null) => void;
};

type DialogRequest = AlertRequest | ConfirmRequest | PromptRequest;

let nextId = 1;
let active: DialogRequest | null = null;
const pending: DialogRequest[] = [];
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot() {
  return active;
}

function enqueue(request: DialogRequest) {
  if (active) {
    pending.push(request);
    return;
  }
  active = request;
  emit();
}

function settle() {
  active = pending.shift() ?? null;
  emit();
}

export function alertApp(options: AlertAppOptions): Promise<void> {
  return new Promise((resolve) => {
    enqueue({
      id: nextId++,
      kind: "alert",
      title: options.title,
      message: options.message,
      confirmLabel: options.confirmLabel ?? "OK",
      resolve,
    });
  });
}

export function confirmApp(options: ConfirmAppOptions): Promise<boolean> {
  return new Promise((resolve) => {
    enqueue({
      id: nextId++,
      kind: "confirm",
      title: options.title,
      message: options.message,
      confirmLabel: options.confirmLabel ?? "OK",
      cancelLabel: options.cancelLabel ?? "キャンセル",
      tone: options.tone ?? "primary",
      resolve,
    });
  });
}

export function promptApp(options: PromptAppOptions): Promise<string | null> {
  return new Promise((resolve) => {
    enqueue({
      id: nextId++,
      kind: "prompt",
      title: options.title,
      message: options.message,
      defaultValue: options.defaultValue ?? "",
      confirmLabel: options.confirmLabel ?? "OK",
      cancelLabel: options.cancelLabel ?? "キャンセル",
      resolve,
    });
  });
}

function focusInitial(
  request: DialogRequest,
  confirmButton: HTMLButtonElement | null,
  cancelButton: HTMLButtonElement | null,
  input: HTMLInputElement | null,
) {
  if (request.kind === "prompt") {
    input?.focus();
    input?.select();
    return;
  }
  if (request.kind === "confirm" && request.tone === "danger") {
    cancelButton?.focus();
    return;
  }
  confirmButton?.focus();
}

function AppDialogView({ request }: { request: DialogRequest }) {
  const titleId = useId();
  const messageId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const settledRef = useRef(false);
  const [promptValue, setPromptValue] = useState(request.kind === "prompt" ? request.defaultValue : "");
  const promptValueRef = useRef(promptValue);
  promptValueRef.current = promptValue;

  const finishRef = useRef<(action: "confirm" | "cancel") => void>(() => {});
  finishRef.current = (action) => {
    if (settledRef.current) return;
    settledRef.current = true;
    if (request.kind === "alert") {
      request.resolve();
    } else if (request.kind === "confirm") {
      request.resolve(action === "confirm");
    } else {
      request.resolve(action === "confirm" ? promptValueRef.current : null);
    }
    settle();
  };

  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    focusInitial(request, confirmRef.current, cancelRef.current, inputRef.current);

    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      finishRef.current("cancel");
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      document.body.style.overflow = previousOverflow;
      previous?.focus();
    };
  }, [request]);

  const onPanelKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Tab") return;
    const panel = panelRef.current;
    if (!panel) return;
    const focusable = Array.from(
      panel.querySelectorAll<HTMLElement>("button:not([disabled]), input:not([disabled]), textarea:not([disabled])"),
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  const danger = request.kind === "confirm" && request.tone === "danger";

  return (
    <div className="app-dialog-backdrop" onClick={() => finishRef.current("cancel")}>
      <div
        ref={panelRef}
        className="app-dialog-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={messageId}
        onClick={(event) => event.stopPropagation()}
        onKeyDown={onPanelKeyDown}
      >
        <h2 id={titleId} className="app-dialog-title">
          {request.title}
        </h2>
        <p id={messageId} className="app-dialog-message">
          {request.message}
        </p>
        {request.kind === "prompt" ? (
          <input
            ref={inputRef}
            className="app-dialog-input"
            value={promptValue}
            onChange={(event) => setPromptValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                finishRef.current("confirm");
              }
            }}
            aria-labelledby={messageId}
          />
        ) : null}
        <div className="app-dialog-actions">
          {request.kind === "alert" ? null : (
            <button
              ref={cancelRef}
              type="button"
              className="app-dialog-button app-dialog-button-ghost"
              onClick={() => finishRef.current("cancel")}
            >
              {request.cancelLabel}
            </button>
          )}
          <button
            ref={confirmRef}
            type="button"
            className={danger ? "app-dialog-button app-dialog-button-danger" : "app-dialog-button app-dialog-button-primary"}
            onClick={() => finishRef.current("confirm")}
          >
            {request.confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export function AppDialogHost() {
  const request = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  if (!request) return null;
  return createPortal(<AppDialogView key={request.id} request={request} />, document.body);
}
