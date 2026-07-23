// Package cmd defines the dropzone47 command-line interface (Cobra + Viper).
//
// Every command and flag carries help text and examples so the binary is fully
// self-describing: `dropzone47 --help` and `dropzone47 <cmd> --help` reveal the whole
// surface, for humans and for AI agents alike.
package cmd

import (
	"fmt"
	"log/slog"
	"os"
	"strings"

	"github.com/spf13/cobra"
	"github.com/spf13/pflag"
	"github.com/spf13/viper"

	"github.com/carlosprados/dropzone47/internal/config"
	"github.com/carlosprados/dropzone47/internal/download"
)

var (
	v       = viper.New()
	cfgFile string
)

var rootCmd = &cobra.Command{
	Use:   "dropzone47",
	Short: "Size-aware YouTube downloader — Telegram bot and CLI",
	Long: `dropzone47 downloads YouTube audio/video using lux (pure Go) with an
automatic fallback to yt-dlp, keeping files under Telegram's size limit.

Run it as a Telegram bot (serve) or download straight to disk (get).

Configuration precedence (low to high): defaults < config file < environment
(DROPZONE47_*) < command-line flags.`,
	SilenceUsage:  true,
	SilenceErrors: true,
	PersistentPreRunE: func(cmd *cobra.Command, _ []string) error {
		if cfgFile != "" {
			v.SetConfigFile(cfgFile)
			if err := v.ReadInConfig(); err != nil {
				return fmt.Errorf("read config: %w", err)
			}
		}
		// Explicitly-set flags win over env/config/default without hitting the
		// viper/pflag default-shadowing trap.
		cmd.Flags().Visit(func(f *pflag.Flag) {
			v.Set(f.Name, f.Value.String())
		})
		return nil
	},
}

// Execute runs the root command.
func Execute() error { return rootCmd.Execute() }

func init() {
	config.SetDefaults(v)

	pf := rootCmd.PersistentFlags()
	pf.StringVar(&cfgFile, "config", "", "config file (yaml)")
	pf.String(config.KeyTelegramToken, "", "Telegram bot token (env DROPZONE47_TELEGRAM_TOKEN)")
	pf.String(config.KeyDownloader, "", "download backend: lux | yt-dlp | auto (default auto)")
	pf.String(config.KeyDownloadDir, "", "directory for downloads (default ./downloads)")
	pf.String(config.KeySessionsDB, "", "SQLite session store base path (default ./downloads/sessions)")
	pf.String(config.KeyLogLevel, "", "log level: debug|info|warn|error (default info)")
	pf.String(config.KeyLang, "", "bot language: en | es (default en)")
	pf.Int(config.KeyTelegramMaxMB, 0, "max upload size in MB (default 1900)")
	pf.Int(config.KeyMaxHeight, 0, "max video resolution (default 720)")
	pf.String(config.KeyVideoHeightLad, "", "descending resolutions to try on oversize (default 720,480,360,240)")
	pf.Int(config.KeyAudioKbitrate, 0, "MP3 bitrate in kbps (default 128)")
	pf.Int(config.KeySocketTimeout, 0, "yt-dlp socket timeout seconds (default 30)")
	pf.Int(config.KeyYtdlpRetries, 0, "yt-dlp retry count (default 3)")
	pf.Bool(config.KeyCleanupAfterSend, false, "delete files after sending (default false)")

	rootCmd.AddCommand(serveCmd, getCmd, configCmd, versionCmd)
}

// newLogger builds a slog logger at the configured level.
func newLogger(level string) *slog.Logger {
	var lvl slog.Level
	switch strings.ToLower(level) {
	case "debug":
		lvl = slog.LevelDebug
	case "warn", "warning":
		lvl = slog.LevelWarn
	case "error":
		lvl = slog.LevelError
	default:
		lvl = slog.LevelInfo
	}
	return slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: lvl}))
}

// buildDownloader constructs the composed backend for the configured selection.
func buildDownloader(cfg config.Config, log *slog.Logger) download.Downloader {
	lux := download.NewLux()
	yt := download.NewYtdlp(cfg.SocketTimeout, cfg.YtdlpRetries)
	forced := ""
	switch cfg.Downloader {
	case download.BackendLux:
		forced = download.BackendLux
	case download.BackendYtdlp:
		forced = download.BackendYtdlp
	}
	return download.NewAuto(lux, yt, forced, log)
}
