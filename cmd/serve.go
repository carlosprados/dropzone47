package cmd

import (
	"context"
	"errors"
	"os"
	"os/signal"
	"syscall"

	"github.com/spf13/cobra"

	"github.com/carlosprados/dropzone47/internal/bot"
	"github.com/carlosprados/dropzone47/internal/config"
	"github.com/carlosprados/dropzone47/internal/session"
)

var serveCmd = &cobra.Command{
	Use:   "serve",
	Short: "Run the Telegram bot (long polling)",
	Long: `Start the Telegram bot and serve download requests over long polling.

Users send a YouTube URL, pick audio or video, and receive the file. Downloads are
capped by a global concurrency limit (a queue) and a per-user rate limit.

Requires a bot token via --telegram-token or DROPZONE47_TELEGRAM_TOKEN, and ffmpeg on
PATH. No network ports are opened.`,
	Example: `  dropzone47 serve
  DROPZONE47_TELEGRAM_TOKEN=123:abc dropzone47 serve --lang es --max-concurrent 3
  dropzone47 serve --downloader yt-dlp --rate-limit-max 10 --rate-limit-window 30m`,
	RunE: func(cmd *cobra.Command, _ []string) error {
		cfg := config.Load(v)
		log := newLogger(cfg.LogLevel)
		if cfg.TelegramToken == "" {
			return errors.New("telegram token required: set --telegram-token or DROPZONE47_TELEGRAM_TOKEN")
		}

		store, err := session.Open(cfg.SessionsDB)
		if err != nil {
			return err
		}
		defer store.Close()

		dl := buildDownloader(cfg, log)
		b := bot.New(cfg, dl, store, log)

		ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
		defer stop()
		return b.Run(ctx)
	},
}

func init() {
	f := serveCmd.Flags()
	f.Int(config.KeyMaxConcurrent, 0, "max concurrent downloads across all users (default 2)")
	f.Int(config.KeyRateLimitMax, 0, "downloads per window per user; 0 disables (default 5)")
	f.Duration(config.KeyRateLimitWindow, 0, "rate-limit window, e.g. 1h or 30m (default 1h)")
}
