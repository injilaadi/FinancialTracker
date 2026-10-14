import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development the browser talks to Vite, and Vite forwards /api/* to the FastAPI service
// (stripping the /api prefix), so there is no CORS to configure. In Docker, nginx does the same.
const API_URL = process.env.API_URL ?? "http://localhost:8080";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: API_URL, changeOrigin: true, rewrite: (path) => path.replace(/^\/api/, "") } },
  },
  preview: {
    port: 5173,
    proxy: { "/api": { target: API_URL, changeOrigin: true, rewrite: (path) => path.replace(/^\/api/, "") } },
  },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
