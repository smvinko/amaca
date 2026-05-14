import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5173,
    proxy: {
      // Proxy API + WebSocket calls to the FastAPI backend.
      // Cookies set by the backend end up on the same origin (5173)
      // because the browser sees a single hop.
      '/api': { target: 'http://localhost:8000', changeOrigin: true, ws: true }
    }
  }
});
