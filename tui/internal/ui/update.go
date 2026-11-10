package ui

import (
	"context"
	"errors"
	"strings"
	"time"

	tea "charm.land/bubbletea/v2"

	"github.com/dannyboy-1412/FPLBud/tui/internal/api"
	"github.com/dannyboy-1412/FPLBud/tui/internal/auth"
	"github.com/dannyboy-1412/FPLBud/tui/internal/chat"
	"github.com/dannyboy-1412/FPLBud/tui/internal/protocol"
)

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.fitInput()
		return m, nil
	case tea.MouseClickMsg:
		if msg.Button == tea.MouseLeft {
			if idx, ok := m.commandIndexAt(msg.Y); ok {
				return m.runCommand(m.slashMatches()[idx].Name)
			}
		}
		return m.passPointer(msg)
	case tea.MouseMotionMsg:
		if idx, ok := m.commandIndexAt(msg.Y); ok {
			m.commandCursor = idx
			return m, nil
		}
		return m.passPointer(msg)
	case tea.MouseWheelMsg:
		if msg.Button == tea.MouseWheelUp {
			m.scroll += 3
		}
		if msg.Button == tea.MouseWheelDown {
			m.scroll -= 3
		}
		if m.scroll < 0 {
			m.scroll = 0
		}
		return m, nil
	case signedInMsg:
		m.session = msg.session
		m.fileSession = msg.file
		m.booting = true
		return m, tea.Batch(m.loadDesk(), m.wakeLater(), m.spinLater())
	case signedOutMsg:
		m.booting = false
		m.mode = screenLogin
		return m, nil
	case deskMsg:
		return m.gotDesk(msg)
	case streamOpened:
		m.threadID = msg.id
		m.stream = msg.ch
		return m, waitStream(msg.ch)
	case streamFailed:
		return m.failSend(msg)
	case api.StreamMsg:
		return m.gotStream(msg)
	case loginStarted:
		m.login = msg.login
		m.loginURL = msg.login.URL
		cmds := []tea.Cmd{waitLogin(msg.login)}
		if !m.pasting {
			cmds = append(cmds, openBrowser(msg.login.URL))
		}
		return m, tea.Batch(cmds...)
	case loginCode:
		return m, m.exchange(msg.code)
	case loginFailed:
		if msg.err != nil && !errors.Is(msg.err, context.Canceled) && !errors.Is(msg.err, context.DeadlineExceeded) {
			m.notice = msg.err.Error()
		}
		m.login = nil
		return m, nil
	case authResult:
		if msg.err != nil {
			m.notice = msg.err.Error()
			return m, nil
		}
		m.session = msg.session
		m.mode = screenBoot
		m.booting = true
		m.notice = ""
		m.pasting = false
		return m, tea.Batch(m.loadDesk(), m.wakeLater(), m.spinLater(), m.input.Focus())
	case loggedOut:
		m = freshLogin(m)
		return m, nil
	case noted:
		if msg.text == "" {
			return m, nil
		}
		m.messages = append(m.messages, note(msg.text))
		m.scroll = 0
		return m, nil
	case threadsMsg:
		if msg.err != nil {
			m.notice = msg.err.Error()
			return m, nil
		}
		m.threads = msg.threads
		if m.threadCursor >= len(m.threads) {
			m.threadCursor = len(m.threads) - 1
		}
		if m.threadCursor < 0 {
			m.threadCursor = 0
		}
		m.mode = screenThreads
		return m, nil
	case openedThread:
		if msg.err != nil {
			m.notice = msg.err.Error()
			m.mode = screenThreads
			return m, nil
		}
		m.threadID = msg.detail.Thread.ID
		m.messages = messagesFrom(msg.detail.Messages)
		m.mode = screenChat
		m.scroll = 0
		m.proposal = nil
		return m, m.input.Focus()
	case clockMsg:
		m.now = time.Now()
		return m, m.clock()
	case wakeMsg:
		if m.booting || m.streaming {
			m.waking = true
		}
		return m, nil
	case spinMsg:
		if m.booting || m.streaming {
			m.spin++
			return m, m.spinLater()
		}
		return m, nil
	case tea.KeyPressMsg:
		return m.onKey(msg)
	}
	if m.composerLive() {
		var cmd tea.Cmd
		m.input, cmd = m.input.Update(msg)
		m.fitInput()
		return m, cmd
	}
	return m, nil
}

