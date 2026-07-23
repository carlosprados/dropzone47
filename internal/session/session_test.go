package session

import (
	"path/filepath"
	"testing"
)

func TestRoundTripAndDelete(t *testing.T) {
	base := filepath.Join(t.TempDir(), "sessions")
	store, err := Open(base)
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()

	if d, err := store.Load(42); err != nil || d != nil {
		t.Fatalf("empty load: %v %v", d, err)
	}

	if err := store.Save(42, Data{URL: "u", Title: "T", ID: "vid"}); err != nil {
		t.Fatal(err)
	}
	got, err := store.Load(42)
	if err != nil || got == nil || got.ID != "vid" || got.Title != "T" {
		t.Fatalf("load: %+v %v", got, err)
	}

	// Upsert overwrites.
	if err := store.Save(42, Data{URL: "u2", Title: "T2", ID: "vid2"}); err != nil {
		t.Fatal(err)
	}
	if got, _ := store.Load(42); got == nil || got.ID != "vid2" {
		t.Fatalf("upsert: %+v", got)
	}

	if err := store.Delete(42); err != nil {
		t.Fatal(err)
	}
	if got, _ := store.Load(42); got != nil {
		t.Fatalf("after delete: %+v", got)
	}
}
