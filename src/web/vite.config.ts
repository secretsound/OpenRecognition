import { readFileSync } from "fs";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import basicSsl from "@vitejs/plugin-basic-ssl";
import { resolve } from "path";

const pkg = JSON.parse(readFileSync(resolve(__dirname, "package.json"), "utf-8")) as {
  version: string;
};

/** Which runtime is executing this build (Deno or Node). */
function buildRuntime(): string {
  const g = globalThis as { Deno?: { version?: { deno?: string } } };
  if (g.Deno?.version?.deno) return `Deno ${g.Deno.version.deno}`;
  return `Node ${process.versions.node}`;
}

/** API the dev server proxies to. Override with VITE_API_PROXY=http://host:port. */
const apiProxy = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8080";

export default defineConfig({
  plugins: [vue(), basicSsl()],
  define: {
    "import.meta.env.VITE_WEB_UI_VERSION": JSON.stringify(pkg.version),
    "import.meta.env.VITE_BUILD_RUNTIME": JSON.stringify(buildRuntime()),
    "import.meta.env.VITE_BUILD_TIME": JSON.stringify(new Date().toISOString()),
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
  build: {
    outDir: resolve(__dirname, "dist"),
    emptyOutDir: true,
    chunkSizeWarningLimit: 600,
  },
  server: {
    https: true,
    host: true,
    port: 5173,
    proxy: {
      "/v1": {
        target: apiProxy,
        changeOrigin: true,
        timeout: 0,
      },
      ...Object.fromEntries(
        ["/health", "/docs", "/redoc", "/openapi.json", "/api"].map((p) => [p, apiProxy]),
      ),
    },
  },
});
