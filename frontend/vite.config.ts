import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/** The API the dev server proxies to. Override when the backend is elsewhere. */
const apiTarget = process.env.DABJOB_API_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Bind IPv4 loopback explicitly: the default resolves to ::1 on macOS,
    // which makes `curl 127.0.0.1` and the container setup disagree with
    // the browser. strictPort turns a double `make dev` into an error
    // instead of a silent move to 5174.
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      // The UI never learns the API's origin: one path, one proxy, no CORS.
      "/api": { target: apiTarget, changeOrigin: false },
    },
  },
});
