package config

import (
	"reflect"
	"testing"

	"github.com/spf13/viper"
)

func TestParseIntList(t *testing.T) {
	if got := ParseIntList("720,480, 360 ,240"); !reflect.DeepEqual(got, []int{720, 480, 360, 240}) {
		t.Fatalf("got %v", got)
	}
	if got := ParseIntList("720,,x,480"); !reflect.DeepEqual(got, []int{720, 480}) {
		t.Fatalf("skips invalid: %v", got)
	}
	if got := ParseIntList(""); got != nil {
		t.Fatalf("empty: %v", got)
	}
}

func TestLoadDefaultsAndClamps(t *testing.T) {
	v := viper.New()
	SetDefaults(v)
	cfg := Load(v)
	if cfg.Downloader != "auto" || cfg.MaxHeight != 720 || cfg.TelegramMaxMB != 1900 {
		t.Fatalf("unexpected defaults: %+v", cfg)
	}
	if !reflect.DeepEqual(cfg.VideoHeightLadder, []int{720, 480, 360, 240}) {
		t.Fatalf("ladder default: %v", cfg.VideoHeightLadder)
	}
	// max-concurrent is clamped to >= 1.
	v.Set(KeyMaxConcurrent, 0)
	if Load(v).MaxConcurrentDownloads != 1 {
		t.Fatal("max-concurrent should clamp to 1")
	}
}
