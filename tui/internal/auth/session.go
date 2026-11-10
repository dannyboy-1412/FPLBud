// Package auth signs the TUI in through Supabase and keeps the session off disk when it can.
package auth

import (
	"errors"
	"strings"
	"time"
)

const refreshWindow = 60 * time.Second

var (
	ErrSignedOut    = errors.New("not signed in")
	ErrInvalidGrant = errors.New("session expired")
)

// Session is one Supabase login. The refresh token is rotated on every refresh.
type Session struct {
	AccessToken  string    `json:"access_token"`
	RefreshToken string    `json:"refresh_token"`
	ExpiresAt    time.Time `json:"expires_at"`
	UserID       string    `json:"user_id"`
	Email        string    `json:"email"`
}

func (s Session) SignedIn() bool {
	return s.AccessToken != "" && s.RefreshToken != ""
}

// NeedsRefresh reports whether the access token expires inside the refresh window.
func NeedsRefresh(s Session, now time.Time) bool {
	if !s.SignedIn() || s.ExpiresAt.IsZero() {
		return true
	}
	return !now.Add(refreshWindow).Before(s.ExpiresAt)
}

func ProjectRef(supabaseURL string) string {
	host := strings.TrimPrefix(supabaseURL, "https://")
	host = strings.TrimPrefix(host, "http://")
	host = strings.Split(host, "/")[0]
	ref := strings.Split(host, ".")[0]
	if ref == "" || ref == "localhost" || ref == "127" {
		return "local"
	}
	return ref
}
