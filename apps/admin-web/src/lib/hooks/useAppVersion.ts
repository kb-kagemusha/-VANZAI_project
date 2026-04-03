import { useCallback, useEffect, useState } from "react";

declare global {
  interface Window {
    __APP_VERSION__?: string;
  }
}

interface AppVersionState {
  /** ページ読み込み時のビルドバージョン（インラインスクリプトで埋め込まれた値） */
  currentVersion: string;
  /** サーバーの最新バージョン（フェッチ後に確定） */
  latestVersion: string | null;
  /** currentVersion と latestVersion が異なるとき true */
  hasUpdate: boolean;
  /** 最新バージョンで強制リフレッシュ */
  refreshNow: () => void;
}

async function fetchLatestVersion(): Promise<string | null> {
  try {
    const r = await fetch("/version.json?_t=" + Date.now(), { cache: "no-store" });
    const d: { version?: string } = await r.json();
    return d.version ?? null;
  } catch {
    return null;
  }
}

export function useAppVersion(): AppVersionState {
  const currentVersion = window.__APP_VERSION__ ?? "dev";
  const [latestVersion, setLatestVersion] = useState<string | null>(null);

  useEffect(() => {
    // 初回チェック
    fetchLatestVersion().then((v) => { if (v) setLatestVersion(v); });

    // 5分ごとに再チェック（ブラウザをしばらく放置した後でも気づける）
    const interval = setInterval(() => {
      fetchLatestVersion().then((v) => { if (v) setLatestVersion(v); });
    }, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, []);

  const hasUpdate = latestVersion !== null && latestVersion !== currentVersion;

  const refreshNow = useCallback(() => {
    const target = latestVersion ?? currentVersion;
    location.replace(location.pathname + "?_v=" + target + location.hash);
  }, [latestVersion, currentVersion]);

  return { currentVersion, latestVersion, hasUpdate, refreshNow };
}
