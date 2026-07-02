import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { versionCheckPlugin } from "../../tools/vite-plugin-version-check";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    plugins: [react(), versionCheckPlugin()],
    test: {
      environment: "node",
      include: ["src/**/*.test.ts"],
    },
    build: {
      emptyOutDir: true,
    },
    server: {
      port: 3000,
      proxy: {
        "/api": {
          target: env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },
  };
});