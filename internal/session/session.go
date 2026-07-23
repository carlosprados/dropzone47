// Package session persists pending per-user download sessions in SQLite.
package session

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	_ "modernc.org/sqlite" // pure-Go SQLite driver (no cgo)
)

// Data is the pending session for a user: the URL they sent and its metadata.
type Data struct {
	URL   string `json:"url"`
	Title string `json:"title"`
	ID    string `json:"id"`
}

// Store is a SQLite-backed session store.
type Store struct {
	db *sql.DB
}

// Open opens (creating if needed) the store at "<base>.sqlite3".
func Open(base string) (*Store, error) {
	path := base + ".sqlite3"
	if parent := filepath.Dir(path); parent != "" {
		if err := os.MkdirAll(parent, 0o755); err != nil {
			return nil, err
		}
	}
	db, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, err
	}
	if _, err := db.Exec(
		"CREATE TABLE IF NOT EXISTS sessions (user_id INTEGER PRIMARY KEY, data TEXT NOT NULL)",
	); err != nil {
		_ = db.Close()
		return nil, err
	}
	return &Store{db: db}, nil
}

// Close releases the underlying database.
func (s *Store) Close() error { return s.db.Close() }

// Save upserts the session for userID.
func (s *Store) Save(userID int64, d Data) error {
	blob, err := json.Marshal(d)
	if err != nil {
		return err
	}
	_, err = s.db.Exec(
		"INSERT INTO sessions (user_id, data) VALUES (?, ?) "+
			"ON CONFLICT(user_id) DO UPDATE SET data = excluded.data",
		userID, string(blob),
	)
	return err
}

// Load returns the session for userID, or (nil, nil) if none exists.
func (s *Store) Load(userID int64) (*Data, error) {
	var blob string
	err := s.db.QueryRow("SELECT data FROM sessions WHERE user_id = ?", userID).Scan(&blob)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var d Data
	if err := json.Unmarshal([]byte(blob), &d); err != nil {
		return nil, fmt.Errorf("decode session %d: %w", userID, err)
	}
	return &d, nil
}

// Delete removes the session for userID (no error if absent).
func (s *Store) Delete(userID int64) error {
	_, err := s.db.Exec("DELETE FROM sessions WHERE user_id = ?", userID)
	return err
}
