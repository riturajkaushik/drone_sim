import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  publicDir: 'assets',
  server: {
    port: 3000,
    open: false,
  },
  build: {
    outDir: 'dist',
  },
});
