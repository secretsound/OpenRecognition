# OpenRecognition

Your homelab already knows the lights are on. OpenRecognition teaches it *who* walked in.

Enroll the people, pets, and things that live with you. Hand it a voice clip, a photo, or a short video, and it answers from a gallery that stays on your own hardware. A web console covers the day-to-day stuff. Everything else is a plain HTTP API your automations can call.

## Features

- **Voices and faces.** One person, two ways to say hello: a clip of them speaking, or their face in a photo or video.
- **Pets and objects.** The dog gets a name. So can the backpack.
- **Audio gate.** Hear the difference between someone talking and the TV in the background, before speech-to-text ever starts.
- **Web console.** Enroll, try a match, manage keys, and peek at activity from the browser.
- **Webhooks and MQTT.** Matches land where your automations already live. It can also act as a **Wyoming endpoint**, so a voice pipeline learns who is talking before speech-to-text runs.

Samples turn into embeddings and get compared locally. Install the ONNX weights when you want the real speaker, face, and vision models. The API is happy to run on built-in heuristics until you do.

## Get started

Docker is the fast way in. The first start writes an admin API key and a one-time console password into the data volume.

```bash
docker compose up --build
```

The gallery stays in `/data` and model weights stay in `/models`. Either mount can be a NAS share; see [Deployment tiers](docs/deployment-tiers.md).

A published GitHub release also pushes this image to GHCR. Pull a version with:

```bash
OPENRECOGNITION_IMAGE=ghcr.io/<owner>/<repo>:0.1.0 docker compose up
```

Tags, platforms, and the workflow are in [Deployment tiers](docs/deployment-tiers.md).

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
| [Web UI](web/README.md) | Console development |

## License

Apache License 2.0. See [LICENSE](LICENSE). ONNX weights you download stay under their upstream licenses; see [docs/models.md](docs/models.md).
