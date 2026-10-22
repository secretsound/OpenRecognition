/** Injected at build/dev via vite.config `define` → import.meta.env. */

export const webUiVersion = import.meta.env.VITE_WEB_UI_VERSION ?? "0.1.0";
/** e.g. "Deno 2.4.1" or "Node 22.23.3" — whichever ran the build. */
export const buildRuntime = import.meta.env.VITE_BUILD_RUNTIME ?? "—";
export const buildTime = import.meta.env.VITE_BUILD_TIME ?? "";
