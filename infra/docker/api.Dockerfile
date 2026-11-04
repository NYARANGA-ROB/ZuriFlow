# syntax=docker/dockerfile:1
# Production API image for Kubernetes — same build as api/Dockerfile, K8s entrypoint.
# Build: docker build -f infra/docker/api.Dockerfile -t dograh-api:k8s .
#
# Uses a single uvicorn process per pod; scale with Deployment replicas / HPA.

FROM python:3.13-slim AS builder

WORKDIR /app
RUN apt-get update && apt-get install -y git && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
ENV VIRTUAL_ENV=/opt/venv PATH=/opt/venv/bin:$PATH
RUN python -m venv "$VIRTUAL_ENV"
RUN --mount=type=bind,source=api/requirements.txt,target=/tmp/req.txt \
    --mount=type=cache,target=/root/.cache/uv \
    uv pip install -r /tmp/req.txt
RUN --mount=type=bind,source=pipecat,target=/tmp/pipecat,rw \
    --mount=type=cache,target=/root/.cache/uv \
    uv pip install '/tmp/pipecat[cartesia,deepgram,openai,elevenlabs,groq,google,azure,sarvam,soundfile,silero,webrtc,speechmatics,openrouter,camb,mcp,inworld,smallest]' \
 && uv pip uninstall opencv-python \
 && uv pip install opencv-python-headless \
 && python -c "import nltk; nltk.download('punkt_tab', download_dir='/opt/venv/nltk_data', quiet=True)"

FROM node:22-slim AS ts-deps
WORKDIR /ts_validator
COPY api/mcp_server/ts_validator/package*.json ./
RUN npm ci --omit=dev && npm cache clean --force

FROM debian:trixie-slim AS ffmpeg-static
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && case "${TARGETARCH}" in \
         amd64) url="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz" ;; \
         arm64) url="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz" ;; \
         *) exit 1 ;; \
       esac \
    && curl -fsSL -o /tmp/ffmpeg.tar.xz "$url" \
    && tar -xJf /tmp/ffmpeg.tar.xz -C /tmp \
    && mv "$(find /tmp -name ffmpeg | head -1)" /usr/local/bin/ffmpeg \
    && mv "$(find /tmp -name ffprobe | head -1)" /usr/local/bin/ffprobe \
    && chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe

FROM python:3.13-slim AS runner
WORKDIR /app
RUN groupadd --system dograh && useradd --system --gid dograh --home-dir /app dograh && chown dograh:dograh /app
COPY --from=ffmpeg-static /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg-static /usr/local/bin/ffprobe /usr/local/bin/ffprobe
COPY --from=node:22-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=builder /opt/venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv PATH=/opt/venv/bin:$PATH
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app LOG_TO_FILE=false
COPY --chown=dograh:dograh ./api ./api
COPY --chown=dograh:dograh ./scripts/entrypoints ./scripts/entrypoints
COPY --from=ts-deps --chown=dograh:dograh /ts_validator/node_modules ./api/mcp_server/ts_validator/node_modules
COPY --chown=dograh:dograh ./docs ./docs
USER dograh
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"
CMD ["./scripts/entrypoints/k8s-api.sh"]
