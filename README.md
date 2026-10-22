# OpenRecognition

Your homelab already knows the lights are on. OpenRecognition teaches it *who* walked in.

Enroll the people, pets, and things that live with you. Hand it a voice clip, a photo, or a short video, and it answers from a gallery that stays on your own hardware. A web console covers the day-to-day stuff. Everything else is a plain HTTP API your automations can call.

## Features

- **Voices and faces.** One person, two ways to say hello: a clip of them speaking, or their face in a photo or video.
- **Pets and objects.** The dog gets a name. So can the backpack.
- **Audio gate.** Hear the difference between someone talking and the TV in the background, before speech-to-text ever starts.
- **Web console.** Enroll, recognize a clip or photo, manage keys, and peek at activity from the browser.
- **Webhooks and MQTT.** Matches land where your automations already live. It can also act as a **Wyoming endpoint**, so a voice pipeline learns who is talking before speech-to-text runs.

Samples turn into embeddings and get compared locally. Install the ONNX weights when you want the real speaker, face, and vision models. The API is happy to run on built-in heuristics until you do.

## Get started

Docker is the fast way in. On a new data volume the console asks you to create the admin account. The password stays in the database.

```bash
docker compose up --build
```

The gallery stays in `/data` and model weights stay in `/models`. Either mount can be a NAS share. The published image is [`ghcr.io/secretsound/openrecognition`](https://github.com/secretsound/OpenRecognition/pkgs/container/openrecognition).

```bash
docker pull ghcr.io/secretsound/openrecognition:dev
docker run -d --name openrecognition \
  --publish 8080:8080 \
  --volume openrecognition-data:/data \
  --volume openrecognition-models:/models \
  ghcr.io/secretsound/openrecognition:dev
```

Variables use the `OPENRECOGNITION_` prefix. The image already sets `HOST=0.0.0.0`, `PORT=8080`, `DATA_DIR=/data`, and `MODELS_DIR=/models`. `AUTH_REQUIRED` and `WEB_ENABLED` default to `true`. Set `WYOMING_ENABLED=true` and publish `10301` when Home Assistant should use the Wyoming proxy. MQTT stays off until `MQTT_ENABLED=true`. The [container guide](docker/README.md) lists every variable, the volume layout, and the release tags.

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/) and sign in as `admin`. The API explorer is at [/docs](http://127.0.0.1:8080/docs).

From Python 3.12: `pip install -e .`, then `openrecognition bootstrap` and `openrecognition serve`. Model downloads, the web console, and the Dev Container are in the docs below.

## Documentation

| Guide | What it covers |
|-------|----------------|
| [Development](docs/development.md) | Dev Container, local setup, web UI |
| [Models](docs/models.md) | Which weights to download, and when to re-enroll |
| [Architecture](docs/architecture.md) | How a request moves through the service |
| [Deployment tiers](docs/deployment-tiers.md) | `edge`, `standard`, and `home` packs |
| [Frigate](docs/integrations/frigate.md) | Snapshot URL ingest |
| [Container image](docker/README.md) | Run the image, mounts, environment variables |
| [Web UI](src/web/README.md) | Console development |

## License

Apache License 2.0. See [LICENSE](LICENSE). ONNX weights you download stay under their upstream licenses; see [docs/models.md](docs/models.md).
