package download

import (
	"context"
	"fmt"
	"log/slog"
)

// Backend selection strings.
const (
	BackendLux   = "lux"
	BackendYtdlp = "yt-dlp"
	BackendAuto  = "auto"
)

// Auto composes the backends: lux for the video happy-path (fast, pure Go), yt-dlp for
// audio, for size-limited retries, and whenever lux fails. A forced backend bypasses
// the composition.
type Auto struct {
	lux    *Lux
	ytdlp  *Ytdlp
	forced string // "", BackendLux, or BackendYtdlp
	log    *slog.Logger
}

// NewAuto builds the composed backend. forced is "" for auto behavior, or a specific
// backend name to always use.
func NewAuto(lux *Lux, ytdlp *Ytdlp, forced string, log *slog.Logger) *Auto {
	if log == nil {
		log = slog.Default()
	}
	return &Auto{lux: lux, ytdlp: ytdlp, forced: forced, log: log}
}

func (a *Auto) Name() string {
	if a.forced != "" {
		return a.forced
	}
	return BackendAuto
}

// FetchInfo tries the preferred backend and falls back to the other.
func (a *Auto) FetchInfo(ctx context.Context, url string) (Info, error) {
	switch a.forced {
	case BackendLux:
		return a.lux.FetchInfo(ctx, url)
	case BackendYtdlp:
		return a.ytdlp.FetchInfo(ctx, url)
	}
	// Auto: yt-dlp gives richer metadata (duration); prefer it, fall back to lux.
	if a.ytdlp.Available() {
		if info, err := a.ytdlp.FetchInfo(ctx, url); err == nil {
			return info, nil
		} else {
			a.log.Warn("yt-dlp FetchInfo failed, trying lux", "err", err)
		}
	}
	return a.lux.FetchInfo(ctx, url)
}

// Fetch downloads according to the composition rules.
func (a *Auto) Fetch(ctx context.Context, req Request, onProgress ProgressFunc) (Result, error) {
	switch a.forced {
	case BackendLux:
		return a.lux.Fetch(ctx, req, onProgress)
	case BackendYtdlp:
		return a.ytdlp.Fetch(ctx, req, onProgress)
	}

	// Audio: lux does not reliably produce MP3, so go straight to yt-dlp.
	if req.Format == Audio {
		return a.ytdlp.Fetch(ctx, req, onProgress)
	}

	// Video happy-path: try lux, accept only if the result fits the size limit.
	res, err := a.lux.Fetch(ctx, req, onProgress)
	if err == nil && !ExceedsSizeLimit(res.Files, req.MaxMB) {
		return res, nil
	}
	if err != nil {
		a.log.Warn("lux failed, falling back to yt-dlp", "url", req.URL, "err", err)
	} else {
		a.log.Info("lux result too large, falling back to yt-dlp ladder", "url", req.URL)
		ForceRemove(res.Files)
	}
	if !a.ytdlp.Available() {
		return Result{}, fmt.Errorf("lux failed and yt-dlp is not installed: %w", err)
	}
	return a.ytdlp.Fetch(ctx, req, onProgress)
}
