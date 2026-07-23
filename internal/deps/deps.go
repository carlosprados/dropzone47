// Package deps performs a runtime preflight: it detects the OS/distro and checks that
// the external tools (ffmpeg, yt-dlp) are available, producing per-distro install help.
package deps

import (
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"
)

// Tool is the availability of an external binary.
type Tool struct {
	Name  string
	Found bool
	Path  string
}

// Report is the result of a preflight check.
type Report struct {
	OS         string // runtime.GOOS
	DistroID   string // e.g. "debian", "ubuntu", "raspbian" (linux only)
	DistroLike string // os-release ID_LIKE
	FFmpeg     Tool
	Ytdlp      Tool
}

func lookup(name string) Tool {
	p, err := exec.LookPath(name)
	return Tool{Name: name, Found: err == nil, Path: p}
}

// Check inspects the current system.
func Check() Report {
	id, like := detectDistro()
	return Report{
		OS:         runtime.GOOS,
		DistroID:   id,
		DistroLike: like,
		FFmpeg:     lookup("ffmpeg"),
		Ytdlp:      lookup("yt-dlp"),
	}
}

func detectDistro() (id, like string) {
	if runtime.GOOS != "linux" {
		return "", ""
	}
	b, err := os.ReadFile("/etc/os-release")
	if err != nil {
		return "", ""
	}
	for line := range strings.SplitSeq(string(b), "\n") {
		key, val, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		val = strings.Trim(strings.TrimSpace(val), `"`)
		switch strings.TrimSpace(key) {
		case "ID":
			id = strings.ToLower(val)
		case "ID_LIKE":
			like = strings.ToLower(val)
		}
	}
	return id, like
}

// Label is a human-readable system name.
func (r Report) Label() string {
	if r.DistroID != "" {
		return r.DistroID
	}
	return r.OS
}

// RequiredMissing lists the tools required for the given backend that are absent.
// ffmpeg is always required (merging/audio). yt-dlp is required unless the backend is
// forced to "lux".
func (r Report) RequiredMissing(backend string) []string {
	var missing []string
	if !r.FFmpeg.Found {
		missing = append(missing, "ffmpeg")
	}
	if backend != "lux" && !r.Ytdlp.Found {
		missing = append(missing, "yt-dlp")
	}
	return missing
}

// Instructions returns install guidance for whichever tools are missing. Empty when
// nothing is missing.
func (r Report) Instructions() string {
	if r.FFmpeg.Found && r.Ytdlp.Found {
		return ""
	}
	var b strings.Builder
	fmt.Fprintf(&b, "Detected system: %s\n", r.Label())

	if !r.FFmpeg.Found {
		b.WriteString("\nInstall ffmpeg (Debian / Ubuntu / Raspbian):\n")
		b.WriteString("  sudo apt update && sudo apt install -y ffmpeg\n")
	}
	if !r.Ytdlp.Found {
		b.WriteString("\nInstall yt-dlp — pick one:\n")
		b.WriteString("  # pip (Debian/Ubuntu/Raspbian may need a venv or --break-system-packages):\n")
		b.WriteString("  python3 -m pip install -U yt-dlp\n")
		b.WriteString("  # uv — persistent tool on PATH (avoids the PEP 668 restriction):\n")
		b.WriteString("  uv tool install yt-dlp\n")
		b.WriteString("  # uvx — run once without installing:\n")
		b.WriteString("  uvx yt-dlp <url>\n")
	}
	return b.String()
}
