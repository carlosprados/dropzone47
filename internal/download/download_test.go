package download

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestVideoHeightLadder(t *testing.T) {
	got := VideoHeightLadder(720, []int{720, 480, 360, 240})
	if !reflect.DeepEqual(got, []int{720, 480, 360, 240}) {
		t.Fatalf("full ladder: got %v", got)
	}
	if got := VideoHeightLadder(480, []int{720, 480, 360, 240}); !reflect.DeepEqual(got, []int{480, 360, 240}) {
		t.Fatalf("capped: got %v", got)
	}
	// max always included even when not in the ladder.
	if got := VideoHeightLadder(1080, []int{480, 360}); !reflect.DeepEqual(got, []int{1080, 480, 360}) {
		t.Fatalf("includes max: got %v", got)
	}
	if got := VideoHeightLadder(720, nil); !reflect.DeepEqual(got, []int{720}) {
		t.Fatalf("empty ladder: got %v", got)
	}
}

func TestFindOutputFilesSkipsTempAndScopes(t *testing.T) {
	dir := t.TempDir()
	touch(t, filepath.Join(dir, "clip-VID123.mp4"))
	touch(t, filepath.Join(dir, "clip-VID123.mp3"))
	touch(t, filepath.Join(dir, "clip-VID123.mp4.part"))
	touch(t, filepath.Join(dir, "clip-VID123.f1.ytdl"))
	touch(t, filepath.Join(dir, "other-OTHER.mp4"))

	got := FindOutputFiles(dir, "VID123")
	want := []string{
		filepath.Join(dir, "clip-VID123.mp3"),
		filepath.Join(dir, "clip-VID123.mp4"),
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v want %v", got, want)
	}
}

func TestPickFilesForChoice(t *testing.T) {
	files := []string{"/t/v-a.mp4", "/t/v-a.webm", "/t/a-a.mp3", "/t/x.txt"}
	if got := PickFilesForChoice(files, Audio); !reflect.DeepEqual(got, []string{"/t/a-a.mp3"}) {
		t.Fatalf("audio: %v", got)
	}
	if got := PickFilesForChoice(files, Video); !reflect.DeepEqual(got, []string{"/t/v-a.mp4"}) {
		t.Fatalf("video prefers mp4: %v", got)
	}
	// falls back to other video containers when no mp4
	if got := PickFilesForChoice([]string{"/t/v.webm"}, Video); !reflect.DeepEqual(got, []string{"/t/v.webm"}) {
		t.Fatalf("video fallback: %v", got)
	}
}

func TestStableID(t *testing.T) {
	if got := StableID("https://www.youtube.com/watch?v=dQw4w9WgXcQ"); got != "dQw4w9WgXcQ" {
		t.Fatalf("youtube.com id: %q", got)
	}
	if got := StableID("https://youtu.be/abc123"); got != "abc123" {
		t.Fatalf("youtu.be id: %q", got)
	}
	// Non-YouTube URLs get a stable hash.
	a := StableID("https://example.com/x")
	b := StableID("https://example.com/x")
	if a == "" || a != b {
		t.Fatalf("hash not stable: %q vs %q", a, b)
	}
}

func TestBuildBaseName(t *testing.T) {
	got := BuildBaseName("My Video: Part #2!", "abc")
	if got != "My_Video_Part_2-abc" {
		t.Fatalf("basename: %q", got)
	}
}

func TestExceedsSizeLimit(t *testing.T) {
	dir := t.TempDir()
	small := filepath.Join(dir, "s.bin")
	if err := os.WriteFile(small, make([]byte, 1024), 0o644); err != nil {
		t.Fatal(err)
	}
	if ExceedsSizeLimit([]string{small}, 1) {
		t.Fatal("1KB should not exceed 1MB")
	}
}

func touch(t *testing.T, path string) {
	t.Helper()
	if err := os.WriteFile(path, []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
}
