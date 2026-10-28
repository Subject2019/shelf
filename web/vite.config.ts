import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 开发时 /api 代理到后端 8080，生产由 nginx 反代（deploy/nginx.conf）
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8080",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
