import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  publicDir: false,
  build: {
    outDir: "public",
    emptyOutDir: true,
    assetsDir: "assets",
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ["echarts"],
          react: ["react", "react-dom"]
        }
      }
    }
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000"
    }
  }
});
