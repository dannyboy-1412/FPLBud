package ui

import (
	"context"
	"crypto/rand"
	"errors"
	"fmt"
	"strings"
	"time"

	tea "charm.land/bubbletea/v2"
	"github.com/pkg/browser"

	"github.com/dannyboy-1412/FPLBud/tui/internal/api"
	"github.com/dannyboy-1412/FPLBud/tui/internal/auth"
	"github.com/dannyboy-1412/FPLBud/tui/internal/version"
)

type authResult struct {
	session auth.Session
	err     error
}

type openedThread struct {
	detail api.ThreadDetail
	err    error
}

func versionNumber() string { return version.Number }

func newID() string {
	var b [16]byte
	_, _ = rand.Read(b[:])
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
}

func (m model) loadDesk() tea.Cmd {
	client := m.client
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 45*time.Second)
		defer cancel()
		var msg deskMsg
		msg.meta, msg.metaErr = client.Meta(ctx)
		msg.me, msg.meErr = client.Me(ctx)
		health, err := client.Health(ctx)
		if err != nil {
			msg.reachErr = err
			return msg
		}
		msg.enabled = health.Enabled
		if !msg.enabled {
			return msg
		}
		msg.usage, msg.usageErr = client.ChatUsage(ctx)
		msg.usageOK = msg.usageErr == nil
		msg.threads, _ = client.Threads(ctx)
		return msg
	}
}

func (m model) startLogin() tea.Cmd {
	supabaseURL := m.cfg.SupabaseURL
	return func() tea.Msg {
		login, err := auth.Begin(context.Background(), supabaseURL)
		if err != nil {
			return loginFailed{err}
		}
		return loginStarted{login}
	}
}

func waitLogin(login *auth.Login) tea.Cmd {
	return func() tea.Msg {
		select {
		case code := <-login.Code:
			return loginCode{code}
		case err := <-login.Err:
			if err == nil {
				err = errors.New("sign-in did not finish")
			}
			return loginFailed{err}
		}
	}
}

func openBrowser(url string) tea.Cmd {
	return func() tea.Msg {
		_ = browser.OpenURL(url)
		return nil
	}
}

func (m model) exchange(code string) tea.Cmd {
	cfg := m.cfg
	sessions := m.sessions
	verifier := ""
	if m.login != nil {
		verifier = m.login.Verifier
	}
	return func() tea.Msg {
		if verifier == "" {
			return authResult{err: errors.New("start the sign-in again, then paste the link")}
		}
		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
		defer cancel()
		sess, err := auth.Exchange(ctx, cfg.SupabaseURL, cfg.SupabaseAnonKey, code, verifier)
		if err != nil {
			return authResult{err: err}
		}
		if err := sessions.Save(sess); err != nil {
			return authResult{err: err}
		}
		return authResult{session: sess}
	}
}

func (m model) logout() (model, tea.Cmd) {
	cfg := m.cfg
	sessions := m.sessions
	access := m.session.AccessToken
	return m, func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = auth.End(ctx, cfg.SupabaseURL, cfg.SupabaseAnonKey, access)
		_ = sessions.Clear()
		return loggedOut{}
	}
}

func (m model) fetchThreads() tea.Cmd {
	client := m.client
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()
		threads, err := client.Threads(ctx)
		return threadsMsg{threads: threads, err: err}
	}
}

func (m model) openThread(id string) tea.Cmd {
	client := m.client
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()
		detail, err := client.Thread(ctx, id)
		return openedThread{detail: detail, err: err}
	}
}

func (m model) deleteSelected() (model, tea.Cmd) {
	if m.threadCursor < 0 || m.threadCursor >= len(m.threads) {
		return m, nil
	}
	id := m.threads[m.threadCursor].ID
	client := m.client
	if id == m.threadID {
		m.threadID = ""
		m.messages = nil
	}
	return m, func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()
		if err := client.DeleteThread(ctx, id); err != nil {
			return noted{err.Error()}
		}
		threads, err := client.Threads(ctx)
		return threadsMsg{threads: threads, err: err}
	}
}

