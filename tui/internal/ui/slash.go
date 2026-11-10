package ui

import (
	"strings"

	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
)

// slashCommand is one row in the menu that opens when the composer starts with /.
// Names here are the only catalogue; slash() is what actually runs them.
type slashCommand struct {
	Name string
	Hint string
}

func commandList() []slashCommand {
	return []slashCommand{
		{Name: "new", Hint: "Start a new chat"},
		{Name: "threads", Hint: "Earlier chats"},
		{Name: "help", Hint: "Shortcuts"},
		{Name: "usage", Hint: "Turns left today"},
		{Name: "memory", Hint: "Saved preferences"},
		{Name: "logout", Hint: "Sign out"},
		{Name: "squad", Hint: "Squad stays on the website"},
		{Name: "plan", Hint: "Plans stay on the website"},
		{Name: "rerun", Hint: "Reruns stay on the website"},
	}
}

func filterCommands(token string) []slashCommand {
	token = strings.ToLower(token)
	var out []slashCommand
	for _, cmd := range commandList() {
		if token == "" || strings.HasPrefix(cmd.Name, token) {
			out = append(out, cmd)
		}
	}
	return out
}

// slashToken is the command prefix while the menu should be open.
// A slash command with arguments ("/memory forget") is typed without the menu.
func (m model) slashToken() (string, bool) {
	if !m.composerLive() || m.focus != focusComposer {
		return "", false
	}
	text := m.input.Value()
	if strings.Contains(text, "\n") {
		return "", false
	}
	fields := strings.Fields(text)
	if len(fields) != 1 || !strings.HasPrefix(fields[0], "/") {
		return "", false
	}
	return strings.TrimPrefix(strings.ToLower(fields[0]), "/"), true
}

func (m model) slashOpen() bool {
	_, open := m.slashToken()
	return open
}

func (m model) slashMatches() []slashCommand {
	token, open := m.slashToken()
	if !open {
		return nil
	}
	return filterCommands(token)
}

func (m *model) syncCommandCursor() {
	token, open := m.slashToken()
	if !open {
		m.commandQuery = "\x00"
		m.commandCursor = 0
		return
	}
	if token != m.commandQuery {
		m.commandQuery = token
		m.commandCursor = 0
	}
	n := len(filterCommands(token))
	if n == 0 {
		m.commandCursor = 0
		return
	}
	if m.commandCursor >= n {
		m.commandCursor = n - 1
	}
	if m.commandCursor < 0 {
		m.commandCursor = 0
	}
}

func (m model) paletteBudget() int {
	reserved := 1 + 2 + m.composerHeight() + 1
	if m.banner() != "" {
		reserved++
	}
	room := m.height - reserved - 1
	if room < 4 {
		return 4
	}
	return room
}

func (m model) paletteRowCap() int {
	capRows := m.paletteBudget()
	if !m.plain {
		capRows -= 2
	}
	if capRows < 1 {
		return 1
	}
	return capRows
}

func (m model) visibleCommands() ([]slashCommand, int) {
	all := m.slashMatches()
	if len(all) == 0 {
		return nil, 0
	}
	limit := m.paletteRowCap()
	if len(all) <= limit {
		return all, 0
	}
	start := m.commandCursor - limit/2
	if start < 0 {
		start = 0
	}
	if start+limit > len(all) {
		start = len(all) - limit
	}
	return all[start : start+limit], start
}

func (m model) paletteHeight() int {
	if !m.slashOpen() {
		return 0
	}
	rows := len(m.slashMatches())
	if rows == 0 {
		rows = 1
	} else if rows > m.paletteRowCap() {
		rows = m.paletteRowCap()
	}
	if m.plain {
		return rows
	}
	return rows + 2
}

func (m model) paletteTop() int {
	y := 1
	if m.banner() != "" {
		y++
	}
	y++
	y += m.transcriptHeight()
	y++
	return y
}

func (m model) commandIndexAt(y int) (int, bool) {
	items, offset := m.visibleCommands()
	if len(items) == 0 {
		return 0, false
	}
	row := y - m.paletteTop()
	if !m.plain {
		row--
	}
	if row < 0 || row >= len(items) {
		return 0, false
	}
	return offset + row, true
}

func (m model) startNewChat() (model, tea.Cmd) {
	m.stopStream(false)
	m.messages = nil
	m.threadID = ""
	m.proposal = nil
	m.scroll = 0
	m.notice = ""
	m.mode = screenChat
	m.focus = focusComposer
	m.confirming = false
	m.input.SetValue("")
	m.fitInput()
	return m, m.input.Focus()
}

func (m model) paletteView() string {
	if !m.slashOpen() {
		return ""
	}
	items, offset := m.visibleCommands()
	width := m.width - 2
	if width < 10 {
		width = 10
	}
	innerWidth := width
	if !m.plain {
		innerWidth -= 2
	}
	if innerWidth < 8 {
		innerWidth = 8
	}
	var lines []string
	if len(items) == 0 {
		lines = append(lines, "  "+m.theme.Paint(m.theme.Faint, "No matching commands"))
	}
	for i, cmd := range items {
		lines = append(lines, m.commandRow(cmd, offset+i == m.commandCursor, innerWidth))
	}
	inner := strings.Join(lines, "\n")
	if m.plain {
		return inner
	}
	return lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(lipgloss.Color(m.border())).
		Width(width).
		Render(inner)
}

func (m model) commandRow(cmd slashCommand, selected bool, width int) string {
	name := "/" + cmd.Name
	gap := 12 - len(name)
	if gap < 2 {
		gap = 2
	}
	label := name + strings.Repeat(" ", gap) + cmd.Hint
	label = trimWidth(label, width-2)
	if selected {
		return m.theme.Paint(m.theme.Accent, "› ") + m.theme.Paint(m.theme.Bold, label)
	}
	return "  " + m.theme.Paint(m.theme.Ink, label)
}

func (m model) runCommand(name string) (model, tea.Cmd) {
	m.input.SetValue("")
	m.fitInput()
	return m.slash("/" + name)
}
