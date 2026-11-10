package ui

import (
	"fmt"
	"strings"
	"time"

	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
	"github.com/mattn/go-runewidth"

	"github.com/dannyboy-1412/FPLBud/tui/internal/render"
)

func (m model) View() tea.View {
	view := tea.NewView(m.render())
	view.AltScreen = !m.plain
	view.WindowTitle = "FPLBud"
	view.MouseMode = tea.MouseModeCellMotion
	if !m.plain && !m.theme.Plain {
		view.BackgroundColor = m.theme.Paper
		view.ForegroundColor = m.theme.Fore
	}
	return view
}

func (m model) render() string {
	if m.width < 1 || m.height < 1 {
		return "FPLBud"
	}
	switch m.mode {
	case screenLogin:
		return m.pad(m.loginView())
	case screenHelp:
		return m.pad(m.helpView())
	case screenThreads:
		return m.frame(m.threadView())
	default:
		return m.frame(m.transcriptView())
	}
}

func (m model) frame(body string) string {
	parts := []string{m.header()}
	if extra := m.banner(); extra != "" {
		parts = append(parts, extra)
	}
	parts = append(parts, "", body)
	if menu := m.paletteView(); menu != "" {
		parts = append(parts, "", menu)
	} else {
		parts = append(parts, "")
	}
	parts = append(parts, m.composer(), m.footer())
	return m.pad(strings.Join(parts, "\n"))
}

func (m model) pad(s string) string {
	n := lipgloss.Height(s)
	if n >= m.height {
		return s
	}
	return s + strings.Repeat("\n", m.height-n)
}

func (m model) transcriptHeight() int {
	used := 1 + 2 + m.composerHeight() + 1 + m.paletteHeight()
	if m.banner() != "" {
		used++
	}
	h := m.height - used
	if h < 1 {
		return 1
	}
	return h
}

func (m model) composerHeight() int {
	if !m.composerOpen() {
		return 3
	}
	return lipgloss.Height(m.input.View()) + 2
}

func (m model) composerOpen() bool {
	return m.mode == screenChat && !m.streaming && !m.chatOff && !m.capped() && !m.blocked
}

func (m model) header() string {
	segs := []segment{{plain: "FPLBud", styled: m.theme.Paint(m.theme.Bold, "FPLBud")}}
	if name := teamName(m.me.Profile.TeamName, m.me.Profile.DisplayName); name != "" {
		segs = append(segs, segment{plain: name, styled: m.theme.Paint(m.theme.Soft, name)})
	}
	if line, urgent := m.deadlineLine(); line != "" {
		style := m.theme.Soft
		if urgent {
			style = m.theme.Accent
		}
		segs = append(segs, segment{plain: line, styled: m.theme.Paint(style, line)})
	}
	if m.usage != nil {
		label := fmt.Sprintf("%d left", m.usage.TurnsLeft)
		style := m.theme.Faint
		if m.usage.TurnsLeft <= 3 {
			style = m.theme.Warn
		}
		segs = append(segs, segment{plain: label, styled: m.theme.Paint(style, label)})
	}
	return fitSegments(m.width, segs)
}

func (m model) deadlineLine() (string, bool) {
	gw := m.meta.Next
	if gw == nil || gw.Deadline.IsZero() {
		return "", false
	}
	left := gw.Deadline.Sub(m.now)
	when := gw.Deadline.Local().Format("Mon 2 Jan 15:04")
	urgent := left > 0 && left < 2*time.Hour
	return fmt.Sprintf("GW %d · %s · %s", gw.ID, when, formatLeft(left)), urgent
}

func formatLeft(d time.Duration) string {
	if d <= 0 {
		return "deadline passed"
	}
	hours := int(d.Hours())
	mins := int(d.Minutes()) % 60
	if hours >= 48 {
		return fmt.Sprintf("%dd %dh", hours/24, hours%24)
	}
	if hours >= 1 {
		return fmt.Sprintf("%dh %dm", hours, mins)
	}
	return fmt.Sprintf("%dm", int(d.Minutes()))
}

func teamName(team, display *string) string {
	if team != nil && strings.TrimSpace(*team) != "" {
		return trimWidth(strings.TrimSpace(*team), 24)
	}
	if display != nil && strings.TrimSpace(*display) != "" {
		return trimWidth(strings.TrimSpace(*display), 24)
	}
	return ""
}

