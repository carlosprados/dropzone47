package cmd

import (
	"fmt"
	"strings"

	"github.com/spf13/cobra"

	"github.com/carlosprados/dropzone47/internal/config"
)

var configCmd = &cobra.Command{
	Use:   "config",
	Short: "Inspect configuration",
	Long:  "Commands to inspect the resolved configuration (defaults < file < env < flags).",
}

var configShowCmd = &cobra.Command{
	Use:   "show",
	Short: "Print the resolved configuration",
	Long:  "Print the effective configuration after merging defaults, config file, environment and flags. The Telegram token is masked.",
	Example: `  dropzone47 config show
  DROPZONE47_LANG=es dropzone47 config show`,
	RunE: func(cmd *cobra.Command, _ []string) error {
		cfg := config.Load(v)
		fmt.Printf("downloader:               %s\n", cfg.Downloader)
		fmt.Printf("lang:                     %s\n", cfg.Lang)
		fmt.Printf("log-level:                %s\n", cfg.LogLevel)
		fmt.Printf("download-dir:             %s\n", cfg.DownloadDir)
		fmt.Printf("sessions-db:              %s\n", cfg.SessionsDB)
		fmt.Printf("telegram-token:           %s\n", maskToken(cfg.TelegramToken))
		fmt.Printf("telegram-max-mb:          %d\n", cfg.TelegramMaxMB)
		fmt.Printf("max-height:               %d\n", cfg.MaxHeight)
		fmt.Printf("video-height-ladder:      %v\n", cfg.VideoHeightLadder)
		fmt.Printf("audio-kbitrate:           %d\n", cfg.AudioKbitrate)
		fmt.Printf("socket-timeout:           %d\n", cfg.SocketTimeout)
		fmt.Printf("ytdlp-retries:            %d\n", cfg.YtdlpRetries)
		fmt.Printf("cleanup-after-send:       %t\n", cfg.CleanupAfterSend)
		fmt.Printf("max-concurrent:           %d\n", cfg.MaxConcurrentDownloads)
		fmt.Printf("rate-limit-max:           %d\n", cfg.RateLimitMax)
		fmt.Printf("rate-limit-window:        %s\n", cfg.RateLimitWindow)
		return nil
	},
}

func init() {
	configCmd.AddCommand(configShowCmd)
}

func maskToken(t string) string {
	if t == "" {
		return "(unset)"
	}
	if i := strings.IndexByte(t, ':'); i > 0 && i+4 < len(t) {
		return t[:i+1] + "****"
	}
	return "****"
}
