package cmd

import (
	"fmt"
	"os/exec"

	"github.com/spf13/cobra"
)

// Version is set at build time via -ldflags "-X ...cmd.Version=...".
var Version = "dev"

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Print version and available download backends",
	Long:  "Print the binary version and which download backends are available (lux is built in; yt-dlp must be on PATH).",
	RunE: func(cmd *cobra.Command, _ []string) error {
		fmt.Printf("dropzone47 %s\n", Version)
		fmt.Println("backends:")
		fmt.Println("  lux:    built-in")
		if _, err := exec.LookPath("yt-dlp"); err == nil {
			fmt.Println("  yt-dlp: available (on PATH)")
		} else {
			fmt.Println("  yt-dlp: NOT found on PATH (fallback disabled)")
		}
		if _, err := exec.LookPath("ffmpeg"); err == nil {
			fmt.Println("  ffmpeg: available (on PATH)")
		} else {
			fmt.Println("  ffmpeg: NOT found on PATH (merging/audio extraction will fail)")
		}
		return nil
	},
}
