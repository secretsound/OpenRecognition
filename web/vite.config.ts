import { execSync } from "child_process";
import { readFileSync } from "fs";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import basicSsl from "@vitejs/plugin-basic-ssl";
import { resolve } from "path";

const pkg = JSON.parse(readFileSync(resolve(__dirname, "package.json"), "utf-8")) as {
  version: string;
};

function npmVersion(): string {
  try {
    return execSync("npm -v", { encoding: "utf-8" }).trim();
  } catch {
    return "";
  }
}

export default defineConfig({
  plugins: [vue(), basicSsl()],
  define: {
    "import.meta.env.VITE_WEB_UI_VERSION": JSON.stringify(pkg.version),
    "import.meta.env.VITE_NODE_VERSION": JSON.stringify(process.version),
    "import.meta.env.VITE_NPM_VERSION": JSON.stringify(npmVersion()),
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
  build: {
    outDir: resolve(__dirname, "dist"),
    emptyOutDir: true,
  },
  server: {
    https: true,
    host: true,
    port: 5173,
    proxy: {
      "/v1": "http://127.0.0.1:8080",
      "/health": "http://127.0.0.1:8080",
      "/docs": "http://127.0.0.1:8080",
      "/redoc": "http://127.0.0.1:8080",
      "/openapi.json": "http://127.0.0.1:8080",
      "/api": "http://127.0.0.1:8080",
    },
  },
});
