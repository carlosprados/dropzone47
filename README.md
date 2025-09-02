# dropzone47

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-22.x-28a745)
![yt-dlp](https://img.shields.io/badge/yt--dlp-active-orange)

> Fast, size‑aware YouTube downloader bot for Telegram. Shows progress, supports cancel, and uploads real files with friendly filenames.

Telegram bot to download YouTube content and send audio/video to the chat with size controls, configurable download folder, lightweight session persistence, visible progress (percent, speed, ETA), and cancel support.

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
- `AUDIO_KBITRATE`: MP3 audio bitrate (kbps). Default `128`.
- `SOCKET_TIMEOUT`: network timeout for `yt-dlp` (s). Default `30`.
- `YTDLP_RETRIES`: retry count for `yt-dlp`. Default `3`.
- `CLEANUP_AFTER_SEND`: whether to delete files after sending (`true`/`false`). In `.env.example` it's `false` to keep files.
- `SESSIONS_DB`: base path for `shelve` persistence. Default `./downloads/sessions`.
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
- `dropzone47/utils.py`: filesystem and formatting helpers.
- `dropzone47/session.py`: simple persistence and in-memory state.
- `dropzone47/download.py`: yt-dlp format selection and download helpers.
- `dropzone47/bot.py`: Telegram handlers and orchestration.
- `tests/`: unit tests for helpers.

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
- The bot tries to keep files under the configured size limit. If a video exceeds the limit, it retries with a lower resolution (e.g., 480p). For audio, it reduces bitrate if needed.
- Sessions are stored lightly on disk to allow continuation after simple restarts. Not intended for high concurrency/multiprocessing.
- To keep files locally, use `CLEANUP_AFTER_SEND=false`.

## Development
- Main libraries: `python-telegram-bot 22.x`, `yt-dlp`, `python-dotenv`.
- File uploads: files are opened in binary and passed as file handles to `send_audio`/`send_video`/`send_document` with an explicit `filename` to force a real upload and a visible name.
- Uses `effective_message` and guard checks to avoid Pyright warnings around potential `None` for `update.message`/`callback_query`.

## FAQ
- Why don't I see downloaded files locally?
  - Check `CLEANUP_AFTER_SEND`. If it's `true`, files are removed after sending. Set it to `false` to keep them.
- Telegram says the file is too large. What can I do?
  - Increase `TELEGRAM_MAX_MB` within Telegram limits or let the bot retry with a lower resolution/bitrate.
- Where are files stored?
  - By default under `./downloads` using the template `%(title).80s-%(id)s.%(ext)s`.
- I get errors about FFmpeg.
  - Ensure `ffmpeg` is installed and available on your system `PATH`.

## GitHub (About & Topics)
- Repository description (copy into GitHub “About”):
  - Telegram bot that downloads YouTube audio/video via yt-dlp, shows progress, and uploads actual files. Size-aware with automatic 480p/lower-bitrate fallback. Config via .env.
- Suggested topics:
  - `telegram-bot`, `python-telegram-bot`, `yt-dlp`, `youtube`, `downloader`, `ffmpeg`, `asyncio`, `python`, `bot`
