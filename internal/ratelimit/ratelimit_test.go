package ratelimit

import (
	"testing"
	"time"
)

func TestAllowUpToQuota(t *testing.T) {
	rl := New(2, time.Hour)
	if !rl.Allow(1) {
		t.Fatal("first should be allowed")
	}
	if !rl.Allow(1) {
		t.Fatal("second should be allowed")
	}
	if rl.Allow(1) {
		t.Fatal("third should be blocked")
	}
	if !rl.Allow(2) {
		t.Fatal("a different key has its own budget")
	}
}

func TestZeroDisablesLimit(t *testing.T) {
	rl := New(0, time.Hour)
	for range 100 {
		if !rl.Allow(7) {
			t.Fatal("zero max should allow everything")
		}
	}
	if rl.RetryAfter(7) != 0 {
		t.Fatal("no wait when disabled")
	}
}

func TestWindowExpiry(t *testing.T) {
	rl := New(1, 10*time.Second)
	now := time.Unix(1000, 0)
	rl.now = func() time.Time { return now }

	if !rl.Allow(1) {
		t.Fatal("first allowed")
	}
	if rl.Allow(1) {
		t.Fatal("second blocked within window")
	}
	if rl.RetryAfter(1) <= 0 {
		t.Fatal("should report a wait")
	}
	now = now.Add(11 * time.Second)
	if !rl.Allow(1) {
		t.Fatal("allowed after window expiry")
	}
}
