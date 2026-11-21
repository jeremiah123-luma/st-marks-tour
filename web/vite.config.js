import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The intro and the text panels are a small React chunk, so the church name and "Begin the tour" show before
// the 3D arrives. The room (three, react-three-fiber, the scene) is a separate chunk that App.jsx imports lazily.
export default defineConfig({
  base: './',
  plugins: [react()],
  server: { port: 5320, strictPort: true, host: '127.0.0.1' },
  build: {
    target: 'es2022',
    modulePreload: { polyfill: false },
    chunkSizeWarningLimit: 1000, // three alone is about 990KB raw: r3f imports all of it
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            { name: 'three', test: /node_modules[\\/](three|@react-three)[\\/]/, priority: 1 },
            { name: 'react', test: /node_modules[\\/](react|react-dom|scheduler|its-fine|zustand|suspend-react|react-use-measure|use-sync-external-store)[\\/]/, priority: 2 },
          ],
        },
      },
    },
  },
});
