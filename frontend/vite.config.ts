import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({ plugins: [react()], build: { rollupOptions: { output: { manualChunks: { livekit: ['livekit-client'] } } } }, server: { proxy: { '/api': 'http://127.0.0.1:8000' } } });
