# OpenRecognition Web UI

Vue 3 + Naive UI admin console for enrollments, API keys, and webhooks. UI conventions: [../docs/ui-design.md](../docs/ui-design.md).

## Prerequisites

- Node.js 20+ and npm
- OpenRecognition API running on port 8080

## Development

```bash
cd web
npm install --legacy-peer-deps
export OPENRECOGNITION_WEB_ORIGIN=https://localhost:5173   # API env (HTTPS for mic)
openrecognition serve   # separate terminal
npm run dev
```

Open **[https://localhost:5173](https://localhost:5173)** (Vite uses a self-signed certificate — accept the browser warning once). Vite proxies `/v1` and `/health` to the API.

**Microphone / voice enrollment** requires a [secure context](https://developer.mozilla.org/en-US/docs/Web/Security/Secure_Contexts). The dev server enables HTTPS for that reason. The built-in UI at `http://127.0.0.1:8080` works for mic only when the hostname is `localhost` or `127.0.0.1`; remote HTTP URLs will block recording.

Default user: `admin`. On first start the password is written to `data/admin.password` (mode 0600) and printed once by `openrecognition bootstrap`. Change it after you sign in.

## Production build

```bash
npm run build
```

Output is written to [`dist/`](dist/). FastAPI serves it at `/` when the API is running.

## Stack

- Vue 3 + TypeScript + Vite
- [Naive UI](https://www.naiveui.com/)
- Session cookie auth (`credentials: include`)
