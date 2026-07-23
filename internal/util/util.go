// Package util holds small, pure helpers shared across the app.
package util

import (
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
)

// IsValidURL reports whether s is a well-formed http(s) URL.
func IsValidURL(s string) bool {
	u, err := url.Parse(s)
	if err != nil {
		return false
	}
	return (u.Scheme == "http" || u.Scheme == "https") && u.Host != ""
}

// HumanizeDuration formats seconds as HH:MM:SS (or MM:SS below an hour).
func HumanizeDuration(seconds int) string {
	if seconds < 0 {
		return "unknown"
	}
	h := seconds / 3600
	m := (seconds % 3600) / 60
	s := seconds % 60
	if h > 0 {
		return fmt.Sprintf("%02d:%02d:%02d", h, m, s)
	}
	return fmt.Sprintf("%02d:%02d", m, s)
}

// SizeofFmt renders a byte count with a binary unit suffix.
func SizeofFmt(num float64) string {
	units := []string{"B", "KB", "MB", "GB"}
	for _, unit := range units {
		if num < 1024.0 {
			return strconv.FormatFloat(num, 'f', 1, 64) + " " + unit
		}
		num /= 1024.0
	}
	return strconv.FormatFloat(num, 'f', 1, 64) + " TB"
}

// UserDownloadDir returns (and creates) the per-user download directory under base.
func UserDownloadDir(base string, userID int64) (string, error) {
	path := filepath.Join(base, strconv.FormatInt(userID, 10))
	if err := os.MkdirAll(path, 0o755); err != nil {
		return "", err
	}
	return path, nil
}

// EnsureDir creates dir (and parents) if missing.
func EnsureDir(dir string) error {
	return os.MkdirAll(dir, 0o755)
}
