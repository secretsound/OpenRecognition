# OpenRecognition container

Image: `ghcr.io/secretsound/openrecognition`

The container listens on port **8080** for the HTTP API and web console. Port **10301** is the Wyoming speech-to-text proxy, and it stays closed until `OPENRECOGNITION_WYOMING_ENABLED=true`.

On a new data directory the console asks you to create the admin account. The password is stored in the database. API keys are created later in the console, and only their hashes are stored.

## Run

```bash
docker pull ghcr.io/secretsound/openrecognition:dev

docker run -d --name openrecognition \
  --publish 8080:8080 \
  --volume openrecognition-data:/data \
  --volume openrecognition-models:/models \
  ghcr.io/secretsound/openrecognition:dev
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/). The API explorer is at [/docs](http://127.0.0.1:8080/docs).

Use a NAS share, or any other host directory, for one or both mounts:

```bash
docker run -d --name openrecognition \
  --publish 8080:8080 \
  --publish 10301:10301 \
  --volume /mnt/nas/openrecognition/data:/data \
  --volume /mnt/nas/openrecognition/models:/models \
  --env OPENRECOGNITION_WYOMING_ENABLED=true \
  ghcr.io/secretsound/openrecognition:dev
```

| Mount | Contents |
|-------|----------|
| `/data` | Gallery database and accounts |
| `/models` | Downloaded ONNX weights |

Weight downloads from the console go to `/models`, so they survive a new container. Files already on the mount are left alone.

| Tag | What it is |
|-----|------------|
| `dev` | Newest manual build |
| `sha-<commit>` | That commit |
| `0.1.0`, `0.1`, `latest` | GitHub releases. `latest` moves on a stable release. |

`linux/amd64` and `linux/arm64`.

## Environment

Every variable uses the prefix `OPENRECOGNITION_`. The image already sets the paths and the listen address. Leave those alone unless you are changing where the mounts live inside the container.

| Variable | Image default | Purpose |
|----------|---------------|---------|
| `HOST` | `0.0.0.0` | Address the API binds |
| `PORT` | `8080` | API and console port |
| `DATA_DIR` | `/data` | Gallery, password, and API key |
| `MODELS_DIR` | `/models` | Where new downloads are stored |
| `MODEL_PACKS_DIR` | `/models` | Older pack folders are still searched when this path differs from `MODELS_DIR` |
| `AUTH_REQUIRED` | `true` | Require an API key or console session |
| `WEB_ENABLED` | `true` | Serve the console at `/` |
| `DOCS_ENABLED` | `true` | Serve `/docs`, `/redoc`, and `/openapi.json` |
| `INFERENCE_BACKEND` | `auto` | `auto`, `onnx`, or `heuristic` |
| `WEB_ORIGIN` | unset | Browser origin allowed to call the API with cookies. Set this to the console URL when it is not the same host as the API. |
| `SESSION_TTL_MINUTES` | `60` | Console session lifetime |
| `AUTH_RATE_LIMIT_PER_MINUTE` | `60` | Sign-in attempts per minute |
| `ENROLLMENT_MEDIA_RETENTION` | `embeddings_only` | `embeddings_only` or `keep` |
| `MAINTENANCE_MODE` | `false` | Refuse recognition while you change models or data |
| `MODEL_IDLE_UNLOAD_MINUTES` | `0` | Unload unused ONNX sessions after this many minutes. `0` keeps them loaded. |

### Wyoming

Off until you set `WYOMING_ENABLED=true`. Publish `10301` when you turn it on.

| Variable | Default | Purpose |
|----------|---------|---------|
| `WYOMING_ENABLED` | `false` | Listen as a Wyoming speech-to-text service |
| `WYOMING_URI` | `tcp://0.0.0.0:10301` | Address Home Assistant connects to |
| `WYOMING_UPSTREAM_URI` | `tcp://127.0.0.1:10300` | Upstream speech-to-text, such as faster-whisper |
| `WYOMING_MIN_CONFIDENCE` | `0.75` | Speaker match threshold |
| `WYOMING_REQUIRE_SPEAKER_MATCH` | `true` | Hold audio until a speaker matches |
| `WYOMING_BLOCK_ON_GATE_REJECT` | `true` | Drop audio the gate rejects |
| `WYOMING_TAG_SPEAKER` | `false` | Prefix the transcript with the speaker name |
| `WYOMING_ZEROCONF_ENABLED` | `true` | Advertise over mDNS |
| `WYOMING_ZEROCONF_NAME` | `openrecognition` | Name shown in discovery |
| `WYOMING_ADVERTISE_HOST` | empty | LAN address to advertise when mDNS would otherwise publish a container address |
| `WYOMING_HOME_ASSISTANT_URL` | empty | Home Assistant URL used by the connectivity check |

### MQTT

| Variable | Default | Purpose |
|----------|---------|---------|
| `MQTT_ENABLED` | `false` | Publish matches |
| `MQTT_HOST` | `localhost` | Broker address |
| `MQTT_PORT` | `1883` | Broker port |
| `MQTT_TOPIC_PREFIX` | `openrecognition` | Topic prefix |

### Video limits

| Variable | Default | Purpose |
|----------|---------|---------|
| `VIDEO_RECOMMENDED_MIN_SEC` | `10` | Shortest clip the console recommends |
| `VIDEO_RECOMMENDED_MAX_SEC` | `30` | Longest clip the console recommends |
| `VIDEO_ENROLLMENT_MAX_SEC` | `60` | Longest enrollment clip |
| `VIDEO_RECOGNIZE_SYNC_MAX_SEC` | `120` | Longest clip accepted on a synchronous recognize call |
| `VIDEO_RECOGNIZE_ASYNC_MAX_SEC` | `300` | Longest clip accepted on an asynchronous recognize call |
| `VIDEO_MAX_UPLOAD_BYTES` | `104857600` | Largest upload, 100 MiB |

`WEB_DIST` (`/app/web/dist`) is set by the image. It locates the built console. Change `MODELS_DIR` when the writable model mount is not `/models`.
