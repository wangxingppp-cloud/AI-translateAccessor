import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import electron from 'vite-plugin-electron';
import electronRenderer from 'vite-plugin-electron-renderer';
import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Copy raw CJS preload to dist-electron (fires in both dev and build)
function copyPreloadPlugin() {
  const src = resolve(__dirname, 'electron/preload.cjs');
  const destDir = resolve(__dirname, 'dist-electron');
  const dest = resolve(destDir, 'preload.cjs');
  function copy() {
    mkdirSync(destDir, { recursive: true });
    copyFileSync(src, dest);
  }
  return {
    name: 'copy-preload',
    buildStart: copy,
    writeBundle: copy,
    configureServer() { copy(); },
  };
}

export default defineConfig({
  plugins: [
    react(),
    electron([
      {
        // Main process — ESM with "type": "module" in package.json
        entry: 'electron/main.ts',
        onstart(args) {
          args.startup();
        },
        vite: {
          build: {
            outDir: 'dist-electron',
            rollupOptions: {
              external: ['electron'],
            },
          },
        },
      },
      // Preload is a raw CJS file (electron/preload.cjs), copied by copyPreloadPlugin above.
      // It is NOT built by Vite because Electron sandbox requires pure CommonJS,
      // and vite-plugin-electron cannot reliably output CJS format.
    ]),
    electronRenderer(),
    copyPreloadPlugin(),
  ],
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
