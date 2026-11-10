package api

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"
)

func TestGetRetriesUnauthorizedOnce(t *testing.T) {
	var calls atomic.Int32
	var refreshed atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n := calls.Add(1)
		if r.Header.Get("X-FPLBud-Client") == "" {
			t.Errorf("missing client header")
		}
		if n == 1 {
			w.WriteHeader(http.StatusUnauthorized)
			_, _ = io.WriteString(w, `{"detail":"nope"}`)
			return
		}
		_, _ = io.WriteString(w, `{"turns_left":3,"daily_cap":20,"resets_at":"00:00 UTC"}`)
	}))
	defer srv.Close()
	client := &Client{
		BaseURL: srv.URL,
		Version: "test",
		Token:   func(context.Context) (string, error) { return "old", nil },
		ForceRefresh: func(context.Context) (string, error) {
			refreshed.Add(1)
			return "new", nil
		},
	}
	usage, err := client.ChatUsage(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if usage.TurnsLeft != 3 || refreshed.Load() != 1 || calls.Load() != 2 {
		t.Fatalf("usage %#v calls %d refresh %d", usage, calls.Load(), refreshed.Load())
	}
}

func TestGetRetriesGateway(t *testing.T) {
	var calls atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if calls.Add(1) == 1 {
			w.WriteHeader(http.StatusBadGateway)
			return
		}
		_, _ = io.WriteString(w, `{"enabled":true}`)
	}))
	defer srv.Close()
	client := &Client{BaseURL: srv.URL, Token: func(context.Context) (string, error) { return "t", nil }}
	health, err := client.Health(context.Background())
	if err != nil || !health.Enabled {
		t.Fatal(err, health)
	}
}

func TestStreamIdle(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		_, _ = io.WriteString(w, ": ping\n\n")
		if f, ok := w.(http.Flusher); ok {
			f.Flush()
		}
		time.Sleep(300 * time.Millisecond)
	}))
	defer srv.Close()
	client := &Client{BaseURL: srv.URL, Token: func(context.Context) (string, error) { return "t", nil }}
	ch, err := client.OpenStream(context.Background(), "thread", "hi", "msg", 80*time.Millisecond)
	if err != nil {
		t.Fatal(err)
	}
	var last StreamMsg
	for msg := range ch {
		last = msg
	}
	if !last.Done || last.Err != ErrIdle {
		t.Fatalf("%#v", last)
	}
}
