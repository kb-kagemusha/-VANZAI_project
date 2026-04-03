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

export function useAppVersion(): AppVersionState {
  const currentVersion = window.__APP_VERSION__ ?? "dev";
  const [latestVersion, setLatestVersion] = useState<string | null>(null);

  useEffect(() => {
    fetch("/version.json?_t=" + Date.now(), { cache: "no-store" })
      .then((r) => r.json())
      .then((d: { version?: string }) => {
        if (d.version) setLatestVersion(d.version);
      })
      .catch(() => {/* ネットワーク不可時は無視 */});
  }, []);

  const hasUpdate = latestVersion !== null && latestVersion !== currentVersion;

  const refreshNow = useCallback(() => {
    const target = latestVersion ?? currentVersion;
    location.replace(location.pathname + "?_v=" + target + location.hash);
  }, [latestVersion, currentVersion]);

  return { currentVersion, latestVersion, hasUpdate, refreshNow };
}