func (m model) onKey(msg tea.KeyPressMsg) (tea.Model, tea.Cmd) {
	key := msg.String()
	if key == "ctrl+c" {
		if m.streaming {
			m.stopStream(true)
			return m, m.input.Focus()
		}
		return m, tea.Quit
	}
	switch m.mode {
	case screenLogin:
		return m.onLoginKey(msg)
	case screenHelp:
		if key == "esc" || key == "?" || key == "enter" {
			m.mode = screenChat
		}
		return m, nil
	case screenThreads:
		return m.onThreadKey(key)
	}
	if m.confirming {
		switch key {
		case "y":
			m.confirming = false
			return m.deleteSelected()
		case "n", "esc":
			m.confirming = false
		}
		return m, nil
	}
	if m.proposal != nil && m.input.Value() == "" && (key == "y" || key == "n") {
		return m.answerProposal(key == "y")
	}
	switch key {
	case "?":
		m.mode = screenHelp
		return m, nil
	case "ctrl+n":
		return m.startNewChat()
	case "ctrl+t":
		if m.streaming {
			m.stopStream(true)
		}
		return m, m.fetchThreads()
	case "ctrl+o":
		m.toggleLast()
		return m, nil
	case "tab":
		if m.slashOpen() {
			return m.onCommandKey("tab")
		}
		if m.focus == focusComposer {
			m.focus = focusTranscript
			m.selected = m.lastAssistant()
			m.input.Blur()
			return m, nil
		}
		m.focus = focusComposer
		return m, m.input.Focus()
	case "pgup", "ctrl+u":
		m.scroll += m.page()
		return m, nil
	case "pgdown", "ctrl+d":
		m.scroll -= m.page()
		if m.scroll < 0 {
			m.scroll = 0
		}
		return m, nil
	case "esc":
		if m.streaming {
			m.stopStream(true)
			return m, m.input.Focus()
		}
		if m.pasting {
			m.pasting = false
			m.input.Placeholder = askPlaceholder
			m.input.SetValue("")
			return m, nil
		}
		if m.focus == focusTranscript {
			m.focus = focusComposer
			return m, m.input.Focus()
		}
		if m.input.Value() != "" {
			m.input.SetValue("")
			m.fitInput()
		}
		return m, nil
	}
	if m.focus == focusTranscript {
		return m.onTranscriptKey(key)
	}
	if !m.composerLive() {
		return m, nil
	}
	if m.slashOpen() && (key == "up" || key == "down" || key == "enter" || key == "tab") {
		return m.onCommandKey(key)
	}
	if key == "enter" {
		return m.submit()
	}
	if key == "up" && m.input.Value() == "" && m.lastSent != "" {
		m.input.SetValue(m.lastSent)
		m.fitInput()
		return m, nil
	}
	if m.input.Value() == "" && len(m.messages) == 0 && key >= "1" && key <= "4" {
		idx := int(key[0] - '1')
		if idx < len(suggestions) {
			return m.send(suggestions[idx])
		}
	}
	var cmd tea.Cmd
	m.input, cmd = m.input.Update(msg)
	m.fitInput()
	return m, cmd
}