func (m model) banner() string {
	switch {
	case m.blocked:
		return m.theme.Paint(m.theme.Warn, "Update fplbud to keep chatting.")
	case m.chatOff:
		return m.theme.Paint(m.theme.Faint, "Chat isn't available yet.")
	case m.notice != "":
		return m.theme.Paint(m.theme.Warn, m.notice)
	case m.me.Profile.EntryID == nil && m.mode == screenChat && !m.booting:
		return m.theme.Paint(m.theme.Warn, "Add your team at "+m.cfg.SiteURL+"/onboarding")
	case m.fileSession:
		return m.theme.Paint(m.theme.Faint, "This session is stored in a file. The system keychain was unavailable.")
	default:
		return ""
	}
}

func (m model) transcriptView() string {
	height := m.transcriptHeight()
	if m.booting {
		label := "FPLBud"
		if m.waking {
			label = "Waking the server…"
		}
		return strings.Join(centerLines([]string{label}, height), "\n")
	}
	if len(m.messages) == 0 {
		return strings.Join(centerLines(m.emptyLines(), height), "\n")
	}
	return strings.Join(window(m.conversationLines(), height, m.scroll), "\n")
}

func (m model) emptyLines() []string {
	lines := []string{m.theme.Paint(m.theme.Faint, "Ask about your squad, or pick a question.")}
	lines = append(lines, "")
	for i, prompt := range suggestions {
		num := m.theme.Paint(m.theme.Accent, fmt.Sprintf("%d", i+1))
		lines = append(lines, "  "+num+"  "+m.theme.Paint(m.theme.Ink, prompt))
	}
	return lines
}

func (m model) conversationLines() []string {
	width := m.width
	if width > 100 {
		width = 100
	}
	var lines []string
	for i, msg := range m.messages {
		if i > 0 {
			lines = append(lines, "")
		}
		lines = append(lines, m.messageLines(msg, i == m.selected && m.focus == focusTranscript, width)...)
	}
	if m.proposal != nil {
		lines = append(lines, "", m.theme.Paint(m.theme.Warn, "Save preference: "+m.proposal.Label+"   y save · n dismiss"))
	}
	return lines
}

func (m model) messageLines(msg message, selected bool, width int) []string {
	switch msg.kind {
	case kindUser:
		return m.userLines(msg.text, width)
	case kindNote:
		return wrapPlain(m.theme.Paint(m.theme.Faint, msg.text), msg.text, width)
	default:
		return m.assistantLines(msg, selected, width)
	}
}

func (m model) userLines(text string, width int) []string {
	body := wrapWords(render.Sanitize(text), width-2)
	if len(body) == 0 {
		body = []string{""}
	}
	out := make([]string, len(body))
	for i, line := range body {
		prefix := "  "
		if i == 0 {
			prefix = m.theme.Paint(m.theme.Accent, "› ")
		}
		out[i] = prefix + m.theme.Paint(m.theme.Bold, line)
	}
	return out
}

func (m model) assistantLines(msg message, selected bool, width int) []string {
	if msg.pending && msg.text == "" {
		return nil
	}
	draft := msg.pending
	laid := render.LayOut(msg.text, msg.citations, draft, width-2)
	var lines []string
	for i, line := range laid {
		prefix := "  "
		if i == 0 && selected {
			prefix = m.theme.Paint(m.theme.Accent, "▸ ")
		}
		lines = append(lines, prefix+m.paintLine(line))
	}
	if msg.grounding == "repaired" || msg.grounding == "fallback" {
		lines = append(lines, "  "+m.theme.Paint(m.theme.Warn, "adjusted to match FPLBud's data"))
	}
	for _, line := range msg.disclaimers {
		lines = append(lines, "  "+m.theme.Paint(m.theme.Faint, render.Sanitize(line)))
	}
	if msg.stopped {
		lines = append(lines, "  "+m.theme.Paint(m.theme.Faint, "Stopped."))
	}
	if !msg.pending {
		lines = append(lines, m.toolLines(msg)...)
	}
	return lines
}

func (m model) paintLine(line render.Line) string {
	var b strings.Builder
	b.WriteString(line.Prefix)
	for _, span := range line.Spans {
		switch span.Kind {
		case render.KindBold:
			b.WriteString(m.theme.Paint(m.theme.Bold, span.Text))
		case render.KindChip:
			name := span.Chip.Name
			if strings.HasPrefix(span.Text, name) {
				b.WriteString(m.theme.Paint(m.theme.Accent, name))
				b.WriteString(m.theme.Paint(m.theme.Faint, strings.TrimPrefix(span.Text, name)))
			} else {
				b.WriteString(m.theme.Paint(m.theme.Faint, span.Text))
			}
		default:
			b.WriteString(m.theme.Paint(m.theme.Ink, span.Text))
		}
	}
	return b.String()
}

