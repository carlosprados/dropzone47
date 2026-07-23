package download

import (
	"context"
	"fmt"

	luxdl "github.com/iawia002/lux/downloader"
	"github.com/iawia002/lux/extractors"
)

// Lux is the pure-Go backend (github.com/iawia002/lux). It does a single best-quality
// grab: it does not honor an exact resolution or extract MP3 audio, and it cannot be
// interrupted mid-download (no context support). The Auto backend uses it only for the
// video happy-path and falls back to yt-dlp otherwise.
type Lux struct{}

// NewLux builds a lux backend.
func NewLux() *Lux { return &Lux{} }

func (l *Lux) Name() string { return "lux" }

// FetchInfo extracts metadata. lux does not expose a duration, so DurationSec is -1.
// lux extractors can panic on unsupported/changed sites, so we recover into an error.
func (l *Lux) FetchInfo(_ context.Context, url string) (info Info, err error) {
	defer func() {
		if r := recover(); r != nil {
			info, err = Info{}, fmt.Errorf("lux panicked: %v", r)
		}
	}()
	data, err := extractors.Extract(url, extractors.Options{})
	if err != nil {
		return Info{}, fmt.Errorf("lux extract: %w", err)
	}
	if len(data) == 0 || data[0] == nil {
		return Info{}, fmt.Errorf("lux: no data for %s", url)
	}
	d := data[0]
	if d.Err != nil {
		return Info{}, fmt.Errorf("lux extract: %w", d.Err)
	}
	return Info{Title: d.Title, ID: StableID(url), DurationSec: -1}, nil
}

// Fetch downloads the best available stream. It ignores the size ladder; a too-large
// or audio result is left for the caller/Auto to redirect to yt-dlp. lux internals can
// panic, so we recover into an error to let the caller fall back.
func (l *Lux) Fetch(ctx context.Context, req Request, onProgress ProgressFunc) (res Result, err error) {
	defer func() {
		if r := recover(); r != nil {
			res, err = Result{}, fmt.Errorf("lux panicked: %v", r)
		}
	}()
	if err := ctx.Err(); err != nil {
		return Result{}, err
	}
	data, err := extractors.Extract(req.URL, extractors.Options{})
	if err != nil {
		return Result{}, fmt.Errorf("lux extract: %w", err)
	}
	if len(data) == 0 || data[0] == nil || data[0].Err != nil {
		return Result{}, fmt.Errorf("lux: extraction failed for %s", req.URL)
	}

	emit(onProgress, Progress{Label: string(req.Format), Stage: StageDownloading, Percent: -1})

	dl := luxdl.New(luxdl.Options{
		OutputPath: req.DestDir,
		OutputName: req.BaseName,
		Silent:     true,
		AudioOnly:  req.Format == Audio,
	})
	if err := dl.Download(data[0]); err != nil {
		return Result{}, fmt.Errorf("lux download: %w", err)
	}

	files := PickFilesForChoice(FindOutputFiles(req.DestDir, req.ID), req.Format)
	if len(files) == 0 {
		return Result{}, fmt.Errorf("lux: no matching output for %s", req.ID)
	}
	return Result{Files: files}, nil
}
