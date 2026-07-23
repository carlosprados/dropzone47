// Package download abstracts video/audio downloading behind a Downloader
// interface with lux (pure Go) and yt-dlp (external binary) backends.
package download

import (
	"context"
	"crypto/sha1"
	"encoding/hex"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// Format is the kind of media requested.
type Format string

const (
	Audio Format = "audio"
	Video Format = "video"
)

// Info is lightweight metadata about a URL (no download performed).
type Info struct {
	Title       string
	ID          string
	DurationSec int
	Thumbnail   string
}

// Request describes a download. A backend fits the result under MaxMB, stepping the
// HeightLadder (video) or lowering the bitrate (audio) when it supports doing so.
type Request struct {
	URL          string
	ID           string // stable id used to name/locate output files
	BaseName     string // output basename without extension: "<title>-<id>"
	Format       Format
	MaxHeight    int
	AudioKbps    int
	MaxMB        int
	HeightLadder []int
	DestDir      string
}

// Result is the outcome of a successful download.
type Result struct {
	Files []string
}

// Progress stage constants.
const (
	StageDownloading = "downloading"
	StageProcessing  = "processing"
	StageFallbackVid = "fallback_video" // Height carries the new resolution
	StageFallbackAud = "fallback_audio"
)

// Progress is a coarse or fine progress update from a backend.
type Progress struct {
	Label      string
	Stage      string
	Percent    int // -1 when unknown
	SpeedBytes float64
	ETASeconds int
	Height     int // set for StageFallbackVid
}

// ProgressFunc receives progress updates. It must be non-blocking and safe to
// call from another goroutine.
type ProgressFunc func(Progress)

// Downloader is a media backend.
type Downloader interface {
	Name() string
	FetchInfo(ctx context.Context, url string) (Info, error)
	Fetch(ctx context.Context, req Request, onProgress ProgressFunc) (Result, error)
}

// tempExts are partial/temporary extensions written mid-download.
var tempExts = []string{".part", ".ytdl", ".temp", ".tmp"}

// VideoHeightLadder returns descending distinct heights to try, capped at maxHeight
// and always including maxHeight as the first (best) rung.
func VideoHeightLadder(maxHeight int, ladder []int) []int {
	set := map[int]struct{}{maxHeight: {}}
	for _, h := range ladder {
		if h > 0 && h <= maxHeight {
			set[h] = struct{}{}
		}
	}
	out := make([]int, 0, len(set))
	for h := range set {
		out = append(out, h)
	}
	sort.Sort(sort.Reverse(sort.IntSlice(out)))
	return out
}

// FindOutputFiles returns final artifacts for videoID in destDir (temp files skipped).
func FindOutputFiles(destDir, videoID string) []string {
	matches, err := filepath.Glob(filepath.Join(destDir, "*-"+videoID+".*"))
	if err != nil {
		return nil
	}
	var out []string
	for _, m := range matches {
		if !hasTempExt(m) {
			out = append(out, m)
		}
	}
	sort.Strings(out)
	return out
}

func hasTempExt(path string) bool {
	lower := strings.ToLower(path)
	for _, ext := range tempExts {
		if strings.HasSuffix(lower, ext) {
			return true
		}
	}
	return false
}

// PickFilesForChoice filters files by the requested format.
func PickFilesForChoice(files []string, format Format) []string {
	switch format {
	case Audio:
		return filterByExt(files, ".mp3")
	case Video:
		if vids := filterByExt(files, ".mp4"); len(vids) > 0 {
			return vids
		}
		return filterByExt(files, ".mkv", ".webm", ".mov")
	default:
		return nil
	}
}

func filterByExt(files []string, exts ...string) []string {
	var out []string
	for _, f := range files {
		lower := strings.ToLower(f)
		for _, ext := range exts {
			if strings.HasSuffix(lower, ext) {
				out = append(out, f)
				break
			}
		}
	}
	return out
}

// ExceedsSizeLimit reports whether any file is larger than maxMB megabytes.
func ExceedsSizeLimit(files []string, maxMB int) bool {
	limit := int64(maxMB) * 1024 * 1024
	for _, f := range files {
		if fi, err := os.Stat(f); err == nil && fi.Size() > limit {
			return true
		}
	}
	return false
}

// ForceRemove deletes files unconditionally, ignoring missing ones. It is used to
// discard a too-large artifact before retrying at lower quality (otherwise a backend
// may see the existing output and skip the re-download).
func ForceRemove(files []string) {
	for _, f := range files {
		_ = os.Remove(f)
	}
}

// StableID derives a stable id from a URL: the YouTube video id when present,
// otherwise a short hash of the URL. Used so both backends produce predictable
// filenames we can locate afterwards.
func StableID(rawurl string) string {
	if u, err := url.Parse(rawurl); err == nil {
		host := strings.ToLower(u.Host)
		if strings.Contains(host, "youtube.com") {
			if v := u.Query().Get("v"); v != "" {
				return sanitizeID(v)
			}
		}
		if strings.Contains(host, "youtu.be") {
			if seg := strings.Trim(u.Path, "/"); seg != "" {
				return sanitizeID(seg)
			}
		}
	}
	sum := sha1.Sum([]byte(rawurl))
	return hex.EncodeToString(sum[:])[:11]
}

func sanitizeID(s string) string {
	var b strings.Builder
	for _, r := range s {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '_' || r == '-' {
			b.WriteRune(r)
		}
		if b.Len() >= 16 {
			break
		}
	}
	if b.Len() == 0 {
		return "id"
	}
	return b.String()
}

// BuildBaseName returns "<sanitized-title>-<id>" (title capped at 80 chars).
func BuildBaseName(title, id string) string {
	return sanitizeTitle(title) + "-" + id
}

func sanitizeTitle(title string) string {
	var b strings.Builder
	for _, r := range title {
		switch {
		case (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '_' || r == '-' || r == '.':
			b.WriteRune(r)
		case r == ' ':
			b.WriteRune('_')
		}
		if b.Len() >= 80 {
			break
		}
	}
	return b.String()
}

// outTmpl is the yt-dlp output template within a destination directory using our
// controlled basename and yt-dlp's %(ext)s for the extension.
func outTmpl(destDir, baseName string) string {
	return filepath.Join(destDir, baseName+".%(ext)s")
}
