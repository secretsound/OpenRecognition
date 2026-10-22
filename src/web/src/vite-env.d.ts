/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_WEB_UI_VERSION: string;
  readonly VITE_BUILD_RUNTIME: string;
  readonly VITE_BUILD_TIME: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
