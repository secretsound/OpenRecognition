#!/bin/sh
set -e

DATA_DIR="${OPENRECOGNITION_DATA_DIR:-/data}"
MODELS_DIR="${OPENRECOGNITION_MODELS_DIR:-${OPENRECOGNITION_MODEL_PACKS_DIR:-/models}}"

mkdir -p "${DATA_DIR}" "${MODELS_DIR}"

# Creates the data directory and database. The console asks for the admin password
# when no account exists yet.
openrecognition bootstrap

exec "$@"
