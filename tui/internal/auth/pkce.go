package auth

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"errors"
	"net/url"
	"strings"
)

// Verifier is a PKCE code verifier and its S256 challenge.
type Verifier struct {
	Value     string
	Challenge string
}

func NewVerifier() (Verifier, error) {
	var buf [32]byte
	if _, err := rand.Read(buf[:]); err != nil {
		return Verifier{}, err
	}
	value := base64.RawURLEncoding.EncodeToString(buf[:])
	return Verifier{Value: value, Challenge: Challenge(value)}, nil
}

func Challenge(verifier string) string {
	sum := sha256.Sum256([]byte(verifier))
	return base64.RawURLEncoding.EncodeToString(sum[:])
}

// CodeFromRedirect pulls the authorization code out of a pasted callback URL.
func CodeFromRedirect(raw string) (string, error) {
	raw = strings.TrimSpace(raw)
	raw = strings.Trim(raw, `"'`)
	if raw == "" {
		return "", errors.New("paste the redirected URL")
	}
	parsed, err := url.Parse(raw)
	if err != nil {
		return "", err
	}
	if msg := parsed.Query().Get("error_description"); msg != "" {
		return "", errors.New(msg)
	}
	if code := parsed.Query().Get("code"); code != "" {
		return code, nil
	}
	if !strings.Contains(raw, "://") && !strings.ContainsAny(raw, " \t&?") {
		return raw, nil
	}
	return "", errors.New("that URL has no code")
}
