import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "prompt",
      includeAssets: ["icon-192.png", "icon-512.png", "icon.svg", "theme.js", "manifest-it.webmanifest"],
      manifest: {
        name: "Split Companion",
        short_name: "Split",
        description: "Shared expenses, peace of mind.",
        lang: "en",
        start_url: "/",
        scope: "/",
        display: "standalone",
        theme_color: "#f2f2f7",
        background_color: "#f2f2f7",
        icons: [
          {
            src: "/icon-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any maskable",
          },
        ],
      },
      workbox: {
        importScripts: ["/push-sw.js"],
        navigateFallback: "index.html",
        navigateFallbackDenylist: [/^\/api\//],
        globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
        runtimeCaching: [],
      },
    }),
  ],
  server: { proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: false } } },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: [
            "react",
            "react-dom",
            "react-router-dom",
            "@tanstack/react-query",
          ],
        },
      },
    },
  },
});
