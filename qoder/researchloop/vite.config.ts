import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const proxy = { "/api": "http://127.0.0.1:8788" };

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL(".", import.meta.url)) } },
  server: { host: "127.0.0.1", proxy },
  preview: { host: "127.0.0.1", proxy },
  build: { outDir: "dist" },
});
