package download

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
)

// Ytdlp downloads via the external yt-dlp binary. It is the reliable fallback and
// provides fine-grained progress plus honest resolution/bitrate control.
type Ytdlp struct {
	Bin           string
	SocketTimeout int
	Retries       int
}

// NewYtdlp builds a yt-dlp backend.
func NewYtdlp(socketTimeout, retries int) *Ytdlp {
	return &Ytdlp{Bin: "yt-dlp", SocketTimeout: socketTimeout, Retries: retries}
}

func (y *Ytdlp) Name() string { return "yt-dlp" }

// Available reports whether the yt-dlp binary is on PATH.
func (y *Ytdlp) Available() bool {
	_, err := exec.LookPath(y.Bin)
	return err == nil
}

func (y *Ytdlp) cacheDir(destDir string) string {
	return filepath.Join(destDir, ".cache", "yt-dlp")
}

type ytdlpInfo struct {
	Title     string   `json:"title"`
	ID        string   `json:"id"`
	Duration  *float64 `json:"duration"`
	Thumbnail string   `json:"thumbnail"`
}

// FetchInfo returns metadata without downloading.
func (y *Ytdlp) FetchInfo(ctx context.Context, url string) (Info, error) {
	cache := filepath.Join(os.TempDir(), "dropzone47-ytdlp-cache")
	cmd := exec.CommandContext(ctx, y.Bin,
		"-J", "--no-playlist", "--no-warnings", "--quiet",
		"--cache-dir", cache, url,
	)
	out, err := cmd.Output()
	if err != nil {
		return Info{}, fmt.Errorf("yt-dlp info: %w", err)
	}
	var raw ytdlpInfo
	if err := json.Unmarshal(out, &raw); err != nil {
		return Info{}, fmt.Errorf("yt-dlp info decode: %w", err)
	}
	dur := -1
	if raw.Duration != nil {
		dur = int(*raw.Duration)
	}
	return Info{Title: raw.Title, ID: raw.ID, DurationSec: dur, Thumbnail: raw.Thumbnail}, nil
}

// Fetch downloads and fits the result under req.MaxMB, stepping the ladder (video)
// or lowering the bitrate once (audio).
func (y *Ytdlp) Fetch(ctx context.Context, req Request, onProgress ProgressFunc) (Result, error) {
	if req.Format == Audio {
		return y.fetchAudio(ctx, req, onProgress)
	}
	return y.fetchVideo(ctx, req, onProgress)
}

func (y *Ytdlp) fetchVideo(ctx context.Context, req Request, onProgress ProgressFunc) (Result, error) {
	ladder := VideoHeightLadder(req.MaxHeight, req.HeightLadder)
	var files []string
	for i, height := range ladder {
		label := "video"
		if i > 0 {
			label = fmt.Sprintf("video (%dp)", height)
			emit(onProgress, Progress{Stage: StageFallbackVid, Height: height, Percent: -1})
		}
		var err error
		files, err = y.one(ctx, req, height, 0, label, onProgress)
		if err != nil {
			return Result{}, err
		}
		if !ExceedsSizeLimit(files, req.MaxMB) {
			break
		}
		if i < len(ladder)-1 {
			ForceRemove(files)
		}
	}
	return Result{Files: files}, nil
}

func (y *Ytdlp) fetchAudio(ctx context.Context, req Request, onProgress ProgressFunc) (Result, error) {
	files, err := y.one(ctx, req, req.MaxHeight, req.AudioKbps, "audio", onProgress)
	if err != nil {
		return Result{}, err
	}
	if ExceedsSizeLimit(files, req.MaxMB) {
		emit(onProgress, Progress{Stage: StageFallbackAud, Percent: -1})
		ForceRemove(files)
		kbps := min(req.AudioKbps, 96)
		files, err = y.one(ctx, req, req.MaxHeight, kbps, fmt.Sprintf("audio (%dkbps)", kbps), onProgress)
		if err != nil {
			return Result{}, err
		}
	}
	return Result{Files: files}, nil
}

// one runs a single yt-dlp invocation at the given height/bitrate and returns the
// output files for req.ID.
func (y *Ytdlp) one(ctx context.Context, req Request, height, audioKbps int, label string, onProgress ProgressFunc) ([]string, error) {
	if err := os.MkdirAll(req.DestDir, 0o755); err != nil {
		return nil, err
	}
	cache := y.cacheDir(req.DestDir)
	_ = os.MkdirAll(cache, 0o755)

	format := "bestaudio/best"
	if req.Format == Video {
		format = fmt.Sprintf("bestvideo[height<=%d]+bestaudio/best[height<=%d]/best", height, height)
	}

	args := []string{
		"--no-playlist", "--no-warnings", "--newline", "--force-overwrites",
		"-f", format,
		"-o", outTmpl(req.DestDir, req.BaseName),
		"--cache-dir", cache,
		"--socket-timeout", strconv.Itoa(y.SocketTimeout),
		"--retries", strconv.Itoa(y.Retries),
		"--progress-template",
		"dlprog|%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|%(progress.speed)s|%(progress.eta)s",
	}
	if req.Format == Audio {
		args = append(args, "-x", "--audio-format", "mp3", "--audio-quality", fmt.Sprintf("%dK", audioKbps))
	} else {
		args = append(args, "--merge-output-format", "mp4")
	}
	args = append(args, req.URL)

	cmd := exec.CommandContext(ctx, y.Bin, args...)
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		return nil, err
	}

	scanner := bufio.NewScanner(stdout)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if strings.HasPrefix(line, "dlprog|") {
			if p, ok := parseYtdlpProgress(line, label); ok {
				emit(onProgress, p)
			}
		} else if strings.Contains(line, "[Merger]") || strings.Contains(line, "[ExtractAudio]") {
			emit(onProgress, Progress{Label: label, Stage: StageProcessing, Percent: -1})
		}
	}
	if err := cmd.Wait(); err != nil {
		return nil, fmt.Errorf("yt-dlp download: %w", err)
	}

	files := PickFilesForChoice(FindOutputFiles(req.DestDir, req.ID), req.Format)
	if len(files) == 0 {
		return nil, fmt.Errorf("yt-dlp: no output file for %s", req.ID)
	}
	return files, nil
}

func emit(onProgress ProgressFunc, p Progress) {
	if onProgress != nil {
		onProgress(p)
	}
}

func parseYtdlpProgress(line, label string) (Progress, bool) {
	parts := strings.Split(line, "|")
	if len(parts) != 6 {
		return Progress{}, false
	}
	downloaded := parseFloat(parts[1])
	total := parseFloat(parts[2])
	if total <= 0 {
		total = parseFloat(parts[3])
	}
	pct := -1
	if total > 0 {
		pct = int(downloaded * 100 / total)
	}
	return Progress{
		Label:      label,
		Stage:      StageDownloading,
		Percent:    pct,
		SpeedBytes: parseFloat(parts[4]),
		ETASeconds: int(parseFloat(parts[5])),
	}, true
}

func parseFloat(s string) float64 {
	s = strings.TrimSpace(s)
	if s == "" || s == "NA" || s == "None" {
		return 0
	}
	f, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return 0
	}
	return f
}
