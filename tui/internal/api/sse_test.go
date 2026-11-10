package api

import (
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/dannyboy-1412/FPLBud/tui/internal/chat"
	"github.com/dannyboy-1412/FPLBud/tui/internal/protocol"
)

func TestGoldenTranscriptEveryByte(t *testing.T) {
	raw := readGolden(t)
	for i := 0; i <= len(raw); i++ {
		events, err := ReadAll(&split{a: append([]byte(nil), raw[:i]...), b: append([]byte(nil), raw[i:]...)}, MaxLine)
		if err != nil {
			t.Fatal(err)
		}
		if len(events) != 5 || events[0].Name != "turn.start" || events[4].Name != "done" {
			t.Fatalf("split %d: %#v", i, names(events))
		}
	}
	events, err := ReadAll(&oneByte{bytes: raw}, MaxLine)
	if err != nil || len(events) != 5 {
		t.Fatalf("%v %d", err, len(events))
	}
}

func TestCRLFCommentsAndUnknown(t *testing.T) {
	normalized := strings.ReplaceAll(string(readGolden(t)), "\r\n", "\n")
	normalized = strings.ReplaceAll(normalized, "\r", "\n")
	body := strings.ReplaceAll(normalized, "\n", "\r\n")
	body = ": ping\r\n\r\n" + body + "event: future.thing\r\ndata: {\"ok\":true}\r\n\r\n"
	events, err := ReadAll(strings.NewReader(body), MaxLine)
	if err != nil {
		t.Fatal(err)
	}
	if len(events) != 6 || events[5].Name != "future.thing" {
		t.Fatalf("%#v", names(events))
	}
	state := chat.Turn{}
	for _, ev := range events {
		decoded, err := protocol.Decode(ev.Name, ev.Data)
		if err != nil {
			t.Fatal(err)
		}
		state = chat.Apply(state, decoded)
	}
	if !state.Done || state.TurnsLeft == nil || *state.TurnsLeft != 19 {
		t.Fatalf("%#v", state)
	}
	if !strings.Contains(state.Text(), "Haaland") {
		t.Fatal(state.Text())
	}
}

func TestOversizedLine(t *testing.T) {
	_, err := ReadAll(strings.NewReader("event: status\ndata: "+strings.Repeat("a", 40)+"\n\n"), 16)
	if !errors.Is(err, ErrLineTooLong) {
		t.Fatal(err)
	}
}

func readGolden(t *testing.T) []byte {
	t.Helper()
	dir, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	for {
		candidate := filepath.Join(dir, "contracts", "chat", "sse", "deadline.sse")
		raw, err := os.ReadFile(candidate)
		if err == nil {
			return raw
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			t.Fatal("contracts/chat/sse/deadline.sse not found")
		}
		dir = parent
	}
}

type oneByte struct {
	bytes []byte
	i     int
}

func (o *oneByte) Read(p []byte) (int, error) {
	if o.i >= len(o.bytes) {
		return 0, io.EOF
	}
	if len(p) == 0 {
		return 0, nil
	}
	p[0] = o.bytes[o.i]
	o.i++
	return 1, nil
}

type split struct {
	a    []byte
	b    []byte
	done bool
}

func (s *split) Read(p []byte) (int, error) {
	if !s.done {
		s.done = true
		if len(s.a) > 0 {
			n := copy(p, s.a)
			s.a = s.a[n:]
			return n, nil
		}
	}
	if len(s.a) > 0 {
		n := copy(p, s.a)
		s.a = s.a[n:]
		return n, nil
	}
	if len(s.b) == 0 {
		return 0, io.EOF
	}
	n := copy(p, s.b)
	s.b = s.b[n:]
	return n, nil
}

func names(events []protocol.Raw) []string {
	out := make([]string, len(events))
	for i, ev := range events {
		out[i] = ev.Name
	}
	return out
}
