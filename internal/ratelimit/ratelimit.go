// Package ratelimit implements a per-key sliding-window rate limiter.
package ratelimit

import (
	"sync"
	"time"
)

// Limiter allows at most max events per window per key. A non-positive max
// disables the limit (every call is allowed). It is safe for concurrent use.
type Limiter struct {
	max    int
	window time.Duration

	mu     sync.Mutex
	events map[int64][]time.Time
	now    func() time.Time // injectable clock for tests
}

// New builds a Limiter for max events per window.
func New(max int, window time.Duration) *Limiter {
	return &Limiter{
		max:    max,
		window: window,
		events: make(map[int64][]time.Time),
		now:    time.Now,
	}
}

func (l *Limiter) prune(key int64, now time.Time) []time.Time {
	events := l.events[key]
	cutoff := now.Add(-l.window)
	i := 0
	for i < len(events) && events[i].Before(cutoff) {
		i++
	}
	if i > 0 {
		events = events[i:]
	}
	l.events[key] = events
	return events
}

// Allow records and permits an event if the key is under quota.
func (l *Limiter) Allow(key int64) bool {
	if l.max <= 0 {
		return true
	}
	l.mu.Lock()
	defer l.mu.Unlock()
	now := l.now()
	events := l.prune(key, now)
	if len(events) >= l.max {
		return false
	}
	l.events[key] = append(events, now)
	return true
}

// RetryAfter reports how long until a slot frees up (0 if one is available now).
func (l *Limiter) RetryAfter(key int64) time.Duration {
	if l.max <= 0 {
		return 0
	}
	l.mu.Lock()
	defer l.mu.Unlock()
	now := l.now()
	events := l.prune(key, now)
	if len(events) < l.max {
		return 0
	}
	d := l.window - now.Sub(events[0])
	if d < 0 {
		return 0
	}
	return d
}
