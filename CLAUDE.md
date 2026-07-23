# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Telegram bot that downloads YouTube content via `yt-dlp` and uploads the resulting audio (MP3) or video (MP4) file back to the chat, with live progress, size-aware fallbacks, and cancel support. Runs via long polling — no web server, no exposed ports.

## Commands

```bash
# Setup (uv preferred)
uv sync                          # or: python -m venv .venv && source .venv/bin/activate && pip install -e .

# Run the bot (needs TELEGRAM_BOT_TOKEN in .env)
python main.py

# Lint / type-check (config in pyproject.toml)
ruff check .
mypy .

# Tests
python -m unittest discover -v                          # all
python -m unittest tests.test_utils                     # one module
python -m unittest tests.test_utils.TestUtils.test_sizeof_fmt   # one test

# Docker
docker compose up -d --build     # uses .env; maps ./downloads → /data; UID/GID from .env
docker compose logs -f
```

Requires **FFmpeg on PATH** (merges video+audio, extracts MP3). The Docker image bundles it.

## Architecture

Thin entrypoint `main.py` → `dropzone47.bot.run()`. The package is split by responsibility; the request flow crosses several modules:

1. **`config.py`** — loads `.env` (via `python-dotenv`), exposes all tunables as module-level constants (`TELEGRAM_TOKEN`, `DOWNLOAD_DIR`, `TELEGRAM_MAX_MB`, `MAX_HEIGHT`, `AUDIO_KBITRATE`, `CLEANUP_AFTER_SEND`, …) and sets up logging. Import config values, don't re-read `os.getenv`.
2. **`bot.py`** — all Telegram handlers and orchestration. Flow: user sends URL → `handle_url` fetches metadata (no download) and stores a session → inline buttons → `handle_choice` spawns `download_and_send_task` as an `asyncio.create_task` → that task downloads, applies size fallbacks, and uploads. Commands: `/start`, `/downloads`, `/cancel`, `/clear_downloads`.
3. **`download.py`** — all `yt-dlp` interaction: format-string building, options, the progress hook, output-file discovery/selection, cleanup. `ytdlp_download_with_progress` runs the blocking `YoutubeDL.download` in a thread executor.
4. **`session.py`** — two in-memory dicts keyed by `user_id`: `user_sessions` (pending URL+metadata) and `user_downloads` (task state). `shelve` gives minimal disk persistence for `user_sessions` to survive restarts.
5. **`utils.py`** — pure helpers (duration/size formatting, disk-space check, dir creation). These are what the unit tests cover.

### Concurrency & cancellation model

- **One active download per user.** `handle_choice` refuses a new request if the user's task status is in `{queued, downloading, sending}`.
- The download runs in a thread executor. Cancellation is cooperative: `/cancel` sets `task["cancel"] = True` and calls `async_task.cancel()`. The **progress hook** checks that flag and raises `RuntimeError("cancelled")`, which `ytdlp_download_with_progress` re-raises as `asyncio.CancelledError`. So cancellation only takes effect on the next progress callback.
- The sync progress hook (runs in the executor thread) schedules caption edits on the loop with `loop.call_soon_threadsafe(asyncio.create_task, coro)`. Keep hook work non-blocking and loop-safe.

### Size-aware fallbacks (the core UX logic, in `download_and_send_task`)

After each download, files are size-checked against `TELEGRAM_MAX_MB`. If too big:
- **Video** → step down through `video_height_ladder(MAX_HEIGHT)` (from `VIDEO_HEIGHT_LADDER`, capped at `MAX_HEIGHT`, always starting at `MAX_HEIGHT`) until it fits, or send best-effort on the last rung.
- **Audio** → retry once at ≤96 kbps.

Between retries the current file is deleted with `force_remove` (NOT `safe_cleanup`, which is gated by `CLEANUP_AFTER_SEND`) — otherwise yt-dlp sees the existing output file and skips the re-download, silently re-sending the too-big file.

Files are written to a **per-user directory** `DOWNLOAD_DIR/<user_id>/` (via `user_download_dir`) to prevent cross-user collisions when two users request the same video. Within that dir they are located by glob `*-{video_id}.*` (template `%(title).80s-%(id)s.%(ext)s`, `restrictfilenames=True`), skipping partial/temp extensions (`.part`, `.ytdl`, …), then filtered by extension (`pick_files_for_choice`): audio → `.mp3`; video → prefer `.mp4`, else `.mkv/.webm/.mov`. The download-facing functions (`build_outtmpl`, `find_output_files`, `ytdlp_download_with_progress`) all take `dest_dir` explicitly — don't reintroduce reliance on the global `DOWNLOAD_DIR` for output paths.

## Conventions & gotchas

- **yt-dlp cache is forced under `DOWNLOAD_DIR/.cache/yt-dlp`** (and `XDG_CACHE_HOME` in Docker) to avoid `$HOME` permission failures in containers. Don't remove this — it was the subject of several fixes.
- **Audio-bitrate fallback** is passed as the `audio_kbps` parameter down to the yt-dlp postprocessor. It is NOT read from `os.environ`/config at retry time — an earlier version mutated `os.environ["AUDIO_KBITRATE"]`, which was a dead no-op because `config.AUDIO_KBITRATE` is bound once at import. Keep passing it as a parameter.
- **Config constants are read once at import** (`config.py`). Runtime changes to env vars do not affect them — thread overrides as parameters instead.
- **`noplaylist=True` and URL validation** (`is_valid_url`) are enforced; `handle_url` rejects non-http(s) input, and downloads never fan out to a full playlist.
- **Cancellation is flag-only**: `/cancel` sets `task["cancel"]` and the yt-dlp progress hook aborts the thread. Do NOT call `async_task.cancel()` — it races the executor thread and adds no benefit.
- Handlers guard `update.effective_message` / `callback_query` for `None`, and narrow `query.message` with `isinstance(..., Message)` (it may be a `MaybeInaccessibleMessage`). Keep those guards when adding handlers.
- `CLEANUP_AFTER_SEND` gates `safe_cleanup`; set `false` to keep files in the mounted volume.
- CI (`.github/workflows`) runs ruff + mypy (strict-ish: `disallow_untyped_defs`) + import check + `unittest`. **Type all new defs** (including test methods) and keep lines ≤100 cols. `tests/` needs `__init__.py` for `unittest discover` to find tests from the repo root.

## Known limitations (not yet addressed)

- No rate limiting / per-chat quotas — the bot can be abused if exposed publicly.
- `shelve` persistence is single-process only; not safe for concurrent/multi-worker deployment.
- Only one active download per user; no explicit queue.
- No i18n — user-facing strings are English only.