func (m model) onLoginKey(msg tea.KeyPressMsg) (tea.Model, tea.Cmd) {
	key := msg.String()
	if m.pasting {
		if key == "esc" {
			m.pasting = false
			m.input.Placeholder = askPlaceholder
			m.input.SetValue("")
			return m, nil
		}
		if key == "enter" {
			raw := m.input.Value()
			m.input.SetValue("")
			code, err := auth.CodeFromRedirect(raw)
			if err != nil {
				m.notice = err.Error()
				return m, nil
			}
			if m.login != nil {
				m.login.Cancel()
			}
			return m, m.exchange(code)
		}
		var cmd tea.Cmd
		m.input, cmd = m.input.Update(msg)
		m.fitInput()
		return m, cmd
	}
	switch key {
	case "enter":
		if m.cfg.SupabaseURL == "" || m.cfg.SupabaseAnonKey == "" {
			m.notice = "Set FPLBUD_SUPABASE_URL and FPLBUD_SUPABASE_ANON_KEY to sign in."
			return m, nil
		}
		m.notice = ""
		return m, m.startLogin()
	case "p":
		m.pasting = true
		m.input.Placeholder = pastePlaceholder
		m.input.SetValue("")
		if m.login == nil && m.cfg.SupabaseURL != "" {
			return m, tea.Batch(m.startLogin(), m.input.Focus())
		}
		return m, m.input.Focus()
	case "q":
		return m, tea.Quit
	}
	return m, nil
}

func (m model) onThreadKey(key string) (tea.Model, tea.Cmd) {
	switch key {
	case "esc", "ctrl+t":
		m.mode = screenChat
		m.confirming = false
		return m, m.input.Focus()
	case "up", "k":
		if m.threadCursor > 0 {
			m.threadCursor--
		}
		return m, nil
	case "down", "j":
		if m.threadCursor < len(m.threads)-1 {
			m.threadCursor++
		}
		return m, nil
	case "enter":
		if len(m.threads) == 0 {
			return m, nil
		}
		return m, m.openThread(m.threads[m.threadCursor].ID)
	case "d":
		if len(m.threads) == 0 {
			return m, nil
		}
		m.confirming = true
		return m, nil
	case "n", "ctrl+n":
		return m.startNewChat()
	}
	return m, nil
}

func (m model) onTranscriptKey(key string) (tea.Model, tea.Cmd) {
	ids := m.assistantIndexes()
	switch key {
	case "up", "k":
		m.selected = previous(ids, m.selected)
		return m, nil
	case "down", "j":
		m.selected = nextIndex(ids, m.selected)
		return m, nil
	case "enter":
		if m.selected >= 0 && m.selected < len(m.messages) {
			m.messages[m.selected].expanded = !m.messages[m.selected].expanded
		}
		return m, nil
	case "+", "=":
		return m.feedback(1)
	case "-", "_":
		return m.feedback(-1)
	}
	return m, nil
}

func (m model) passPointer(msg tea.Msg) (tea.Model, tea.Cmd) {
	if m.composerLive() {
		var cmd tea.Cmd
		m.input, cmd = m.input.Update(msg)
		m.fitInput()
		return m, cmd
	}
	return m, nil
}

func (m model) onCommandKey(key string) (model, tea.Cmd) {
	matches := m.slashMatches()
	switch key {
	case "up":
		if m.commandCursor > 0 {
			m.commandCursor--
		}
		return m, nil
	case "down":
		if m.commandCursor < len(matches)-1 {
			m.commandCursor++
		}
		return m, nil
	case "enter", "tab":
		if len(matches) == 0 {
			if key == "enter" {
				return m.submit()
			}
			return m, nil
		}
		return m.runCommand(matches[m.commandCursor].Name)
	default:
		return m, nil
	}
}

func (m model) submit() (model, tea.Cmd) {
	text := strings.TrimSpace(m.input.Value())
	m.input.SetValue("")
	m.fitInput()
	if m.reasonFor != 0 {
		id := m.reasonFor
		m.reasonFor = 0
		m.input.Placeholder = askPlaceholder
		return m, m.sendFeedback(id, -1, text)
	}
	if text == "" {
		return m, nil
	}
	if strings.HasPrefix(text, "/") {
		return m.slash(text)
	}
	return m.send(text)
}

