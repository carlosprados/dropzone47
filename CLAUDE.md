# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Go rewrite of a size-aware YouTube downloader that is both a **Telegram bot** and a
**CLI**. It downloads audio/video with **lux** (pure Go) and falls back to **yt-dlp**
automatically. Long polling; no web server. The original Python version lives in
`legacy/` for reference — do not edit it for new work.

## Commands

```bash
go build -o dropzone47 .          # build the binary
go build ./...                    # compile everything
go vet ./...                      # static checks
gofmt -l cmd internal main.go     # formatting check (must print nothing)
go test ./...                     # all tests
go test ./internal/download/...   # one package
go test ./internal/i18n -run TestSpanish   # one test

# Try it without Telegram:
go run . get --format audio -o /tmp/out "https://youtu.be/<id>"
go run . config show
go run . version
```

Requires **FFmpeg** and **yt-dlp** on `PATH` (yt-dlp is the fallback backend and is
effectively required, since lux's YouTube support is unreliable).

## Architecture

Entrypoint `main.go` → `cmd.Execute()` (Cobra). Config flows through Viper.

- **`cmd/`** — Cobra commands: `serve` (bot), `get` (direct download), `config show`,
  `version`. `root.go` defines persistent flags and, in `PersistentPreRunE`, copies
  **only the flags the user actually set** into Viper (`Flags().Visit` + `v.Set`) to
  dodge the viper/pflag default-shadowing trap. Every command has `Long`+`Example` help
  so the binary is self-describing for humans and AIs.
- **`internal/config`** — `Config` struct; `SetDefaults(v)` (defaults + `DROPZONE47_*`
  env binding) and `Load(v) Config`. Precedence: defaults < file < env < flags.
- **`internal/download`** — the `Downloader` interface and helpers:
  - `Downloader{ Name; FetchInfo; Fetch }`. **`Fetch` does the whole job for one request,
    including the size ladder** (video) / bitrate drop (audio). Backends: `Lux`, `Ytdlp`,
    `Auto`.
  - `Auto` composition: metadata prefers yt-dlp; **audio → yt-dlp** (lux can't reliably
    make MP3); **video → lux, then yt-dlp** on failure or oversize.
  - Filenames are controlled by us: `BuildBaseName(title,id)` = `<sanitized-title>-<id>`,
    where `id` is `StableID(url)` (YouTube id, else URL hash). Both backends write
    `<basename>.<ext>`; `FindOutputFiles(dir,id)` globs `*-<id>.*` and skips temp exts.
  - `ForceRemove` (unconditional) is used between ladder rungs so a backend re-downloads
    instead of skipping the existing too-big file.
- **`internal/bot`** — Telegram handlers (`go-telegram/bot`), the concurrency queue, rate
  limiting, per-user task state, cancellation, progress→caption throttling.
- **`internal/session`** — SQLite store (`modernc.org/sqlite`, no cgo), `<base>.sqlite3`.
- **`internal/ratelimit`** — sliding-window `Limiter` (injectable clock for tests).
- **`internal/i18n`** — `Translator` + `MESSAGES` catalog (en/es), fmt positional verbs.
- **`internal/util`** — URL validation, duration/size formatting, per-user dir.

### Concurrency, queue & cancellation (in `internal/bot`)

- **Queue**: a buffered channel `slots chan struct{}` of size `max-concurrent`. A download
  goroutine acquires a slot with `select { case slots<-{}: ; case <-ctx.Done(): }`; while
  waiting it stays `queued`.
- **One active download per user**; `handle`/callback refuses a second.
- **Rate limit**: `limiter.Allow(userID)` before queueing.
- **Cancellation is real**: each download has its own `context.CancelFunc` stored in the
  task. `/cancel` calls it; yt-dlp runs via `exec.CommandContext`, so the child process is
  killed. Caveat: **lux ignores context** (no ctx support) — an in-progress lux download
  can't be interrupted mid-stream.
- `tasks map[int64]*task` guarded by `b.mu`; use `setStatus` for transitions.

### Progress fidelity differs by backend

yt-dlp gives fine `%` (parsed from `--progress-template`); **lux only emits a coarse
"downloading" tick** (no programmatic percent). Don't assume smooth progress on the lux
path.

## Conventions & gotchas

- **lux panics.** Its extractor can nil-panic on YouTube. `Lux.FetchInfo`/`Fetch` use
  `defer recover()` with named returns to convert panics into errors so `Auto` falls back.
  Keep that recovery if you touch lux.
- **All user-facing strings go through `i18n.T`** — add new keys to BOTH `en` and `es`
  (a test enforces matching keys). Logs/errors stay English.
- **Config is read once via `Load(v)`** at command start; pass values down, don't reach
  for globals.
- yt-dlp output uses our literal basename + `%(ext)s` and `--force-overwrites`; don't
  reintroduce `%(id)s` templating (id there ≠ our StableID).
- CI (`.github/workflows/ci.yml`) runs gofmt check + `go vet` + `go build` + `go test`.
  Keep it green; run `gofmt -w` before committing.

## Known limitations

- lux YouTube support is unreliable (hence the yt-dlp fallback); pure-lux mode may fail.
- SQLite store is single-process; not for multi-worker deployment.
- No abuse controls beyond the per-user rate limit.
- lux downloads can't be cancelled mid-stream (no context support).
