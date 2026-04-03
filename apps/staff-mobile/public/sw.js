/**
 * sw.js — VANZAI Staff Mobile Service Worker
 *
 * 役割:
 * 1. Web Push 受信 → ネイティブ通知を表示
 * 2. 通知クリック → /notices を開く（or フォーカスする）
 */

self.addEventListener("push", (event) => {
  if (!event.data) return;

  let data = {};
  try {
    data = event.data.json();
  } catch {
    data = { title: "VANZAI", body: event.data.text() };
  }

  const title = data.title || "VANZAI通知";
  const options = {
    body: data.body || "",
    icon: "/icon-192.png",
    badge: "/icon-72.png",
    data: { url: data.url || "/notices" },
    requireInteraction: false,
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || "/notices";

  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((windowClients) => {
        // すでに開いているタブがあればそちらをフォーカス
        for (const client of windowClients) {
          if (client.url.includes(self.location.origin) && "focus" in client) {
            client.focus();
            client.navigate(targetUrl);
            return;
          }
        }
        // なければ新規タブを開く
        if (clients.openWindow) {
          return clients.openWindow(targetUrl);
        }
      })
  );
});
