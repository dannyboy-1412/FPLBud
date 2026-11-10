package api

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"runtime"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	"github.com/dannyboy-1412/FPLBud/tui/internal/protocol"
)

var (
	ErrIdle    = errors.New("the server went quiet")
	ErrStopped = errors.New("stopped")
)

// Error is a FastAPI failure the UI can show as-is.
type Error struct {
	Status     int
	Code       string
	Message    string
	RetryAfter time.Duration
}

func (e *Error) Error() string {
	if e.Message != "" {
		return e.Message
	}
	return fmt.Sprintf("request failed (%d)", e.Status)
}

type Client struct {
	BaseURL      string
	Version      string
	Token        func(context.Context) (string, error)
	ForceRefresh func(context.Context) (string, error)
	SignOut      func()
	HTTP         *http.Client
}

type Gameweek struct {
	ID       int      `json:"id"`
	Name     string   `json:"name"`
	Deadline flexTime `json:"deadline_time"`
}

type Meta struct {
	Next       *Gameweek `json:"next_event"`
	Current    *Gameweek `json:"current_event"`
	LastIngest *struct {
		FinishedAt *flexTime `json:"finished_at"`
	} `json:"last_ingest"`
}

type Profile struct {
	DisplayName *string `json:"display_name"`
	TeamName    *string `json:"fpl_team_name"`
	EntryID     *int    `json:"fpl_entry_id"`
}

type Me struct {
	Profile Profile `json:"profile"`
}

type Usage struct {
	TurnsUsed int    `json:"turns_used"`
	TurnsLeft int    `json:"turns_left"`
	DailyCap  int    `json:"daily_cap"`
	ResetsAt  string `json:"resets_at"`
}

type Thread struct {
	ID           string  `json:"id"`
	Title        *string `json:"title"`
	MessageCount int     `json:"message_count"`
}

type Message struct {
	ID        int                 `json:"id"`
	Role      string              `json:"role"`
	Content   string              `json:"content"`
	Citations []protocol.Citation `json:"citations"`
	Feedback  *int                `json:"feedback"`
}

type ThreadDetail struct {
	Thread   Thread    `json:"thread"`
	Messages []Message `json:"messages"`
}

type Health struct {
	Enabled bool `json:"enabled"`
}

type MemoryItem struct {
	Key   string `json:"key"`
	Value string `json:"value"`
}

// StreamMsg is one decoded event, or the terminal result of the stream.
type StreamMsg struct {
	Event any
	Err   error
	Done  bool
}

func (c *Client) Meta(ctx context.Context) (Meta, error) {
	var out Meta
	err := c.do(ctx, http.MethodGet, "/meta", nil, &out, true)
	return out, err
}

func (c *Client) Me(ctx context.Context) (Me, error) {
	var out Me
	err := c.do(ctx, http.MethodGet, "/me", nil, &out, true)
	return out, err
}

func (c *Client) Health(ctx context.Context) (Health, error) {
	var out Health
	err := c.do(ctx, http.MethodGet, "/chat/health", nil, &out, true)
	return out, err
}

func (c *Client) ChatUsage(ctx context.Context) (Usage, error) {
	var out Usage
	err := c.do(ctx, http.MethodGet, "/chat/usage", nil, &out, true)
	return out, err
}

func (c *Client) Threads(ctx context.Context) ([]Thread, error) {
	var out struct {
		Threads []Thread `json:"threads"`
	}
	err := c.do(ctx, http.MethodGet, "/chat/threads", nil, &out, true)
	return out.Threads, err
}

func (c *Client) Thread(ctx context.Context, id string) (ThreadDetail, error) {
	var out ThreadDetail
	err := c.do(ctx, http.MethodGet, "/chat/threads/"+id, nil, &out, true)
	return out, err
}

func (c *Client) CreateThread(ctx context.Context) (Thread, error) {
	var out Thread
	err := c.do(ctx, http.MethodPost, "/chat/threads", map[string]any{}, &out, false)
	return out, err
}

func (c *Client) DeleteThread(ctx context.Context, id string) error {
	return c.do(ctx, http.MethodDelete, "/chat/threads/"+id, nil, nil, false)
}

func (c *Client) Feedback(ctx context.Context, messageID int, value int, reason string) error {
	body := map[string]any{"value": value}
	if reason != "" {
		body["reason"] = reason
	}
	return c.do(ctx, http.MethodPost, fmt.Sprintf("/chat/messages/%d/feedback", messageID), body, nil, false)
}

func (c *Client) Memory(ctx context.Context) ([]MemoryItem, error) {
	var out struct {
		Memory []MemoryItem `json:"memory"`
	}
	err := c.do(ctx, http.MethodGet, "/chat/memory", nil, &out, true)
	return out.Memory, err
}

