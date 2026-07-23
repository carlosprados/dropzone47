// Package config defines the application configuration and how it is loaded
// (defaults < config file < environment < flags) via Viper.
package config

import (
	"strconv"
	"strings"
	"time"

	"github.com/spf13/viper"
)

// EnvPrefix is prepended to every environment variable, e.g. DROPZONE47_TELEGRAM_TOKEN.
const EnvPrefix = "DROPZONE47"

// Config holds all runtime tunables.
type Config struct {
	TelegramToken          string
	DownloadDir            string
	SessionsDB             string
	Downloader             string // lux | yt-dlp | auto
	Lang                   string // en | es
	LogLevel               string
	TelegramMaxMB          int
	MaxHeight              int
	VideoHeightLadder      []int
	AudioKbitrate          int
	SocketTimeout          int // seconds, passed to yt-dlp
	YtdlpRetries           int
	CleanupAfterSend       bool
	MaxConcurrentDownloads int
	RateLimitMax           int
	RateLimitWindow        time.Duration
}

// Keys are the canonical Viper keys (dash-separated so they map to CLI flags).
const (
	KeyTelegramToken    = "telegram-token"
	KeyDownloadDir      = "download-dir"
	KeySessionsDB       = "sessions-db"
	KeyDownloader       = "downloader"
	KeyLang             = "lang"
	KeyLogLevel         = "log-level"
	KeyTelegramMaxMB    = "telegram-max-mb"
	KeyMaxHeight        = "max-height"
	KeyVideoHeightLad   = "video-height-ladder"
	KeyAudioKbitrate    = "audio-kbitrate"
	KeySocketTimeout    = "socket-timeout"
	KeyYtdlpRetries     = "ytdlp-retries"
	KeyCleanupAfterSend = "cleanup-after-send"
	KeyMaxConcurrent    = "max-concurrent"
	KeyRateLimitMax     = "rate-limit-max"
	KeyRateLimitWindow  = "rate-limit-window"
)

// SetDefaults registers default values and environment binding on v.
func SetDefaults(v *viper.Viper) {
	v.SetEnvPrefix(EnvPrefix)
	v.SetEnvKeyReplacer(strings.NewReplacer("-", "_"))
	v.AutomaticEnv()

	v.SetDefault(KeyDownloadDir, "./downloads")
	v.SetDefault(KeySessionsDB, "./downloads/sessions")
	v.SetDefault(KeyDownloader, "auto")
	v.SetDefault(KeyLang, "en")
	v.SetDefault(KeyLogLevel, "info")
	v.SetDefault(KeyTelegramMaxMB, 1900)
	v.SetDefault(KeyMaxHeight, 720)
	v.SetDefault(KeyVideoHeightLad, "720,480,360,240")
	v.SetDefault(KeyAudioKbitrate, 128)
	v.SetDefault(KeySocketTimeout, 30)
	v.SetDefault(KeyYtdlpRetries, 3)
	v.SetDefault(KeyCleanupAfterSend, false)
	v.SetDefault(KeyMaxConcurrent, 2)
	v.SetDefault(KeyRateLimitMax, 5)
	v.SetDefault(KeyRateLimitWindow, time.Hour)
}

// Load materializes a Config from v.
func Load(v *viper.Viper) Config {
	maxConcurrent := v.GetInt(KeyMaxConcurrent)
	if maxConcurrent < 1 {
		maxConcurrent = 1
	}
	return Config{
		TelegramToken:          v.GetString(KeyTelegramToken),
		DownloadDir:            v.GetString(KeyDownloadDir),
		SessionsDB:             v.GetString(KeySessionsDB),
		Downloader:             strings.ToLower(v.GetString(KeyDownloader)),
		Lang:                   v.GetString(KeyLang),
		LogLevel:               v.GetString(KeyLogLevel),
		TelegramMaxMB:          v.GetInt(KeyTelegramMaxMB),
		MaxHeight:              v.GetInt(KeyMaxHeight),
		VideoHeightLadder:      ParseIntList(v.GetString(KeyVideoHeightLad)),
		AudioKbitrate:          v.GetInt(KeyAudioKbitrate),
		SocketTimeout:          v.GetInt(KeySocketTimeout),
		YtdlpRetries:           v.GetInt(KeyYtdlpRetries),
		CleanupAfterSend:       v.GetBool(KeyCleanupAfterSend),
		MaxConcurrentDownloads: maxConcurrent,
		RateLimitMax:           v.GetInt(KeyRateLimitMax),
		RateLimitWindow:        v.GetDuration(KeyRateLimitWindow),
	}
}

// ParseIntList parses a comma-separated list of ints, skipping invalid entries.
func ParseIntList(s string) []int {
	var out []int
	for _, part := range strings.Split(s, ",") {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		if n, err := strconv.Atoi(part); err == nil {
			out = append(out, n)
		}
	}
	return out
}
