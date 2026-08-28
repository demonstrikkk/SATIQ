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
  },
  build: {
    chunkSizeWarningLimit: 1200,
  },
});
