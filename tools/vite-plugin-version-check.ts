/**
 * vite-plugin-version-check.ts
 *
 * ビルド時に dist/version.json を生成し、index.html にインラインスクリプトを埋め込む。
 * スクリプトは起動時に /version.json を no-store で取得し、埋め込まれたバージョンと
 * 一致しない場合は ?_v=<newVersion> 付きで location.replace() する。
 *
 * 【効果の範囲】
 *   - このプラグイン入りの index.html を一度でも取得したユーザー → 以後デプロイ即時反映
 *   - 現在古い index.html をキャッシュ中のユーザー → フェーズ1（クエリ付きURL案内）で対処
 */

import type { Plugin } from "vite";
import { execSync } from "child_process";
import fs from "fs";
import path from "path";

export function versionCheckPlugin(): Plugin {
  let appVersion: string;
  let buildId: string;
  let buildVersion: string;
  let outDir: string;

  return {
    name: "vanzai-version-check",
    apply: "build",

    configResolved(config) {
      outDir = path.resolve(config.root, config.build.outDir);

      try {
        const packageJsonPath = path.join(config.root, "package.json");
        const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf-8")) as { version?: string };
        appVersion = packageJson.version || "0.0.0";
      } catch {
        appVersion = "0.0.0";
      }

      try {
        const gitHash = execSync("git rev-parse --short HEAD", {
          encoding: "utf-8",
          stdio: ["pipe", "pipe", "pipe"],
        }).trim();
        buildId = `${Date.now()}-${gitHash}`;
      } catch {
        buildId = String(Date.now());
      }

      buildVersion = `${appVersion} (${buildId})`;

      console.log(`[version-check] buildVersion = ${buildVersion}`);
    },

    transformIndexHtml() {
      // インラインスクリプト: ブラウザキャッシュが古い index.html を使い続ける問題を自動修復する
      // - CURRENT_VERSION は埋め込み済みの build id
      // - APP_VERSION は画面表示用の semantic version
      // - window.__APP_VERSION__ に公開し React コンポーネントからも参照可能にする
      // - window.__APP_BUILD_ID__ に build id を公開し更新検知に使う
      // - /version.json は毎回サーバーからフェッチ（no-store）
      // - バージョン不一致 → ?_v=<new> 付きで location.replace → 別URLとしてキャッシュバイパス
      // - すでに ?_v= が付いており一致している → 再帰ループしない
      const inlineScript = `(function(){var C="${buildId}";var V="${appVersion}";window.__APP_VERSION__=V;window.__APP_BUILD_ID__=C;var p=new URLSearchParams(location.search);if(p.get("_v")===C)return;fetch("/version.json?_t="+Date.now(),{cache:"no-store"}).then(function(r){return r.json()}).then(function(d){var N=d.buildId||d.version;if(N&&N!==C){location.replace(location.pathname+"?_v="+N+location.hash)}}).catch(function(){})})();`;

      return [
        {
          tag: "script",
          injectTo: "head-prepend" as const,
          children: inlineScript,
        },
      ];
    },

    closeBundle() {
      const versionData = {
        version: appVersion,
        buildId,
        buildTime: new Date().toISOString(),
      };
      const outPath = path.join(outDir, "version.json");
      fs.writeFileSync(outPath, JSON.stringify(versionData, null, 2) + "\n");
      console.log(`[version-check] wrote ${outPath}`);
    },
  };
}
