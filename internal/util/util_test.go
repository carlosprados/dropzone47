package util

import "testing"

func TestIsValidURL(t *testing.T) {
	cases := map[string]bool{
		"https://youtu.be/abc":     true,
		"http://example.com/x?y=1": true,
		"not a url":                false,
		"ftp://host/file":          false,
		"youtube.com/watch?v=abc":  false,
		"":                         false,
	}
	for in, want := range cases {
		if got := IsValidURL(in); got != want {
			t.Errorf("IsValidURL(%q)=%v want %v", in, got, want)
		}
	}
}

func TestHumanizeDuration(t *testing.T) {
	cases := map[int]string{
		-1:   "unknown",
		65:   "01:05",
		3605: "01:00:05",
	}
	for in, want := range cases {
		if got := HumanizeDuration(in); got != want {
			t.Errorf("HumanizeDuration(%d)=%q want %q", in, got, want)
		}
	}
}

func TestSizeofFmt(t *testing.T) {
	cases := map[float64]string{
		500:     "500.0 B",
		1536:    "1.5 KB",
		1048576: "1.0 MB",
	}
	for in, want := range cases {
		if got := SizeofFmt(in); got != want {
			t.Errorf("SizeofFmt(%v)=%q want %q", in, got, want)
		}
	}
}
