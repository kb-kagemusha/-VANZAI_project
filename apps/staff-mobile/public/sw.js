/**
 * sw.js — VANZAI Staff Mobile Service Worker
 *
 * 役割:
 * 1. Web Push 受信 → ネイティブ通知を表示（アクションボタン対応）
 * 2. 通知クリック / アクションボタン → /notices を開く
 *    アクションボタンタップ時: /notices?action=ok&nid=<notice_id> へ遷移
 *    → NoticesPage 側で自動返答APIを呼ぶ
 *
 * push_action_type:
 *   "ok_ng"   → "OKです、了承します" / "NGです" ボタン
 *   "confirm" → "確認しました" ボタン
 *   null / 未指定 → ボタンなし
 */

/** push_action_type → NotificationAction[] */
function buildActions(pushActionType) {
  if (pushActionType === "ok_ng") {
    return [
      { action: "ok", title: "✓ OKです、了承します" },
      { action: "ng", title: "✗ NGです" },
    ];
  }
  if (pushActionType === "confirm") {
    return [{ action: "ok", title: "✓ 確認しました" }];
  }
  return [];
}

self.addEventListener("push", (event) => {
  if (!event.data) return;

  let data = {};
  try {
    data = event.data.json();
  } catch {
    data = { title: "VANZAI", body: event.data.text() };
  }

  const title = data.title || "VANZAI通知";
  const actions = buildActions(data.push_action_type);
  const options = {
    body: data.body || "",
    icon: "/icon-192.png",
    badge: "/icon-72.png",
    data: {
      url: data.url || "/notices",
      notice_id: data.notice_id || null,
    },
    requireInteraction: actions.length > 0,
    actions,
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const action = event.action;           // "ok" | "ng" | "" (本文クリック)
  const noticeId = event.notification.data && event.notification.data.notice_id;
  const baseUrl = (event.notification.data && event.notification.data.url) || "/notices";

  // アクションボタンをタップ → クエリパラメータ付きでリダイレクト
  // NoticesPage がこれを読んで自動返答する
  let targetUrl = baseUrl;
  if (action && noticeId) {
    targetUrl = "/notices?action=" + action + "&nid=" + encodeURIComponent(noticeId);
  }

  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((windowClients) => {
        for (const client of windowClients) {
          if (client.url.includes(self.location.origin) && "focus" in client) {
            client.focus();
            client.navigate(targetUrl);
            return;
          }
        }
        if (clients.openWindow) {
          return clients.openWindow(targetUrl);
        }
      })
  );
});