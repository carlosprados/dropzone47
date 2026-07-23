# dropzone47

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-22.x-28a745)
![yt-dlp](https://img.shields.io/badge/yt--dlp-active-orange)

> Fast, size‑aware YouTube downloader bot for Telegram. Shows progress, supports cancel, and uploads real files with friendly filenames.

Telegram bot to download YouTube content and send audio/video to the chat with size controls, a configurable download folder, SQLite session persistence, visible progress (percent, speed, ETA), and cancel support.

## Features

- **Audio (MP3) or video (MP4)** selection via inline buttons.
- **Size-aware fallbacks**: steps down a configurable video resolution ladder and lowers audio bitrate to fit Telegram's size limit.
- **Live progress**: percent, speed and ETA in the message caption.
- **Cancel & manage**: `/cancel`, `/downloads`, `/clear_downloads`.
- **Per-user isolation**: each user's files live under their own directory.
- **Concurrency cap + queue**: a global limit on simultaneous downloads; extra requests wait for a slot.
- **Per-user rate limiting**: a quota of downloads per time window.
- **Input safety**: only valid http(s) URLs; playlists are not expanded.
- **i18n**: user-facing messages in English or Spanish (`BOT_LANG`).
- **SQLite persistence**: sessions survive restarts.

## Requirements

- Python 3.11+
- FFmpeg installed and available in `PATH` (required for merging video and extracting audio)

## Configuration (.env)

This project loads variables from a `.env` file via `python-dotenv`.

1) Copy the example and edit it:

```
cp .env.example .env
```

2) Fill at least `TELEGRAM_BOT_TOKEN`.

Available variables:

- `TELEGRAM_BOT_TOKEN`: Telegram bot token (required).
- `DOWNLOAD_DIR`: directory where downloads are stored. Default `./downloads`.
- `TELEGRAM_MAX_MB`: max file size to send in MB. Default `1900`.
- `MAX_HEIGHT`: max video resolution (e.g., `720`). Default `720`.
- `VIDEO_HEIGHT_LADDER`: comma-separated resolutions (descending) tried when a video exceeds the size limit; capped at `MAX_HEIGHT`. Default `720,480,360,240`.
- `AUDIO_KBITRATE`: MP3 audio bitrate (kbps). Default `128`.
- `SOCKET_TIMEOUT`: network timeout for `yt-dlp` (s). Default `30`.
- `YTDLP_RETRIES`: retry count for `yt-dlp`. Default `3`.
- `CLEANUP_AFTER_SEND`: whether to delete files after sending (`true`/`false`). In `.env.example` it's `false` to keep files.
- `MAX_CONCURRENT_DOWNLOADS`: max downloads running at once across all users; the rest queue. Default `2`.
- `RATE_LIMIT_MAX`: max downloads per user within `RATE_LIMIT_WINDOW`. `0` disables the quota. Default `5`.
- `RATE_LIMIT_WINDOW`: rate-limit window in seconds. Default `3600` (1 hour).
- `BOT_LANG`: language for user-facing messages, `en` or `es`. Default `en`. (Named `BOT_LANG`, not `LANG`, to avoid clashing with the system locale.)
- `SESSIONS_DB`: base path for the SQLite session store; the file is `<SESSIONS_DB>.sqlite3`. Default base `./downloads/sessions`.
- `LOG_LEVEL`: logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Default `INFO`.

## Install & Run

1) Create the bot with BotFather and copy the token.
2) Set up the environment:

- With `uv` (if you already use it):
  - `uv sync`
- With `pip`:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .`

3) Configure `.env` (see above).
4) Start the bot:

```
python main.py
```

5) In Telegram, send the bot a YouTube URL. You'll see title, duration and buttons to choose `audio` or `video`. The bot uploads the actual files (not just the path) with a friendly filename.

Project structure:

- `dropzone47/config.py`: env/config and logging setup.
- `dropzone47/utils.py`: filesystem, URL and formatting helpers.
- `dropzone47/i18n.py`: message catalog and `t()` translation helper.
- `dropzone47/ratelimit.py`: per-user sliding-window rate limiter.
- `dropzone47/session.py`: SQLite persistence and in-memory state.
- `dropzone47/download.py`: yt-dlp format selection, resolution ladder and download helpers.
- `dropzone47/bot.py`: Telegram handlers, concurrency queue and orchestration.
- `tests/`: unit tests.

## Docker

Build the image:

```
docker build -t dropzone47:0.2.2 .
```

Run the bot (mount a host folder for downloads and pass the token):

```
docker run --rm \
  -e TELEGRAM_BOT_TOKEN=123456:ABC... \
  -e DOWNLOAD_DIR=/data \
  -v $(pwd)/downloads:/data \
  --user $(id -u):$(id -g) \
  --name dropzone47 \
  dropzone47:0.2.2