func (m model) slash(text string) (model, tea.Cmd) {
	fields := strings.Fields(text)
	switch strings.ToLower(fields[0]) {
	case "/new":
		return m.startNewChat()
	case "/threads":
		return m, m.fetchThreads()
	case "/help":
		m.mode = screenHelp
		return m, nil
	case "/usage":
		return m, m.fetchUsage()
	case "/logout":
		return m.logout()
	case "/memory":
		return m.memoryCmd(fields[1:])
	case "/squad", "/plan", "/rerun":
		m.messages = append(m.messages, note("Squad, plans and reruns stay on "+m.cfg.SiteURL+"."))
		return m, nil
	default:
		m.notice = "Unknown command. Press ? for help."
		return m, nil
	}
}

func (m model) send(text string) (model, tea.Cmd) {
	if m.streaming || m.blocked || m.chatOff || m.capped() {
		return m, nil
	}
	m.messages = append(m.messages, message{kind: kindUser, text: text})
	m.messages = append(m.messages, message{kind: kindAssistant, pending: true})
	m.lastSent = text
	m.streaming = true
	m.waking = false
	m.live = chat.Turn{}
	m.scroll = 0
	m.proposal = nil
	ctx, cancel := context.WithCancel(context.Background())
	m.cancel = cancel
	threadID := m.threadID
	client := m.client
	return m, tea.Batch(func() tea.Msg {
		id := threadID
		if id == "" {
			thread, err := client.CreateThread(ctx)
			if err != nil {
				return streamFailed{err: err}
			}
			id = thread.ID
		}
		ch, err := client.OpenStream(ctx, id, text, newID(), 0)
		if err != nil {
			return streamFailed{err: err, id: id}
		}
		return streamOpened{id: id, ch: ch}
	}, m.spinLater(), m.wakeLater())
}

func (m model) gotStream(msg api.StreamMsg) (model, tea.Cmd) {
	if !m.streaming {
		return m, nil
	}
	if msg.Done {
		m.streaming = false
		m.waking = false
		m.cancel = nil
		if msg.Err != nil && !errors.Is(msg.Err, api.ErrStopped) {
			if errors.Is(msg.Err, auth.ErrSignedOut) {
				m.mode = screenLogin
				m.notice = "Sign in again to keep chatting."
				return m, nil
			}
			m.messages = append(m.messages, note(msg.Err.Error()))
		}
		m.commitLive(errors.Is(msg.Err, api.ErrStopped) || errors.Is(msg.Err, api.ErrIdle))
		return m, m.input.Focus()
	}
	if start, ok := msg.Event.(protocol.TurnStart); ok && !protocol.Compatible(start.ProtocolVersion) {
		m.blocked = true
		m.notice = "Update fplbud to keep chatting."
		m.stopStream(false)
		return m, nil
	}
	m.live = chat.Apply(m.live, msg.Event)
	if m.live.TurnsLeft != nil && m.usage != nil {
		m.usage.TurnsLeft = *m.live.TurnsLeft
	}
	m.syncLive()
	if m.scroll > 0 {
		// The reader is following unless they scrolled away.
	} else {
		m.scroll = 0
	}
	return m, waitStream(m.stream)
}

func (m model) failSend(msg streamFailed) (model, tea.Cmd) {
	m.streaming = false
	m.waking = false
	m.stopStream(false)
	m.dropOptimistic()
	m.input.SetValue(m.lastSent)
	m.fitInput()
	if msg.id != "" {
		m.threadID = msg.id
	}
	if errors.Is(msg.err, auth.ErrSignedOut) {
		m.mode = screenLogin
		m.notice = "Sign in again to keep chatting."
		return m, nil
	}
	text := "The message didn't send."
	if msg.err != nil && msg.err.Error() != "" {
		text = msg.err.Error()
	}
	m.notice = text
	return m, m.input.Focus()
}

