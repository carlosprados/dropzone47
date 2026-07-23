# dropzone47

![Go](https://img.shields.io/badge/go-1.26%2B-00ADD8)
![lux](https://img.shields.io/badge/downloader-lux%20%2B%20yt--dlp-orange)

> Fast, size-aware YouTube downloader — a Telegram bot **and** a CLI, written in Go.

dropzone47 downloads YouTube audio/video and keeps files under Telegram's size limit.
It uses **lux** (pure Go) as the fast path and falls back to **yt-dlp** automatically
whenever lux fails or can't fit the size limit. Run it as a Telegram bot or download
straight to disk from the command line.

## Features

- **Two interfaces**: a Telegram bot (`serve`) and a direct CLI downloader (`get`).
- **Dual backend with fallback**: lux first (pure Go), yt-dlp as a robust safety net;
  forceable with `--downloader lux|yt-dlp|auto`.
- **Size-aware**: steps down a configurable resolution ladder (video) and lowers the
  bitrate (audio) to fit `telegram-max-mb`.
- **Concurrency queue**: a global limit on simultaneous downloads; extra requests wait.
- **Per-user rate limiting**: a quota of downloads per time window.
- **Per-user isolation**: each user's files live under their own directory.
- **Live progress**, cancel, and management commands.
- **i18n**: English or Spanish (`--lang`).
- **SQLite** session persistence (pure-Go driver, no cgo).
- **Self-describing CLI**: Cobra help/examples on every command and flag.

## Requirements

- Go 1.26+ (to build).
- **FFmpeg** on `PATH` (merging video, extracting MP3).
- **yt-dlp** on `PATH` for the fallback backend (strongly recommended; lux alone is
  unreliable for YouTube).

## Install & build

```sh
go build -o dropzone47 .
# or install to $GOBIN
go install github.com/carlosprados/dropzone47@latest
```

## Configuration

Precedence (low → high): **defaults < config file < environment (`DROPZONE47_*`) < flags**.

| Flag | Env | Default | Meaning |
|------|-----|---------|---------|
| `--telegram-token` | `DROPZONE47_TELEGRAM_TOKEN` | — | Bot token (required for `serve`) |
| `--downloader` | `DROPZONE47_DOWNLOADER` | `auto` | `lux` \| `yt-dlp` \| `auto` |
| `--download-dir` | `DROPZONE47_DOWNLOAD_DIR` | `./downloads` | Output base dir |
| `--sessions-db` | `DROPZONE47_SESSIONS_DB` | `./downloads/sessions` | SQLite base path (`.sqlite3` appended) |
| `--telegram-max-mb` | `DROPZONE47_TELEGRAM_MAX_MB` | `1900` | Max upload size (MB) |
| `--max-height` | `DROPZONE47_MAX_HEIGHT` | `720` | Max video resolution |
| `--video-height-ladder` | `DROPZONE47_VIDEO_HEIGHT_LADDER` | `720,480,360,240` | Fallback resolutions (capped at max-height) |
| `--audio-kbitrate` | `DROPZONE47_AUDIO_KBITRATE` | `128` | MP3 bitrate (kbps) |
| `--socket-timeout` | `DROPZONE47_SOCKET_TIMEOUT` | `30` | yt-dlp socket timeout (s) |
| `--ytdlp-retries` | `DROPZONE47_YTDLP_RETRIES` | `3` | yt-dlp retries |
| `--cleanup-after-send` | `DROPZONE47_CLEANUP_AFTER_SEND` | `false` | Delete files after sending |
| `--max-concurrent` | `DROPZONE47_MAX_CONCURRENT` | `2` | Global concurrent downloads (queue) |
| `--rate-limit-max` | `DROPZONE47_RATE_LIMIT_MAX` | `5` | Downloads per window per user (`0` disables) |
| `--rate-limit-window` | `DROPZONE47_RATE_LIMIT_WINDOW` | `1h` | Rate-limit window (`1h`, `30m`, `3600s`) |
| `--lang` | `DROPZONE47_LANG` | `en` | Bot language: `en` \| `es` |
| `--log-level` | `DROPZONE47_LOG_LEVEL` | `info` | `debug`\|`info`\|`warn`\|`error` |

Copy `.env.example` to `.env` for docker-compose, or pass `--config config.yaml`.

## Usage

The binary is self-documenting — start with `--help`:

```sh
dropzone47 --help
dropzone47 serve --help
dropzone47 get --help
```

### Run the bot

```sh
DROPZONE47_TELEGRAM_TOKEN=123:abc dropzone47 serve
dropzone47 serve --lang es --max-concurrent 3 --rate-limit-max 10 --rate-limit-window 30m
```

Then in Telegram: send a URL, pick 🎵 Audio or 🎬 Video, receive the file.

Bot commands: `/start`, `/downloads`, `/cancel`, `/clear_downloads`.

### Download from the CLI (no Telegram)

```sh
dropzone47 get "https://youtu.be/dQw4w9WgXcQ"
dropzone47 get --format audio -o ./music "https://youtu.be/dQw4w9WgXcQ"
dropzone47 get --downloader yt-dlp --max-height 480 "<url>"
```

### Other commands

```sh
dropzone47 config show     # print the resolved configuration (token masked)
dropzone47 version         # version + which backends are available
```

## Docker

```sh
docker build -t dropzone47:go .
docker run --rm \
  -e DROPZONE47_TELEGRAM_TOKEN=123:abc \
  -v "$(pwd)/downloads:/data" \
  --user "$(id -u):$(id -g)" \
  dropzone47:go
```

The image bundles ffmpeg and yt-dlp. No ports are exposed (long polling).

### Docker Compose

Put your token (and any overrides) in `.env` (see `.env.example`), then:

```sh
docker compose up -d --build
docker compose logs -f
```

## How the backends compose

- **Metadata** (`FetchInfo`): yt-dlp preferred (richer, includes duration), lux as fallback.
- **Audio**: always yt-dlp (lux does not reliably produce MP3).
- **Video**: lux first; if it panics/fails or the result exceeds the size limit, fall back
  to yt-dlp and run the resolution ladder.
- **Forced** (`--downloader lux|yt-dlp`): bypasses the composition.

> lux's YouTube extractor is fragile and can even panic; those panics are recovered and
> turned into a yt-dlp fallback, so downloads keep working.

## Development

```sh
go build ./...       # compile
go vet ./...         # static checks
gofmt -l cmd internal main.go   # formatting (should print nothing)
go test ./...        # unit tests
```

Package layout:

- `cmd/` — Cobra commands (`serve`, `get`, `config`, `version`) and Viper wiring.
- `internal/config` — configuration struct and loading.
- `internal/download` — `Downloader` interface, lux/yt-dlp/auto backends, ladder & file helpers.
- `internal/bot` — Telegram handlers, concurrency queue, cancellation.
- `internal/session` — SQLite session store.
- `internal/ratelimit` — per-user sliding-window limiter.
- `internal/i18n` — message catalog (en/es).
- `internal/util` — URL/format/path helpers.
- `legacy/` — the original Python implementation, kept for reference.