func (c *Client) ForgetMemory(ctx context.Context, key string) error {
	path := "/chat/memory"
	if key != "" {
		path += "?key=" + key
	}
	return c.do(ctx, http.MethodDelete, path, nil, nil, false)
}

func (c *Client) ConfirmMemory(ctx context.Context, proposalID int, accept bool) error {
	return c.do(ctx, http.MethodPost, "/chat/memory/confirm", map[string]any{
		"proposal_id": proposalID,
		"accept":      accept,
	}, nil, false)
}

// OpenStream sends a message and returns a channel of events. The same client message id is reused if the send is retried.
func (c *Client) OpenStream(ctx context.Context, threadID, text, msgID string, idle time.Duration) (<-chan StreamMsg, error) {
	if idle <= 0 {
		idle = 45 * time.Second
	}
	body := map[string]string{"text": text, "client_msg_id": msgID}
	var res *http.Response
	var err error
	for try := 0; try < 2; try++ {
		res, err = c.open(ctx, "/chat/threads/"+threadID+"/messages", body)
		if err == nil {
			break
		}
		var apiErr *Error
		if errors.As(err, &apiErr) && apiErr.Status == http.StatusServiceUnavailable && apiErr.Code == "BUSY" && try == 0 {
			wait := apiErr.RetryAfter
			if wait <= 0 {
				wait = 2 * time.Second
			}
			if wait > 15*time.Second {
				wait = 15 * time.Second
			}
			select {
			case <-ctx.Done():
				return nil, ErrStopped
			case <-time.After(wait):
				continue
			}
		}
		return nil, err
	}
	ch := make(chan StreamMsg, 32)
	go c.readStream(ctx, res, idle, ch)
	return ch, nil
}

func (c *Client) do(ctx context.Context, method, path string, body any, dest any, retry bool) error {
	var payload []byte
	if body != nil {
		var err error
		payload, err = json.Marshal(body)
		if err != nil {
			return err
		}
	}
	refreshed := false
	var last error
	for attempt := 0; attempt < 3; attempt++ {
		if attempt > 0 {
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(time.Duration(attempt) * 400 * time.Millisecond):
			}
		}
		status, raw, header, err := c.round(ctx, method, path, payload, 10*time.Second)
		if err != nil {
			last = err
			if retry && ctx.Err() == nil {
				continue
			}
			return err
		}
		if status == http.StatusUnauthorized && !refreshed && c.ForceRefresh != nil {
			if _, ferr := c.ForceRefresh(ctx); ferr != nil {
				if c.SignOut != nil {
					c.SignOut()
				}
				return ferr
			}
			refreshed = true
			continue
		}
		if status >= 200 && status < 300 {
			if dest == nil || len(bytes.TrimSpace(raw)) == 0 {
				return nil
			}
			return json.Unmarshal(raw, dest)
		}
		apiErr := parseError(status, raw, header)
		if status == http.StatusUnauthorized {
			if c.SignOut != nil {
				c.SignOut()
			}
			return apiErr
		}
		if retry && (status == http.StatusBadGateway || status == http.StatusServiceUnavailable || status == http.StatusGatewayTimeout) {
			last = apiErr
			continue
		}
		return apiErr
	}
	if last == nil {
		last = errors.New("request failed")
	}
	return last
}

func (c *Client) open(ctx context.Context, path string, body any) (*http.Response, error) {
	payload, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	refreshed := false
	for {
		status, res, err := c.roundStream(ctx, path, payload)
		if err != nil {
			return nil, err
		}
		if status == http.StatusUnauthorized && !refreshed && c.ForceRefresh != nil {
			res.Body.Close()
			if _, ferr := c.ForceRefresh(ctx); ferr != nil {
				if c.SignOut != nil {
					c.SignOut()
				}
				return nil, ferr
			}
			refreshed = true
			continue
		}
		if status >= 200 && status < 300 {
			return res, nil
		}
		raw, _ := io.ReadAll(io.LimitReader(res.Body, 1<<20))
		header := res.Header.Clone()
		res.Body.Close()
		if status == http.StatusUnauthorized && c.SignOut != nil {
			c.SignOut()
		}
		return nil, parseError(status, raw, header)
	}
}

func (c *Client) round(ctx context.Context, method, path string, payload []byte, timeout time.Duration) (int, []byte, http.Header, error) {
	call, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	req, err := c.request(call, method, path, payload)
	if err != nil {
		return 0, nil, nil, err
	}
	res, err := c.http().Do(req)
	if err != nil {
		return 0, nil, nil, err
	}
	defer res.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(res.Body, 4<<20))
	if err != nil {
		return res.StatusCode, nil, res.Header.Clone(), err
	}
	return res.StatusCode, raw, res.Header.Clone(), nil
}