func (m *model) syncLive() {
	if len(m.messages) == 0 {
		return
	}
	last := &m.messages[len(m.messages)-1]
	if last.kind != kindAssistant {
		return
	}
	last.pending = m.live.Pending()
	last.text = m.live.Text()
	last.citations = m.live.Citations
	last.tools = m.live.Tools
	last.dataAsOf = m.live.DataAsOf
	last.disclaimers = m.live.Disclaimers
	last.grounding = m.live.Grounding
	last.messageID = m.live.MessageID
	if m.live.Proposal != nil {
		m.proposal = m.live.Proposal
	}
	if m.live.Error != "" {
		last.text = m.live.Error
		last.pending = false
	}
}

func (m *model) commitLive(stopped bool) {
	m.syncLive()
	if len(m.messages) == 0 {
		return
	}
	last := &m.messages[len(m.messages)-1]
	if last.kind != kindAssistant {
		return
	}
	last.pending = false
	last.stopped = stopped
	if m.live.Error != "" {
		last.text = m.live.Error
	}
}

func (m *model) dropOptimistic() {
	n := len(m.messages)
	if n >= 1 && m.messages[n-1].kind == kindAssistant && m.messages[n-1].pending {
		m.messages = m.messages[:n-1]
		n--
	}
	if n >= 1 && m.messages[n-1].kind == kindUser && m.messages[n-1].text == m.lastSent {
		m.messages = m.messages[:n-1]
	}
}

func (m *model) stopStream(mark bool) {
	if m.cancel != nil {
		m.cancel()
		m.cancel = nil
	}
	m.stream = nil
	m.streaming = false
	m.waking = false
	if mark {
		m.commitLive(true)
	}
}

func (m model) gotDesk(msg deskMsg) (model, tea.Cmd) {
	m.booting = false
	m.waking = false
	if errors.Is(msg.meErr, auth.ErrSignedOut) {
		m.mode = screenLogin
		m.notice = "Sign in again to keep chatting."
		return m, nil
	}
	m.meta = msg.meta
	m.me = msg.me
	if msg.usageOK {
		usage := msg.usage
		m.usage = &usage
	}
	if msg.reachErr != nil {
		m.notice = "Can't reach the assistant at " + m.cfg.APIURL + "."
	} else {
		m.chatOff = !msg.enabled
	}
	m.threads = msg.threads
	m.mode = screenChat
	m.threadID = ""
	m.messages = nil
	m.proposal = nil
	m.scroll = 0
	if msg.meErr != nil && m.notice == "" {
		m.notice = msg.meErr.Error()
	}
	return m, m.input.Focus()
}

func (m model) composerLive() bool {
	if m.pasting || m.reasonFor != 0 {
		return true
	}
	return m.mode == screenChat && m.focus == focusComposer && !m.streaming && !m.chatOff && !m.capped() && !m.blocked
}

func (m model) capped() bool {
	return m.usage != nil && m.usage.TurnsLeft <= 0
}

func (m model) page() int {
	h := m.transcriptHeight()
	if h < 2 {
		return 1
	}
	return h - 1
}

func (m model) clock() tea.Cmd {
	return tea.Tick(30*time.Second, func(time.Time) tea.Msg { return clockMsg{} })
}

func (m model) spinLater() tea.Cmd {
	return tea.Tick(80*time.Millisecond, func(time.Time) tea.Msg { return spinMsg{} })
}

func (m model) wakeLater() tea.Cmd {
	return tea.Tick(5*time.Second, func(time.Time) tea.Msg { return wakeMsg{} })
}

func waitStream(ch <-chan api.StreamMsg) tea.Cmd {
	return func() tea.Msg {
		msg, ok := <-ch
		if !ok {
			return api.StreamMsg{Done: true}
		}
		return msg
	}
}

func note(text string) message {
	return message{kind: kindNote, text: text}
}
