package ui

import (
	"strings"
	"testing"

	tea "charm.land/bubbletea/v2"

	"github.com/dannyboy-1412/FPLBud/tui/internal/config"
)

func menuModel(plain bool) model {
	m := newModel(config.Config{APIURL: "https://fplbud.onrender.com", SiteURL: "https://fplbud.vercel.app"}, plain, "dark")
	m.width = 80
	m.height = 24
	m.mode = screenChat
	m.focus = focusComposer
	entry := 1
	m.me.Profile.EntryID = &entry
	return m
}

func TestSlashMenuListsCommands(t *testing.T) {
	for _, plain := range []bool{true, false} {
		m := menuModel(plain)
		m.input.SetValue("/")
		m.fitInput()
		got := m.render()
		for _, name := range []string{"/new", "/help", "/threads", "Start a new chat", "Shortcuts"} {
			if !strings.Contains(got, name) {
				t.Fatalf("plain=%v missing %s\n%s", plain, name, got)
			}
		}
		for _, line := range strings.Split(got, "\n") {
			if width := visibleWidth(line); width > 80 {
				t.Fatalf("plain=%v line is %d wide: %q", plain, width, line)
			}
		}
	}
}

func TestSlashFilterNarrowsTheMenu(t *testing.T) {
	m := menuModel(true)
	m.input.SetValue("/he")
	m.fitInput()
	got := m.render()
	if !strings.Contains(got, "/help") || strings.Contains(got, "/new") {
		t.Fatal(got)
	}
}

func TestSlashArgumentsHideTheMenu(t *testing.T) {
	m := menuModel(true)
	m.input.SetValue("/memory forget tone")
	m.fitInput()
	if m.slashOpen() {
		t.Fatal("menu stayed open")
	}
}

func TestSlashDownThenEnterRunsHelp(t *testing.T) {
	m := menuModel(true)
	m.input.SetValue("/")
	m.fitInput()
	var cmd tea.Cmd
	for range 2 {
		var next tea.Model
		next, cmd = m.onKey(tea.KeyPressMsg{Code: tea.KeyDown})
		m = next.(model)
		if cmd != nil {
			t.Fatal("down ran a command")
		}
	}
	if m.slashMatches()[m.commandCursor].Name != "help" {
		t.Fatalf("cursor %d %s", m.commandCursor, m.slashMatches()[m.commandCursor].Name)
	}
	next, _ := m.onKey(tea.KeyPressMsg{Code: tea.KeyEnter})
	m = next.(model)
	if m.mode != screenHelp {
		t.Fatalf("mode %d", m.mode)
	}
}

func TestSlashClickStartsANewChat(t *testing.T) {
	m := menuModel(true)
	m.messages = []message{{kind: kindUser, text: "yesterday"}}
	m.threadID = "old"
	m.input.SetValue("/")
	m.fitInput()
	y := m.paletteTop()
	idx, ok := m.commandIndexAt(y)
	if !ok || m.slashMatches()[idx].Name != "new" {
		t.Fatalf("click %d ok=%v", y, ok)
	}
	next, _ := m.Update(tea.MouseClickMsg{Y: y, Button: tea.MouseLeft})
	m = next.(model)
	if m.threadID != "" || len(m.messages) != 0 || m.input.Value() != "" {
		t.Fatalf("thread %q messages %d input %q", m.threadID, len(m.messages), m.input.Value())
	}
}

func TestEveryMenuCommandIsRecognised(t *testing.T) {
	for _, cmd := range commandList() {
		m := menuModel(true)
		next, _ := m.slash("/" + cmd.Name)
		if strings.Contains(next.notice, "Unknown") {
			t.Fatal(cmd.Name)
		}
	}
}
