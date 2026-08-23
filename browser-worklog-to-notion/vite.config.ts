import { copyFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { defineConfig, type Plugin } from "vite";

const projectRoot = fileURLToPath(new URL(".", import.meta.url));

function copyManifest(): Plugin {
  return {
    name: "copy-extension-manifest",
    closeBundle() {
      copyFileSync(resolve(projectRoot, "manifest.json"), resolve(projectRoot, "dist/manifest.json"));
    }
  };
}

export default defineConfig({
  plugins: [copyManifest()],
  build: {
    emptyOutDir: true,
    rollupOptions: {
      input: {
        background: resolve(projectRoot, "src/background.ts"),
        contentScript: resolve(projectRoot, "src/contentScript.ts"),
        options: resolve(projectRoot, "options.html"),
        popup: resolve(projectRoot, "popup.html")
      },
      output: {
        entryFileNames: "[name].js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name][extname]"
      }
    }
  }
});
