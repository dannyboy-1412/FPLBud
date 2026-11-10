package auth

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

type brokenStore struct{}

func (brokenStore) Load() (Session, error) { return Session{}, ErrSignedOut }
func (brokenStore) Save(Session) error     { return ErrSignedOut }
func (brokenStore) Clear() error           { return nil }

func TestRefreshPersistsBeforeUse(t *testing.T) {
	var hits int
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits++
		_ = json.NewEncoder(w).Encode(map[string]any{
			"access_token":  "new-access",
			"refresh_token": "new-refresh",
			"expires_in":    3600,
			"user":          map[string]string{"id": "user", "email": "a@b.c"},
		})
	}))
	defer srv.Close()

	dir := t.TempDir()
	mgr := NewManager(dir, srv.URL, "anon")
	mgr.keys = brokenStore{}
	mgr.now = func() time.Time { return time.Now() }
	if err := mgr.Save(Session{
		AccessToken:  "old",
		RefreshToken: "old-refresh",
		ExpiresAt:    time.Now().Add(10 * time.Second),
		UserID:       "user",
	}); err != nil {
		t.Fatal(err)
	}
	token, err := mgr.Token(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if token != "new-access" {
		t.Fatal(token)
	}
	stored, err := mgr.Load()
	if err != nil {
		t.Fatal(err)
	}
	if stored.RefreshToken != "new-refresh" {
		t.Fatal(stored.RefreshToken)
	}
	if _, err := mgr.Token(context.Background()); err != nil {
		t.Fatal(err)
	}
	if hits != 1 {
		t.Fatalf("refreshed %d times", hits)
	}
}

func TestNeedsRefreshWindow(t *testing.T) {
	now := time.Date(2026, 11, 10, 12, 0, 0, 0, time.UTC)
	soon := Session{AccessToken: "a", RefreshToken: "b", ExpiresAt: now.Add(30 * time.Second)}
	later := soon
	later.ExpiresAt = now.Add(2 * time.Minute)
	if !NeedsRefresh(soon, now) || NeedsRefresh(later, now) {
		t.Fatal("window")
	}
}
