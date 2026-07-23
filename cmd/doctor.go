package cmd

import (
	"errors"
	"fmt"

	"github.com/spf13/cobra"

	"github.com/carlosprados/dropzone47/internal/config"
	"github.com/carlosprados/dropzone47/internal/deps"
)

var doctorCmd = &cobra.Command{
	Use:   "doctor",
	Short: "Check the environment (OS, ffmpeg, yt-dlp) and show install help",
	Long: `Detect the operating system and verify the external tools dropzone47 needs
(ffmpeg and yt-dlp). If any are missing, print copy-paste install commands for
Debian / Ubuntu / Raspbian. Exits non-zero when something required is missing.`,
	RunE: func(cmd *cobra.Command, _ []string) error {
		rep := deps.Check()
		fmt.Printf("System:  %s\n", rep.Label())
		fmt.Printf("ffmpeg:  %s\n", toolStatus(rep.FFmpeg))
		fmt.Printf("yt-dlp:  %s\n", toolStatus(rep.Ytdlp))
		if instr := rep.Instructions(); instr != "" {
			fmt.Print("\n" + instr)
			return errors.New("one or more required tools are missing")
		}
		fmt.Println("\nAll good — ffmpeg and yt-dlp are available.")
		return nil
	},
}

func toolStatus(t deps.Tool) string {
	if t.Found {
		return "found (" + t.Path + ")"
	}
	return "MISSING"
}

// preflight verifies the tools required for the configured backend and returns a
// formatted, actionable error when any are missing. Used by serve and get.
func preflight(cfg config.Config) error {
	rep := deps.Check()
	missing := rep.RequiredMissing(cfg.Downloader)
	if len(missing) == 0 {
		return nil
	}
	return fmt.Errorf("missing required tool(s): %v\n\n%s", missing, rep.Instructions())
}
