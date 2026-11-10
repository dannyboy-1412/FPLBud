package auth

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

var Ports = []int{53682, 53683, 53684}

// Login is an in-flight loopback sign-in.
type Login struct {
	URL      string
	Verifier string
	Code     <-chan string
	Err      <-chan error
	cancel   context.CancelFunc
}

func (l *Login) Cancel() {
	if l != nil && l.cancel != nil {
		l.cancel()
	}
}

// Begin listens on a loopback port and builds the Supabase authorize URL.
func Begin(parent context.Context, supabaseURL string) (*Login, error) {
	supabaseURL = strings.TrimRight(supabaseURL, "/")
	if supabaseURL == "" {
		return nil, errors.New("set FPLBUD_SUPABASE_URL to sign in")
	}
	verifier, err := NewVerifier()
	if err != nil {
		return nil, err
	}
	ctx, cancel := context.WithTimeout(parent, 3*time.Minute)
	ln, port, err := listen(Ports)
	if err != nil {
		cancel()
		return nil, err
	}
	redirect := fmt.Sprintf("http://127.0.0.1:%d/callback", port)
	authURL := fmt.Sprintf("%s/auth/v1/authorize?%s", supabaseURL, url.Values{
		"provider":              {"google"},
		"redirect_to":           {redirect},
		"code_challenge":        {verifier.Challenge},
		"code_challenge_method": {"s256"},
	}.Encode())

	codeCh := make(chan string, 1)
	errCh := make(chan error, 1)
	mux := http.NewServeMux()
	srv := &http.Server{Handler: mux, ReadHeaderTimeout: 10 * time.Second}
	var once sync.Once
	finish := func(code string, err error) {
		once.Do(func() {
			cancel()
			if code != "" {
				codeCh <- code
			}
			if err != nil {
				errCh <- err
			}
			go func() { _ = srv.Shutdown(context.Background()) }()
		})
	}
	mux.HandleFunc("/callback", func(w http.ResponseWriter, r *http.Request) {
		if msg := r.URL.Query().Get("error_description"); msg != "" {
			http.Error(w, msg, http.StatusBadRequest)
			finish("", errors.New(msg))
			return
		}
		code := r.URL.Query().Get("code")
		if code == "" {
			http.Error(w, "missing code", http.StatusBadRequest)
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_, _ = io.WriteString(w, "<!doctype html><meta charset=utf-8><title>FPLBud</title><p>Signed in. You can close this tab.</p>")
		finish(code, nil)
	})
	go func() {
		err := srv.Serve(ln)
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			finish("", err)
		}
	}()
	go func() {
		<-ctx.Done()
		finish("", ctx.Err())
	}()
	return &Login{URL: authURL, Verifier: verifier.Value, Code: codeCh, Err: errCh, cancel: cancel}, nil
}

func listen(ports []int) (net.Listener, int, error) {
	var last error
	for _, port := range ports {
		ln, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
		if err == nil {
			return ln, port, nil
		}
		last = err
	}
	if last == nil {
		last = errors.New("no loopback port")
	}
	return nil, 0, fmt.Errorf("could not listen for the login redirect: %w", last)
}

type tokenResponse struct {
	AccessToken      string `json:"access_token"`
	RefreshToken     string `json:"refresh_token"`
	ExpiresIn        int    `json:"expires_in"`
	ExpiresAt        int64  `json:"expires_at"`
	Error            string `json:"error"`
	ErrorDescription string `json:"error_description"`
	User             struct {
		ID    string `json:"id"`
		Email string `json:"email"`
	} `json:"user"`
}

// Exchange trades an authorization code for a session.
func Exchange(ctx context.Context, supabaseURL, anonKey, code, verifier string) (Session, error) {
	body, _ := json.Marshal(map[string]string{"auth_code": code, "code_verifier": verifier})
	return postToken(ctx, supabaseURL, anonKey, "pkce", body)
}

// Refresh rotates the refresh token. The caller must store the result before using it.
func Refresh(ctx context.Context, supabaseURL, anonKey, refreshToken string) (Session, error) {
	body, _ := json.Marshal(map[string]string{"refresh_token": refreshToken})
	return postToken(ctx, supabaseURL, anonKey, "refresh_token", body)
}

func postToken(ctx context.Context, supabaseURL, anonKey, grant string, body []byte) (Session, error) {
	endpoint := strings.TrimRight(supabaseURL, "/") + "/auth/v1/token?grant_type=" + grant
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return Session{}, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("apikey", anonKey)
	if anonKey != "" {
		req.Header.Set("Authorization", "Bearer "+anonKey)
	}
	client := &http.Client{Timeout: 15 * time.Second}
	res, err := client.Do(req)
	if err != nil {
		return Session{}, err
	}
	defer res.Body.Close()
	raw, _ := io.ReadAll(io.LimitReader(res.Body, 1<<20))
	var tok tokenResponse
	if err := json.Unmarshal(raw, &tok); err != nil {
		return Session{}, fmt.Errorf("sign-in response was not understood")
	}
	if tok.Error != "" {
		if tok.Error == "invalid_grant" {
			return Session{}, ErrInvalidGrant
		}
		if tok.ErrorDescription != "" {
			return Session{}, errors.New(tok.ErrorDescription)
		}
		return Session{}, errors.New(tok.Error)
	}
	if res.StatusCode >= 300 || tok.AccessToken == "" || tok.RefreshToken == "" {
		return Session{}, errors.New("sign-in did not return a session")
	}
	return sessionFromToken(tok, time.Now()), nil
}

func sessionFromToken(tok tokenResponse, now time.Time) Session {
	expires := now.Add(time.Hour)
	if tok.ExpiresAt > 0 {
		expires = time.Unix(tok.ExpiresAt, 0)
	} else if tok.ExpiresIn > 0 {
		expires = now.Add(time.Duration(tok.ExpiresIn) * time.Second)
	}
	return Session{
		AccessToken:  tok.AccessToken,
		RefreshToken: tok.RefreshToken,
		ExpiresAt:    expires,
		UserID:       tok.User.ID,
		Email:        tok.User.Email,
	}
}

// End tells Supabase to drop the access token, then the caller deletes the local copy.
func End(ctx context.Context, supabaseURL, anonKey, access string) error {
	if access == "" {
		return nil
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, strings.TrimRight(supabaseURL, "/")+"/auth/v1/logout", nil)
	if err != nil {
		return err
	}
	req.Header.Set("apikey", anonKey)
	req.Header.Set("Authorization", "Bearer "+access)
	client := &http.Client{Timeout: 10 * time.Second}
	res, err := client.Do(req)
	if err != nil {
		return err
	}
	defer res.Body.Close()
	return nil
}
