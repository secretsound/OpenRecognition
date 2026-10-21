# Dev image — dependencies installed at build; bind-mount updates code at runtime.
ARG BASE_IMAGE=python:3.12-bookworm
FROM ${BASE_IMAGE}

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    libsndfile1 \
    ffmpeg \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22 + npm (Vue / Vite web UI)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version && npm --version

RUN groupadd --gid "${USER_GID}" "${USERNAME}" \
    && useradd -s /bin/bash --uid "${USER_UID}" --gid "${USER_GID}" -m "${USERNAME}" \
    && mkdir -p /workspace /data \
    && echo "${USERNAME} ALL=(ALL) NOPASSWD: /usr/local/bin/pip, /usr/local/bin/python3" >> /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME}

WORKDIR /workspace

COPY pyproject.toml README.md ./
COPY src ./src/
COPY model-packs ./model-packs/
COPY tests ./tests/

RUN pip install --no-cache-dir -e ".[dev]" \
    && python -c "import uvicorn, fastapi, onnxruntime; import openrecognition; print('build ok')" \
    && chown -R "${USERNAME}:${USERNAME}" /workspace /data

USER ${USERNAME}
WORKDIR /workspace

# Wyoming Assist (HA) — must be published in compose / devcontainer forwardPorts too.
EXPOSE 8080 10301/tcp

ENV OPENRECOGNITION_HOST=0.0.0.0 \
    OPENRECOGNITION_PORT=8080 \
    OPENRECOGNITION_DATA_DIR=/data \
    OPENRECOGNITION_MODEL_PACKS_DIR=/workspace/model-packs \
    OPENRECOGNITION_PACK=edge \
    OPENRECOGNITION_AUTH_REQUIRED=true \
    OPENRECOGNITION_WEB_ENABLED=true \
    OPENRECOGNITION_WEB_ORIGIN=http://localhost:5173

CMD ["sleep", "infinity"]
