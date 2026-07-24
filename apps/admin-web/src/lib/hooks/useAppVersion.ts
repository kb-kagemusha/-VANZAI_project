import { useCallback, useEffect, useState } from "react";

declare global {
  interface Window {
    __APP_VERSION__?: string;
    __APP_BUILD_ID__?: string;
  }
}

interface AppVersionState {
  /** ページ読み込み時の表示用バージョン */
  currentVersion: string;
  /** ページ読み込み時の build id */
  currentBuildId: string;
  /** サーバーの最新表示バージョン（フェッチ後に確定） */
  latestVersion: string | null;
  /** build id が異なるとき true */
  hasUpdate: boolean;
  /** 最新バージョンで強制リフレッシュ */
  refreshNow: () => void;
}

interface VersionPayload {
  version?: string;
  buildId?: string;
}

async function fetchLatestVersion(): Promise<VersionPayload | null> {
  try {
    const r = await fetch("/version.json?_t=" + Date.now(), { cache: "no-store" });
    const d: VersionPayload = await r.json();
    return d;
  } catch {
    return null;
  }
}

export function useAppVersion(): AppVersionState {
  const currentVersion = window.__APP_VERSION__ ?? "0.0.0";
  const currentBuildId = window.__APP_BUILD_ID__ ?? currentVersion;
  const [latestVersion, setLatestVersion] = useState<string | null>(null);
  const [latestBuildId, setLatestBuildId] = useState<string | null>(null);

  useEffect(() => {
    // 初回チェック
    fetchLatestVersion().then((payload) => {
      if (!payload) return;
      if (payload.version) setLatestVersion(payload.version);
      if (payload.buildId || payload.version) setLatestBuildId(payload.buildId ?? payload.version ?? null);
    });

    // 5分ごとに再チェック（ブラウザをしばらく放置した後でも気づける）
    const interval = setInterval(() => {
      fetchLatestVersion().then((payload) => {
        if (!payload) return;
        if (payload.version) setLatestVersion(payload.version);
        if (payload.buildId || payload.version) setLatestBuildId(payload.buildId ?? payload.version ?? null);
      });
    }, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, []);

  const hasUpdate = latestBuildId !== null && latestBuildId !== currentBuildId;

  const refreshNow = useCallback(() => {
    const target = latestBuildId ?? currentBuildId;
    location.replace(location.pathname + "?_v=" + target + location.hash);
  }, [latestBuildId, currentBuildId]);

  return { currentVersion, currentBuildId, latestVersion, hasUpdate, refreshNow };
}
