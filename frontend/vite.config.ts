import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

const REPO_ROOT = path.resolve(__dirname, "..");

// README_B: FastAPI에 개발용 CORS 설정이 없다. 브라우저에서 127.0.0.1:8000을 직접
// 호출하지 않고 이 dev proxy를 통해 /api/* → 8000/*로 넘긴다. 서버는 건드리지 않는다.
const API_TARGET = process.env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      // Mock 응답은 복사본을 두지 않고 A가 생성하는 정본(outputs/mock_api/)을 직접 읽는다.
      // scripts/generate_mock_json.py가 재생성하면 프론트도 자동으로 최신이 된다.
      "@mock": path.resolve(REPO_ROOT, "outputs/mock_api"),
    },
  },
  server: {
    fs: {
      // @mock이 Vite root(frontend/) 밖에 있어서 필요하다.
      allow: [REPO_ROOT],
    },
    proxy: {
      "/api": {
        target: API_TARGET,
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    // 테스트는 .env.local과 무관하게 항상 Mock으로 돈다 — 개발자가 live로 바꿔두고
    // 작업하다가 테스트가 실제 서버를 호출하는 일이 없어야 한다.
    env: { VITE_API_MODE: "mock", VITE_MOCK_LATENCY_MS: "0" },
  },
});