func (m model) toolLines(msg message) []string {
	if len(msg.tools) == 0 && msg.dataAsOf == "" {
		return nil
	}
	if msg.expanded {
		var lines []string
		for _, tool := range msg.tools {
			brief := tool.ArgsBrief
			if brief == "" || brief == "{}" {
				brief = ""
			}
			label := tool.Name
			if brief != "" {
				label += "  " + brief
			}
			lines = append(lines, "  "+m.theme.Paint(m.theme.Faint, label))
		}
		if msg.dataAsOf != "" {
			lines = append(lines, "  "+m.theme.Paint(m.theme.Faint, "data as of "+shortWhen(msg.dataAsOf)))
		}
		return lines
	}
	label := "› "
	if len(msg.tools) == 1 {
		label += "1 tool"
	} else if len(msg.tools) > 1 {
		label += fmt.Sprintf("%d tools", len(msg.tools))
	}
	if msg.dataAsOf != "" {
		if len(msg.tools) > 0 {
			label += " · "
		}
		label += shortWhen(msg.dataAsOf)
	}
	return []string{"  " + m.theme.Paint(m.theme.Faint, strings.TrimSpace(label))}
}

func (m model) composer() string {
	inner := m.composerInner()
	if m.plain {
		return inner
	}
	width := m.width - 2
	if width < 10 {
		width = 10
	}
	return lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(lipgloss.Color(m.border())).
		Width(width).
		Render(inner)
}

func (m model) border() string {
	if m.theme.Dark {
		return "#7f9d8c"
	}
	return "#4f6b5c"
}

func (m model) composerInner() string {
	switch {
	case m.streaming:
		return "  " + m.theme.Paint(m.theme.Accent, m.activity())
	case m.blocked:
		return "  " + m.theme.Paint(m.theme.Warn, "Update fplbud to keep chatting.")
	case m.chatOff:
		return "  " + m.theme.Paint(m.theme.Faint, "Chat isn't available yet.")
	case m.capped():
		when := "00:00 UTC"
		if m.usage != nil && m.usage.ResetsAt != "" {
			when = m.usage.ResetsAt
		}
		return "  " + m.theme.Paint(m.theme.Warn, "No turns left today. Resets at "+when+".")
	default:
		return m.input.View()
	}
}

func (m model) activity() string {
	frame := string([]rune("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")[m.spin%10])
	label := "Thinking"
	if m.waking && m.live.Phase == "" && m.live.Text() == "" {
		label = "Waking the server…"
	} else if m.live.ToolLabel != "" {
		label = m.live.ToolLabel
	} else if m.live.Phase == "checking" {
		label = "Checking the answer"
	} else if m.live.Phase == "tool" {
		label = "Working"
	}
	return frame + "  " + label
}

func (m model) footer() string {
	if m.slashOpen() {
		return m.theme.Paint(m.theme.Faint, "↑↓ choose  ·  enter run  ·  esc close")
	}
	if m.mode == screenThreads {
		extra := ""
		if m.confirming {
			extra = "delete this chat? y or n  ·  "
		}
		return m.theme.Paint(m.theme.Faint, extra+"enter open  ·  d delete  ·  n new  ·  esc close")
	}
	if m.streaming {
		return m.theme.Paint(m.theme.Faint, "esc stop")
	}
	hint := "enter send  ·  ctrl+j newline  ·  ctrl+t threads  ·  ? help"
	if m.scroll > 0 {
		hint = "pgdn to follow  ·  " + hint
	}
	if n := len([]rune(m.input.Value())); n >= 1200 {
		hint = fmt.Sprintf("%d left  ·  %s", 1500-n, hint)
	}
	return m.theme.Paint(m.theme.Faint, hint)
}

func (m model) loginView() string {
	var lines []string
	lines = append(lines, m.theme.Paint(m.theme.Bold, "FPLBud"))
	lines = append(lines, "")
	lines = append(lines, m.theme.Paint(m.theme.Ink, "Sign in with Google. This is the same account as the site."))
	lines = append(lines, m.theme.Paint(m.theme.Faint, "FPL credentials are never asked for."))
	lines = append(lines, "")
	if m.loginURL != "" {
		lines = append(lines, wrapPlain(m.theme.Paint(m.theme.Faint, m.loginURL), m.loginURL, m.width)...)
		lines = append(lines, "")
	}
	if m.pasting {
		lines = append(lines, m.composer())
		lines = append(lines, m.theme.Paint(m.theme.Faint, "enter continue  ·  esc back"))
	} else if m.login != nil {
		lines = append(lines, m.theme.Paint(m.theme.Accent, "Waiting for the browser…"))
		lines = append(lines, m.theme.Paint(m.theme.Faint, "p paste the link  ·  esc stays here  ·  ctrl+c quit"))
	} else {
		lines = append(lines, m.theme.Paint(m.theme.Faint, "enter  open the browser"))
		lines = append(lines, m.theme.Paint(m.theme.Faint, "p      paste a login link"))
		lines = append(lines, m.theme.Paint(m.theme.Faint, "q      quit"))
	}
	if m.notice != "" {
		lines = append(lines, "", m.theme.Paint(m.theme.Warn, m.notice))
	}
	return strings.Join(lines, "\n")
}

