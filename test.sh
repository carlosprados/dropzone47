#!/bin/bash
set -euo pipefail

# Build the Docker image
# docker build -t dropzone47:0.2.2 .
# Run the image as a container.
# The token is read from the environment (or a local .env file); it must never
# be hardcoded here. Export it before running, e.g.:
#   export TELEGRAM_BOT_TOKEN="123456:ABC..."
# or place it in .env and `set -a; source .env; set +a`.

: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN is not set. Export it or source your .env first.}"

docker run --rm \
  -e TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}" \
  -e DOWNLOAD_DIR=/data \
  -v "$(pwd)/downloads:/data" \
  --user "$(id -u):$(id -g)" \
  --name dropzone47 \
  dropzone47:0.2.2
