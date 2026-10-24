import { useEffect, useRef, useState } from "react";
import { getVapidPublicKey, registerPushSubscription } from "../api/client";

function urlB64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

function arrayBufferToBase64Url(buffer: ArrayBuffer | null): string {
  if (!buffer) return "";
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function getPlatformHint(): string | null {
  const ua = navigator.userAgent;
  const isIos = /iPhone|iPad|iPod/i.test(ua);
  const isStandalone =
    window.matchMedia?.("(display-mode: standalone)")?.matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true;
  if (isIos && !isStandalone) {
    return "iPhone/iPad の Web Push はホーム画面に追加したアプリからのみ利用できます。Safari の共有メニューから『ホーム画面に追加』して開き直してください。";
  }
  return null;
}

function timeoutAfter<T>(promise: Promise<T>, ms: number, message: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error(message)), ms);
    promise
      .then((v) => { window.clearTimeout(timer); resolve(v); })
      .catch((e) => { window.clearTimeout(timer); reject(e); });
  });
}

export interface PushRegistrationResult {
  permission: NotificationPermission;
  registered: boolean;
  message?: string;
}

export function usePushNotification() {
  const initialized = useRef(false);
  const [isRegistered, setIsRegistered] = useState(false);
  const [lastMessage, setLastMessage] = useState<string | null>(null);
  const [progressMessage, setProgressMessage] = useState<string | null>(null);

  async function doRegister(force = false): Promise<PushRegistrationResult> {
    try {
      if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
        return { permission: Notification.permission, registered: false, message: "このブラウザはプッシュ通知に対応していません。" };
      }
      const hint = getPlatformHint();
      if (hint) return { permission: Notification.permission, registered: false, message: hint };

      setProgressMessage("Service Worker を登録しています...");
      const reg = await timeoutAfter(
        navigator.serviceWorker.register("/sw.js", { scope: "/" }),
        5000, "Service Worker の登録がタイムアウトしました。ページを再読み込みしてください。"
      );

      setProgressMessage("Service Worker の準備を待っています...");
      await timeoutAfter(navigator.serviceWorker.ready, 5000,
        "Service Worker の準備がタイムアウトしました。ページを再読み込みしてください。"
      );

      if (Notification.permission !== "granted") return { permission: Notification.permission, registered: false };

      setProgressMessage("公開鍵を取得しています...");
      const { public_key } = await timeoutAfter(getVapidPublicKey(), 5000,
        "VAPID 公開鍵の取得がタイムアウトしました。通信状態を確認してください。"
      );
      if (!public_key) return { permission: Notification.permission, registered: false, message: "VAPID 公開鍵を取得できませんでした。" };

      const applicationServerKey = urlB64ToUint8Array(public_key);

      setProgressMessage("既存の購読状態を確認しています...");
      const existing = await timeoutAfter(reg.pushManager.getSubscription(), 4000,
        "既存の購読確認がタイムアウトしました。ブラウザを再起動してください。"
      );

      if (existing && force) {
        setProgressMessage("既存の購読を破棄しています...");
        try { await timeoutAfter(existing.unsubscribe(), 4000, "購読解除がタイムアウトしました。"); } catch { /* continue */ }
      }

      let sub = (!force && existing) ? existing : null;
      if (!sub) {
        setProgressMessage("新しいプッシュ購読を作成しています...");
        sub = await timeoutAfter(
          reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey }),
          6000, "プッシュ購読の作成がタイムアウトしました。Chrome のサイト設定と端末通知設定を確認してください。"
        );
      }

      let p256dh = arrayBufferToBase64Url(sub.getKey("p256dh"));
      let auth = arrayBufferToBase64Url(sub.getKey("auth"));
      if (!p256dh || !auth) {
        const json = sub.toJSON();
        p256dh = p256dh || json.keys?.p256dh || "";
        auth = auth || json.keys?.auth || "";
      }
      if (!p256dh || !auth) {
        return { permission: Notification.permission, registered: false, message: "ブラウザから購読鍵を取得できませんでした。ブラウザを再起動してください。" };
      }

      setProgressMessage("サーバーに購読情報を登録しています...");
      await timeoutAfter(
        registerPushSubscription({ endpoint: sub.endpoint, p256dh, auth, user_agent_hash: navigator.userAgent.slice(0, 64) }),
        5000, "サーバーへの登録がタイムアウトしました。通信状態を確認してください。"
      );

      return { permission: Notification.permission, registered: true };
    } finally {
      setProgressMessage(null);
    }
  }

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    if (typeof Notification !== "undefined" && Notification.permission === "granted") {
      doRegister()
        .then((r) => { setIsRegistered(r.registered); if (r.message) setLastMessage(r.message); })
        .catch((e: unknown) => { setLastMessage(e instanceof Error ? e.message : "プッシュ通知の登録に失敗しました。"); });
    }
  }, []);

  async function requestPermission(): Promise<PushRegistrationResult> {
    if (!("Notification" in window)) {
      return { permission: "denied", registered: false, message: "このブラウザは通知APIに対応していません。" };
    }
    const current = Notification.permission;
    if (current === "granted") {
      try {
        const r = await doRegister(true);
        setIsRegistered(r.registered);
        if (r.message) setLastMessage(r.message);
        return r;
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "再登録に失敗しました。";
        setIsRegistered(false); setLastMessage(msg);
        return { permission: "granted", registered: false, message: msg };
      }
    }
    setProgressMessage("ブラウザに通知許可を要求しています...");
    let result: NotificationPermission;
    try {
      result = await Notification.requestPermission();
    } finally {
      setProgressMessage(null);
    }
    if (result === "granted") {
      try {
        const r = await doRegister(true);
        setIsRegistered(r.registered);
        if (r.message) setLastMessage(r.message);
        return r;
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "登録に失敗しました。";
        setIsRegistered(false); setLastMessage(msg);
        return { permission: result, registered: false, message: msg };
      }
    }
    setIsRegistered(false);
    if (result === "denied") {
      const msg = "通知が拒否されました。ブラウザのサイト設定で「通知」を許可に変更してから再読み込みしてください。";
      setLastMessage(msg);
      return { permission: result, registered: false, message: msg };
    }
    const msg = "通知許可の操作が完了しませんでした。もう一度お試しください。";
    setLastMessage(msg);
    return { permission: result, registered: false, message: msg };
  }

  return {
    permission: typeof Notification !== "undefined" ? Notification.permission : ("default" as NotificationPermission),
    requestPermission,
    isRegistered,
    lastMessage,
    progressMessage,
  };
}