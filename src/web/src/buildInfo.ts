/** Injected at build/dev via vite.config `define` → import.meta.env. */

export const webUiVersion = import.meta.env.VITE_WEB_UI_VERSION ?? "0.1.0";
export const nodeVersion = import.meta.env.VITE_NODE_VERSION ?? "—";
export const npmVersion = import.meta.env.VITE_NPM_VERSION ?? "—";