func (m model) helpView() string {
	rows := []string{
		"FPLBud",
		"",
		"enter       send",
		"ctrl+j      new line",
		"up          recall the last message",
		"esc         stop the answer",
		"ctrl+c      stop the answer, or quit",
		"/           command menu",
		"ctrl+n      new chat",
		"ctrl+t      threads",
		"ctrl+o      show how the last answer was made",
		"tab         move between the chat and the input",
		"+ / -       feedback, when the chat is focused",
		"1–4         ask a suggestion when the chat is empty",
		"/new        new chat",
		"/help       shortcuts",
		"/threads    earlier chats",
		"/usage      turns left today",
		"/memory     list saved preferences",
		"/logout     sign out",
		"",
		"esc closes this",
	}
	var lines []string
	for i, row := range rows {
		if i == 0 {
			lines = append(lines, m.theme.Paint(m.theme.Bold, row))
			continue
		}
		lines = append(lines, m.theme.Paint(m.theme.Faint, row))
	}
	return strings.Join(lines, "\n")
}

func (m model) threadView() string {
	if len(m.threads) == 0 {
		return m.theme.Paint(m.theme.Faint, "No chats yet. Press n to start one.")
	}
	var lines []string
	for i, thread := range m.threads {
		title := "New chat"
		if thread.Title != nil && strings.TrimSpace(*thread.Title) != "" {
			title = strings.TrimSpace(*thread.Title)
		}
		prefix := "  "
		if i == m.threadCursor {
			prefix = m.theme.Paint(m.theme.Accent, "› ")
		}
		lines = append(lines, prefix+m.theme.Paint(m.theme.Ink, trimWidth(title, m.width-4)))
	}
	return strings.Join(lines, "\n")
}

type segment struct {
	plain  string
	styled string
}

func fitSegments(width int, segs []segment) string {
	var b strings.Builder
	used := 0
	for i, seg := range segs {
		w := runewidth.StringWidth(seg.plain)
		gap := 0
		if i > 0 {
			gap = 2
		}
		if i > 0 && used+gap+w > width {
			break
		}
		if gap > 0 {
			b.WriteString("  ")
			used += gap
		}
		b.WriteString(seg.styled)
		used += w
	}
	return b.String()
}

func window(lines []string, height, scroll int) []string {
	if height < 1 {
		height = 1
	}
	if scroll < 0 {
		scroll = 0
	}
	if len(lines) > height {
		maxScroll := len(lines) - height
		if scroll > maxScroll {
			scroll = maxScroll
		}
		end := len(lines) - scroll
		return lines[end-height : end]
	}
	out := append([]string{}, lines...)
	for len(out) < height {
		out = append(out, "")
	}
	return out
}

func centerLines(lines []string, height int) []string {
	if len(lines) >= height {
		if len(lines) == height {
			return lines
		}
		return lines[:height]
	}
	top := (height - len(lines)) / 2
	out := make([]string, 0, height)
	for i := 0; i < top; i++ {
		out = append(out, "")
	}
	out = append(out, lines...)
	for len(out) < height {
		out = append(out, "")
	}
	return out
}

func wrapPlain(styled, plain string, width int) []string {
	if width < 8 || runewidth.StringWidth(plain) <= width {
		return []string{styled}
	}
	return wrapWords(plain, width)
}

func wrapWords(text string, width int) []string {
	if width < 4 {
		width = 4
	}
	var lines []string
	var cur string
	for _, word := range strings.Fields(text) {
		next := word
		if cur != "" {
			next = cur + " " + word
		}
		if runewidth.StringWidth(next) > width && cur != "" {
			lines = append(lines, cur)
			cur = word
			continue
		}
		cur = next
	}
	if cur != "" {
		lines = append(lines, cur)
	}
	return lines
}

func trimWidth(s string, width int) string {
	if runewidth.StringWidth(s) <= width {
		return s
	}
	out := ""
	for _, r := range s {
		next := out + string(r)
		if runewidth.StringWidth(next) > width-1 {
			return out + "…"
		}
		out = next
	}
	return out
}

func shortWhen(raw string) string {
	parsed, err := time.Parse(time.RFC3339, raw)
	if err != nil {
		parsed, err = time.Parse(time.RFC3339Nano, raw)
		if err != nil {
			return raw
		}
	}
	return parsed.Local().Format("2 Jan 15:04")
}
