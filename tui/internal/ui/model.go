// Package ui is the full-screen chat client.
package ui

import (
	"context"
	"time"

	"charm.land/bubbles/v2/textarea"
	tea "charm.land/bubbletea/v2"

	"github.com/dannyboy-1412/FPLBud/tui/internal/api"
	"github.com/dannyboy-1412/FPLBud/tui/internal/auth"
	"github.com/dannyboy-1412/FPLBud/tui/internal/chat"
	"github.com/dannyboy-1412/FPLBud/tui/internal/config"
	"github.com/dannyboy-1412/FPLBud/tui/internal/protocol"
	"github.com/dannyboy-1412/FPLBud/tui/internal/theme"
)

const (
	kindUser = iota
	kindAssistant
	kindNote
)

const (
	screenBoot = iota
	screenLogin
	screenChat
	screenHelp
	screenThreads
)

const (
	focusComposer = iota
	focusTranscript
)

var suggestions = []string{
	"Who should I captain?",
	"Is a hit worth it?",
	"Should I use a chip this week?",
	"Which of my players have the best fixtures?",
}

type message struct {
	kind        int
	text        string
	citations   []protocol.Citation
	tools       []protocol.ToolUse
	dataAsOf    string
	disclaimers []string
	grounding   string
	messageID   int
	stopped     bool
	pending     bool
	expanded    bool
}

type model struct {
	cfg      config.Config
	sessions *auth.Manager
	client   *api.Client
	theme    theme.Theme
	plain    bool

	width  int
	height int
	now    time.Time
	spin   int

	mode  int
	focus int
	input textarea.Model

	session     auth.Session
	meta        api.Meta
	me          api.Me
	usage       *api.Usage
	threads     []api.Thread
	threadID    string
	messages    []message
	live        chat.Turn
	streaming   bool
	cancel      context.CancelFunc
	stream      <-chan api.StreamMsg
	booting     bool
	waking      bool
	chatOff     bool
	blocked     bool
	notice      string
	fileSession bool
	scroll      int
	lastSent    string

	threadCursor  int
	confirming    bool
	commandCursor int
	commandQuery  string
	selected      int
	proposal      *chat.Proposal
	reasonFor     int

	login    *auth.Login
	loginURL string
	pasting  bool
}

func newModel(cfg config.Config, plain bool, themeName string) model {
	if themeName == "" {
		themeName = cfg.Theme
	}
	th := theme.New(themeName, plain)
	sessions := auth.NewManager(cfg.Dir, cfg.SupabaseURL, cfg.SupabaseAnonKey)
	client := &api.Client{
		BaseURL: cfg.APIURL,
		Version: versionNumber(),
		Token:   sessions.Token,
		ForceRefresh: func(ctx context.Context) (string, error) {
			return sessions.ForceRefresh(ctx)
		},
		SignOut: func() { _ = sessions.Clear() },
	}
	m := model{
		cfg:      cfg,
		sessions: sessions,
		client:   client,
		theme:    th,
		plain:    plain || th.Plain,
		now:      time.Now(),
		mode:     screenBoot,
		focus:    focusComposer,
		input:    newInput(th),
		selected: -1,
	}
	return m
}

func (m model) Init() tea.Cmd {
	return tea.Batch(m.input.Focus(), m.loadSession(), m.clock())
}

func (m model) loadSession() tea.Cmd {
	sessions := m.sessions
	return func() tea.Msg {
		sess, err := sessions.Load()
		if err != nil || !sess.SignedIn() {
			return signedOutMsg{file: sessions.File}
		}
		return signedInMsg{session: sess, file: sessions.File}
	}
}

type signedInMsg struct {
	session auth.Session
	file    bool
}

type signedOutMsg struct{ file bool }

type deskMsg struct {
	meta     api.Meta
	metaErr  error
	me       api.Me
	meErr    error
	enabled  bool
	reachErr error
	usage    api.Usage
	usageErr error
	usageOK  bool
	threads  []api.Thread
}

type streamOpened struct {
	id string
	ch <-chan api.StreamMsg
}

type streamFailed struct {
	err error
	id  string
}

type loginStarted struct{ login *auth.Login }
type loginCode struct{ code string }
type loginFailed struct{ err error }
type loggedOut struct{}
type clockMsg struct{}
type spinMsg struct{}
type wakeMsg struct{}
type noted struct{ text string }
type threadsMsg struct {
	threads []api.Thread
	err     error
}