```

Notes:

- The image installs `ffmpeg`. No ports are exposed; the bot uses long polling.
- Use `CLEANUP_AFTER_SEND=false` (env) to keep files in the mounted volume.
- If you mount a host directory to `/data`, ensure the container user can write to it. Options:
  - Run with your host UID/GID: `--user $(id -u):$(id -g)`
  - Or relax perms on the host dir: `chmod 777 downloads` (less secure)
  - The bot writes temporary cache under `/data/.cache/yt-dlp` by default.

### Docker Compose

1) Ensure `.env` contains your bot token (and any overrides):

```
TELEGRAM_BOT_TOKEN=123456:ABC...
# Optional: override size or quality
# TELEGRAM_MAX_MB=1900
# MAX_HEIGHT=720
# CLEANUP_AFTER_SEND=false

# For Linux: map your user/group to avoid permission issues on ./downloads
UID=$(id -u)
GID=$(id -g)
```

2) Start with Compose:

```
docker compose up -d --build
```

3) Logs and lifecycle:

```
docker compose logs -f
docker compose stop
docker compose down
```

### Commands

- `/downloads`: show status of your current/recent download.
- `/cancel`: cancel the in-progress download (if any).
- `/clear_downloads`: delete downloaded files associated with your last download.

During the download you'll see periodic progress updates in the caption of the original message (about every 5% or 2s, whichever comes first).

## Notes

- The bot tries to keep files under the configured size limit. If a video exceeds the limit, it steps down through the `VIDEO_HEIGHT_LADDER` resolutions until it fits (or sends best-effort if none do). For audio, it retries at a lower bitrate.
- Only http(s) URLs are accepted; anything else gets a friendly error. Playlists are not expanded (`noplaylist`) — only the single referenced video is downloaded.
- Downloads are stored per user under `DOWNLOAD_DIR/<user_id>/` so two users requesting the same video don't collide.
- At most `MAX_CONCURRENT_DOWNLOADS` downloads run simultaneously; further requests queue and start as slots free up. Each user may only have one active download at a time.
- Each user is limited to `RATE_LIMIT_MAX` downloads per `RATE_LIMIT_WINDOW` seconds.
- User-facing messages follow `BOT_LANG` (`en`/`es`); logs and code remain in English.
- Sessions are persisted in SQLite to allow continuation after restarts. Single-process; not intended for multi-worker deployments.
- To keep files locally, use `CLEANUP_AFTER_SEND=false`.

## Development

- Main libraries: `python-telegram-bot 22.x`, `yt-dlp`, `python-dotenv`.
- File uploads: files are opened in binary and passed as file handles to `send_audio`/`send_video`/`send_document` with an explicit `filename` to force a real upload and a visible name.
- Uses `effective_message` and guard checks to avoid type-checker warnings around potential `None` for `update.message`/`callback_query`.

Quality checks (as CI runs them):

```
ruff check .          # lint + import order
mypy .                # strict-ish type check
python -m unittest discover   # unit tests
```

## FAQ

- Why don't I see downloaded files locally?
  - Check `CLEANUP_AFTER_SEND`. If it's `true`, files are removed after sending. Set it to `false` to keep them.
- Telegram says the file is too large. What can I do?
  - Increase `TELEGRAM_MAX_MB` within Telegram limits or let the bot retry with a lower resolution/bitrate.
- Where are files stored?
  - Under `DOWNLOAD_DIR/<user_id>/` (default base `./downloads`) using the template `%(title).80s-%(id)s.%(ext)s`.
- I get errors about FFmpeg.
  - Ensure `ffmpeg` is installed and available on your system `PATH`.
