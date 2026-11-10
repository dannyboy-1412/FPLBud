package ui

import (
	"errors"
	"strings"
	"testing"

	"github.com/mattn/go-runewidth"

	"github.com/dannyboy-1412/FPLBud/tui/internal/api"
	"github.com/dannyboy-1412/FPLBud/tui/internal/config"
)

func visibleWidth(line string) int {
	var b strings.Builder
	for i := 0; i < len(line); i++ {
		if line[i] != 0x1b {
			b.WriteByte(line[i])
			continue
		}
		if i+1 < len(line) && line[i+1] == '[' {
			i += 2
			for i < len(line) && (line[i] < 0x40 || line[i] > 0x7e) {
				i++
			}
		}
	}
	return runewidth.StringWidth(b.String())
}

func TestEmptyChatShowsSuggestions(t *testing.T) {
	m := newModel(config.Config{SiteURL: "https://fplbud.vercel.app", APIURL: "http://localhost:8000"}, true, "dark")
	m.width = 80
	m.height = 24
	m.mode = screenChat
	entry := 1
	m.me.Profile.EntryID = &entry
	got := m.render()
	if !strings.Contains(got, "Who should I captain?") || !strings.Contains(got, "enter send") {
		t.Fatalf("%s", got)
	}
	for _, line := range strings.Split(got, "\n") {
		if width := visibleWidth(line); width > 80 {
			t.Fatalf("line is %d wide: %q", width, line)
		}
	}
}

func TestDarkChatFitsTheTerminal(t *testing.T) {
	m := newModel(config.Config{SiteURL: "https://fplbud.vercel.app", APIURL: "http://localhost:8000"}, false, "dark")
	m.width = 80
	m.height = 24
	m.mode = screenChat
	entry := 1
	name := "Danny FC"
	m.me.Profile.EntryID = &entry
	m.me.Profile.TeamName = &name
	m.messages = []message{
		{kind: kindUser, text: "Who should I captain?"},
		{kind: kindAssistant, text: "Captain Haaland. He is at home.", messageID: 3},
	}
	for _, line := range strings.Split(m.render(), "\n") {
		if width := visibleWidth(line); width > 80 {
			t.Fatalf("line is %d wide: %q", width, line)
		}
	}
}

func TestOpenStartsANewChat(t *testing.T) {
	m := newModel(config.Config{APIURL: "https://fplbud.onrender.com", SiteURL: "https://fplbud.vercel.app"}, true, "dark")
	m.width = 80
	m.height = 24
	m.threadID = "old"
	m.messages = []message{{kind: kindUser, text: "yesterday"}}
	next, _ := m.gotDesk(deskMsg{
		enabled: true,
		threads: []api.Thread{{ID: "old"}},
	})
	if next.threadID != "" || len(next.messages) != 0 {
		t.Fatalf("thread %q messages %d", next.threadID, len(next.messages))
	}
	if !strings.Contains(next.render(), "Who should I captain?") {
		t.Fatal(next.render())
	}
}

func TestUnreachableAPIIsNotChatDisabled(t *testing.T) {
	m := newModel(config.Config{APIURL: "https://fplbud.onrender.com", SiteURL: "https://fplbud.vercel.app"}, true, "dark")
	m.mode = screenChat
	next, _ := m.gotDesk(deskMsg{reachErr: errors.New("dial")})
	if next.chatOff || next.capped() || !next.composerOpen() {
		t.Fatal("composer closed")
	}
	if !strings.Contains(next.banner(), "Can't reach the assistant") {
		t.Fatal(next.banner())
	}
}

func TestServerTextCannotMoveTheCursor(t *testing.T) {
	m := newModel(config.Config{SiteURL: "https://fplbud.vercel.app"}, true, "dark")
	m.width = 80
	m.height = 24
	m.mode = screenChat
	entry := 1
	m.me.Profile.EntryID = &entry
	m.messages = []message{{kind: kindUser, text: "hello\x1b[2J\x1b]52;c;eA==\x07"}}
	got := m.render()
	if strings.Contains(got, "[2J") || strings.Contains(got, "52;") {
		t.Fatalf("%q", got)
	}
	if !strings.Contains(got, "hello") {
		t.Fatal(got)
	}
}
