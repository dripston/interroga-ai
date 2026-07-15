import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: 5000,
    allowedHosts: true,
    proxy: {
      '/game': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true
      }
    }
  },
});