func (m model) fetchUsage() tea.Cmd {
	client := m.client
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()
		usage, err := client.ChatUsage(ctx)
		if err != nil {
			return noted{err.Error()}
		}
		return noted{fmt.Sprintf("%d of %d turns left today. Resets at %s.", usage.TurnsLeft, usage.DailyCap, usage.ResetsAt)}
	}
}

func (m model) memoryCmd(args []string) (model, tea.Cmd) {
	client := m.client
	if len(args) > 0 && (args[0] == "forget" || args[0] == "clear") {
		key := ""
		if len(args) > 1 {
			key = args[1]
		}
		return m, func() tea.Msg {
			ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
			defer cancel()
			if err := client.ForgetMemory(ctx, key); err != nil {
				return noted{err.Error()}
			}
			return noted{"Forgotten."}
		}
	}
	return m, func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()
		items, err := client.Memory(ctx)
		if err != nil {
			return noted{err.Error()}
		}
		if len(items) == 0 {
			return noted{"No saved preferences."}
		}
		parts := make([]string, len(items))
		for i, item := range items {
			parts[i] = item.Key + ": " + item.Value
		}
		return noted{strings.Join(parts, "\n")}
	}
}

func (m model) answerProposal(accept bool) (model, tea.Cmd) {
	if m.proposal == nil {
		return m, nil
	}
	proposal := *m.proposal
	m.proposal = nil
	label := "Dismissed."
	if accept {
		label = "Saved."
	}
	m.messages = append(m.messages, note(label))
	client := m.client
	return m, func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()
		if err := client.ConfirmMemory(ctx, proposal.ID, accept); err != nil {
			return noted{err.Error()}
		}
		return noted{}
	}
}

func (m model) feedback(value int) (model, tea.Cmd) {
	idx := m.selected
	if idx < 0 || idx >= len(m.messages) {
		idx = m.lastAssistant()
	}
	if idx < 0 || m.messages[idx].messageID == 0 {
		return m, nil
	}
	id := m.messages[idx].messageID
	if value < 0 {
		m.reasonFor = id
		m.focus = focusComposer
		m.input.Placeholder = "What was wrong? Enter to skip"
		return m, m.input.Focus()
	}
	return m, m.sendFeedback(id, value, "")
}

func (m model) sendFeedback(id, value int, reason string) tea.Cmd {
	client := m.client
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()
		if err := client.Feedback(ctx, id, value, reason); err != nil {
			return noted{err.Error()}
		}
		return noted{"Noted."}
	}
}

func (m *model) toggleLast() {
	idx := m.lastAssistant()
	if idx < 0 {
		return
	}
	m.messages[idx].expanded = !m.messages[idx].expanded
}

func (m model) lastAssistant() int {
	for i := len(m.messages) - 1; i >= 0; i-- {
		if m.messages[i].kind == kindAssistant && !m.messages[i].pending {
			return i
		}
	}
	return -1
}

func (m model) assistantIndexes() []int {
	var out []int
	for i, msg := range m.messages {
		if msg.kind == kindAssistant && !msg.pending {
			out = append(out, i)
		}
	}
	return out
}

func previous(ids []int, current int) int {
	if len(ids) == 0 {
		return -1
	}
	best := ids[0]
	for _, id := range ids {
		if id < current {
			best = id
		}
	}
	if current < 0 {
		return ids[len(ids)-1]
	}
	return best
}

func nextIndex(ids []int, current int) int {
	if len(ids) == 0 {
		return -1
	}
	for _, id := range ids {
		if id > current {
			return id
		}
	}
	return ids[len(ids)-1]
}

func messagesFrom(rows []api.Message) []message {
	out := make([]message, 0, len(rows))
	for _, row := range rows {
		kind := kindAssistant
		if row.Role == "user" {
			kind = kindUser
		} else if row.Role != "assistant" {
			continue
		}
		out = append(out, message{
			kind:      kind,
			text:      row.Content,
			citations: row.Citations,
			messageID: row.ID,
		})
	}
	return out
}

func freshLogin(m model) model {
	next := newModel(m.cfg, m.plain, m.cfg.Theme)
	next.width = m.width
	next.height = m.height
	next.mode = screenLogin
	return next
}
