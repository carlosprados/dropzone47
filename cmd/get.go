package cmd

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"github.com/spf13/cobra"

	"github.com/carlosprados/dropzone47/internal/config"
	"github.com/carlosprados/dropzone47/internal/download"
	"github.com/carlosprados/dropzone47/internal/util"
)

var (
	getFormat string
	getOutput string
)

var getCmd = &cobra.Command{
	Use:   "get <url>",
	Short: "Download a URL to disk (no Telegram)",
	Long: `Download a single YouTube URL directly to disk using the configured backend.

Useful for testing the downloader and for scripted/CLI use without a bot. The file is
size-limited exactly like the bot (resolution ladder for video, lower bitrate for audio).`,
	Example: `  dropzone47 get "https://youtu.be/dQw4w9WgXcQ"
  dropzone47 get --format audio -o ./music "https://youtu.be/dQw4w9WgXcQ"
  dropzone47 get --downloader lux --max-height 480 "<url>"`,
	Args: cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		cfg := config.Load(v)
		log := newLogger(cfg.LogLevel)
		url := args[0]
		if !util.IsValidURL(url) {
			return fmt.Errorf("not a valid http(s) URL: %q", url)
		}
		format := download.Format(getFormat)
		if format != download.Audio && format != download.Video {
			return fmt.Errorf("invalid --format %q (want audio or video)", getFormat)
		}
		dest := cfg.DownloadDir
		if getOutput != "" {
			dest = getOutput
		}
		if err := util.EnsureDir(dest); err != nil {
			return err
		}
		if err := preflight(cfg); err != nil {
			return err
		}

		ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
		defer stop()

		dl := buildDownloader(cfg, log)
		info, err := dl.FetchInfo(ctx, url)
		if err != nil {
			return fmt.Errorf("fetch info: %w", err)
		}
		fmt.Fprintf(os.Stderr, "Title: %s\nDuration: %s\nBackend: %s\n",
			info.Title, util.HumanizeDuration(info.DurationSec), dl.Name())

		req := download.Request{
			URL:          url,
			ID:           info.ID,
			BaseName:     download.BuildBaseName(info.Title, info.ID),
			Format:       format,
			MaxHeight:    cfg.MaxHeight,
			AudioKbps:    cfg.AudioKbitrate,
			MaxMB:        cfg.TelegramMaxMB,
			HeightLadder: cfg.VideoHeightLadder,
			DestDir:      dest,
		}
		res, err := dl.Fetch(ctx, req, func(p download.Progress) {
			if p.Stage == download.StageDownloading && p.Percent >= 0 {
				fmt.Fprintf(os.Stderr, "\r%s: %d%%   ", p.Label, p.Percent)
			}
		})
		fmt.Fprintln(os.Stderr)
		if err != nil {
			return err
		}
		for _, f := range res.Files {
			fmt.Println(f)
		}
		return nil
	},
}

func init() {
	f := getCmd.Flags()
	f.StringVar(&getFormat, "format", "video", "media to download: audio | video")
	f.StringVarP(&getOutput, "output", "o", "", "output directory (default: download-dir)")
}
