/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_WEB_UI_VERSION: string;
  readonly VITE_NODE_VERSION: string;
  readonly VITE_NPM_VERSION: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
