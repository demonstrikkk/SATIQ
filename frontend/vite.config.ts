import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [tailwindcss(), react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  optimizeDeps: {
    include: [
      "react",
      "react-dom",
      "react-router",
      "@radix-ui/react-slot",
      "class-variance-authority",
      "clsx",
      "tailwind-merge",
      "zustand",
      "react-markdown",
      "remark-gfm",
      "apexcharts",
      "react-apexcharts",
      "maplibre-gl",
      "lucide-react",
    ],
    force: false,
  },
  server: {
    port: 5173,
    strictPort: false,
    hmr: { overlay: true },
    proxy: {
      "/api": {
        target: "http://localhost:4000",
        changeOrigin: true,
      },
      "/health": {
        target: "http://localhost:4000",
        changeOrigin: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/react") || id.includes("node_modules/react-dom") || id.includes("node_modules/react-router")) return "vendor";
          if (id.includes("node_modules/maplibre-gl")) return "map";
          if (id.includes("node_modules/apexcharts") || id.includes("node_modules/react-apexcharts")) return "charts";
          if (id.includes("node_modules/react-markdown") || id.includes("node_modules/remark-gfm")) return "markdown";
          if (id.includes("node_modules/zustand") || id.includes("node_modules/lucide-react") || id.includes("node_modules/motion")) return "ui";
        },
      },
    },
  },
});
