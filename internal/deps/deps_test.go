package deps

import (
	"strings"
	"testing"
)

func TestRequiredMissing(t *testing.T) {
	both := Report{FFmpeg: Tool{Found: true}, Ytdlp: Tool{Found: true}}
	if got := both.RequiredMissing("yt-dlp"); len(got) != 0 {
		t.Fatalf("nothing should be missing, got %v", got)
	}

	noFFmpeg := Report{FFmpeg: Tool{Found: false}, Ytdlp: Tool{Found: true}}
	if got := noFFmpeg.RequiredMissing("yt-dlp"); len(got) != 1 || got[0] != "ffmpeg" {
		t.Fatalf("expected [ffmpeg], got %v", got)
	}

	noYtdlp := Report{FFmpeg: Tool{Found: true}, Ytdlp: Tool{Found: false}}
	if got := noYtdlp.RequiredMissing("yt-dlp"); len(got) != 1 || got[0] != "yt-dlp" {
		t.Fatalf("expected [yt-dlp], got %v", got)
	}
	// With lux forced, yt-dlp is not required.
	if got := noYtdlp.RequiredMissing("lux"); len(got) != 0 {
		t.Fatalf("lux backend should not require yt-dlp, got %v", got)
	}
}

func TestInstructions(t *testing.T) {
	if s := (Report{FFmpeg: Tool{Found: true}, Ytdlp: Tool{Found: true}}).Instructions(); s != "" {
		t.Fatalf("no instructions when nothing missing, got %q", s)
	}

	r := Report{OS: "linux", DistroID: "raspbian", FFmpeg: Tool{Found: false}, Ytdlp: Tool{Found: false}}
	instr := r.Instructions()
	for _, want := range []string{"raspbian", "apt install -y ffmpeg", "pip install -U yt-dlp", "uv tool install yt-dlp", "uvx yt-dlp"} {
		if !strings.Contains(instr, want) {
			t.Errorf("instructions missing %q:\n%s", want, instr)
		}
	}
}