func (c *Client) roundStream(ctx context.Context, path string, payload []byte) (int, *http.Response, error) {
	req, err := c.request(ctx, http.MethodPost, path, payload)
	if err != nil {
		return 0, nil, err
	}
	req.Header.Set("Accept", "text/event-stream")
	res, err := c.http().Do(req)
	if err != nil {
		return 0, nil, err
	}
	return res.StatusCode, res, nil
}

func (c *Client) request(ctx context.Context, method, path string, payload []byte) (*http.Request, error) {
	token := ""
	if c.Token != nil {
		var err error
		token, err = c.Token(ctx)
		if err != nil {
			return nil, err
		}
	}
	var body io.Reader
	if payload != nil {
		body = bytes.NewReader(payload)
	}
	req, err := http.NewRequestWithContext(ctx, method, strings.TrimRight(c.BaseURL, "/")+path, body)
	if err != nil {
		return nil, err
	}
	version := c.Version
	if version == "" {
		version = "dev"
	}
	req.Header.Set("User-Agent", fmt.Sprintf("fplbud-tui/%s (%s/%s)", version, runtime.GOOS, runtime.GOARCH))
	req.Header.Set("X-FPLBud-Client", "tui/"+version)
	req.Header.Set("Accept", "application/json")
	if payload != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	return req, nil
}

func (c *Client) http() *http.Client {
	if c.HTTP != nil {
		return c.HTTP
	}
	return http.DefaultClient
}

func (c *Client) readStream(ctx context.Context, res *http.Response, idle time.Duration, ch chan<- StreamMsg) {
	defer close(ch)
	defer res.Body.Close()
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()
	body := &idleBody{rc: res.Body, idle: idle, cancel: cancel, ctx: ctx}
	body.last.Store(time.Now().UnixNano())
	go body.watch()
	err := Scan(body, MaxLine, func(raw protocol.Raw) error {
		ev, decErr := protocol.Decode(raw.Name, raw.Data)
		if decErr != nil {
			return decErr
		}
		if ev == nil {
			return nil
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case ch <- StreamMsg{Event: ev}:
			return nil
		}
	})
	if body.idleHit.Load() {
		err = ErrIdle
	} else if errors.Is(err, context.Canceled) || errors.Is(ctx.Err(), context.Canceled) {
		err = ErrStopped
	}
	select {
	case ch <- StreamMsg{Done: true, Err: err}:
	case <-ctx.Done():
		select {
		case ch <- StreamMsg{Done: true, Err: err}:
		default:
		}
	}
}

type idleBody struct {
	rc      io.ReadCloser
	idle    time.Duration
	cancel  context.CancelFunc
	ctx     context.Context
	last    atomic.Int64
	idleHit atomic.Bool
}

func (b *idleBody) Read(p []byte) (int, error) {
	if err := b.ctx.Err(); err != nil {
		return 0, err
	}
	n, err := b.rc.Read(p)
	if n > 0 {
		b.last.Store(time.Now().UnixNano())
	}
	return n, err
}

func (b *idleBody) watch() {
	tick := time.NewTicker(200 * time.Millisecond)
	defer tick.Stop()
	for {
		select {
		case <-b.ctx.Done():
			_ = b.rc.Close()
			return
		case <-tick.C:
			if time.Since(time.Unix(0, b.last.Load())) > b.idle {
				b.idleHit.Store(true)
				b.cancel()
				_ = b.rc.Close()
				return
			}
		}
	}
}

type flexTime struct {
	time.Time
}

func (t *flexTime) UnmarshalJSON(raw []byte) error {
	value := strings.Trim(string(raw), `"`)
	if value == "" || value == "null" {
		return nil
	}
	for _, layout := range []string{time.RFC3339Nano, time.RFC3339, "2006-01-02T15:04:05"} {
		parsed, err := time.Parse(layout, value)
		if err == nil {
			t.Time = parsed
			return nil
		}
	}
	return nil
}

func parseError(status int, raw []byte, header http.Header) *Error {
	out := &Error{Status: status, Message: strings.TrimSpace(string(raw))}
	if header != nil {
		if secs, err := strconv.Atoi(strings.TrimSpace(header.Get("Retry-After"))); err == nil && secs > 0 {
			out.RetryAfter = time.Duration(secs) * time.Second
		}
	}
	var wrap struct {
		Detail json.RawMessage `json:"detail"`
		Error  string          `json:"error"`
	}
	if err := json.Unmarshal(raw, &wrap); err != nil {
		return out
	}
	if wrap.Error != "" {
		out.Message = wrap.Error
	}
	if len(wrap.Detail) == 0 {
		return out
	}
	var text string
	if err := json.Unmarshal(wrap.Detail, &text); err == nil && text != "" {
		out.Message = text
		return out
	}
	var detail struct {
		Code    string `json:"code"`
		Message string `json:"message"`
	}
	if err := json.Unmarshal(wrap.Detail, &detail); err == nil {
		out.Code = detail.Code
		if detail.Message != "" {
			out.Message = detail.Message
		}
	}
	return out
}
