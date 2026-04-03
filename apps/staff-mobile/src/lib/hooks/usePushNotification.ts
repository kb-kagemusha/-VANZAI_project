/**
 * usePushNotification.ts
 */
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

async function doRegister(): Promise<void> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;
  const reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
  await navigator.serviceWorker.ready;
  if (Notification.permission !== "granted") return;
  const { public_key } = await getVapidPublicKey();
  if (!public_key) return;
  const applicationServerKey = urlB64ToUint8Array(public_key);
  const existing = await reg.pushManager.getSubscription();
  if (existing) return;
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey,
  });
  const json = sub.toJSON();
  await registerPushSubscription({
    endpoint: sub.endpoint,
    p256dh: json.keys?.p256dh ?? "",
    auth: json.keys?.auth ?? "",
    user_agent_hash: navigator.userAgent.slice(0, 64),
  });
}

export function usePushNotification() {
  const [permission, setPermission] = useState<NotificationPermission>(
    typeof Notification !== "undefined" ? Notification.permission : "default"
  );
  const registered = useRef(false);
  useEffect(() => {
    if (permission === "granted" && !registered.current) {
      registered.current = true;
      doRegister().catch(console.error);
    }
  }, [permission]);
  const requestPermission = async () => {
    if (!("Notification" in window)) return;
    const result = await Notification.requestPermission();
    setPermission(result);
    if (result === "granted") {
      await doRegister().catch(console.error);
    }
  };
  return { permission, requestPermission };
}
