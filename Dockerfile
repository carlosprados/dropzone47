# --- build stage ---
FROM golang:1.26-bookworm AS build

WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download

COPY . .
ARG VERSION=docker
RUN CGO_ENABLED=0 go build \
    -ldflags "-s -w -X github.com/carlosprados/dropzone47/cmd.Version=${VERSION}" \
    -o /out/dropzone47 .

# --- runtime stage ---
# python-slim gives us ffmpeg (apt) plus yt-dlp (pip) for the fallback backend.
FROM python:3.11-slim

ENV DROPZONE47_DOWNLOAD_DIR=/data \
    HOME=/home/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir yt-dlp \
    && groupadd -r app \
    && useradd -m -d /home/app -r -g app app \
    && mkdir -p /data \
    && chown -R app:app /data /home/app

COPY --from=build /out/dropzone47 /usr/local/bin/dropzone47

USER app:app
ENTRYPOINT ["dropzone47"]
CMD ["serve"]
