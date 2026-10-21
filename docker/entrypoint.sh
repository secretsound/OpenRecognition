#!/bin/sh
set -e

DATA_DIR="${OPENRECOGNITION_DATA_DIR:-/data}"
MODELS_DIR="${OPENRECOGNITION_MODEL_PACKS_DIR:-/models}"
SHIPPED_PACKS="${OPENRECOGNITION_SHIPPED_PACKS_DIR:-/app/model-packs}"

mkdir -p "${DATA_DIR}" "${MODELS_DIR}"

# Copy shipped pack manifests (and any weights baked into the image) onto the
# models mount when those files are not already there. A NAS share is left as-is.
if [ -d "${SHIPPED_PACKS}" ] && [ "${SHIPPED_PACKS}" != "${MODELS_DIR}" ]; then
  for manifest in "${SHIPPED_PACKS}"/*/model-pack.yaml; do
    [ -f "${manifest}" ] || continue
    pack=$(basename "$(dirname "${manifest}")")
    dest_dir="${MODELS_DIR}/${pack}"
    mkdir -p "${dest_dir}"
    if [ ! -f "${dest_dir}/model-pack.yaml" ]; then
      cp "${manifest}" "${dest_dir}/model-pack.yaml"
    fi
    for weight in "${SHIPPED_PACKS}/${pack}/"*.onnx; do
      [ -f "${weight}" ] || continue
      dest_weight="${dest_dir}/$(basename "${weight}")"
      if [ ! -f "${dest_weight}" ]; then
        cp "${weight}" "${dest_weight}"
      fi
    done
  done
fi

# Creates the data directory and database. The console asks for the admin password
# when no account exists yet.
openrecognition bootstrap

exec "$@"
