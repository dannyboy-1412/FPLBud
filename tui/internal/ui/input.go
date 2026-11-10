package ui

import (
	"charm.land/bubbles/v2/key"
	"charm.land/bubbles/v2/textarea"
	"charm.land/lipgloss/v2"

	"github.com/dannyboy-1412/FPLBud/tui/internal/theme"
)

const askPlaceholder = "Ask about your team, a player, or this gameweek…"
const pastePlaceholder = "Paste the redirected URL"

func newInput(th theme.Theme) textarea.Model {
	ta := textarea.New()
	ta.ShowLineNumbers = false
	ta.CharLimit = 1500
	ta.MaxHeight = 6
	ta.Prompt = "› "
	ta.Placeholder = askPlaceholder
	ta.EndOfBufferCharacter = ' '
	ta.SetHeight(1)
	ta.SetWidth(40)
	ta.KeyMap.InsertNewline = key.NewBinding(key.WithKeys("ctrl+j"))
	ta.SetStyles(inputStyles(th))
	return ta
}

func inputStyles(th theme.Theme) textarea.Styles {
	s := textarea.DefaultStyles(th.Dark)
	if th.Plain {
		return s
	}
	base := lipgloss.NewStyle()
	s.Focused.Base = base
	s.Focused.CursorLine = base
	s.Focused.EndOfBuffer = base
	s.Focused.Text = th.Ink
	s.Focused.Placeholder = th.Faint
	s.Focused.Prompt = th.Accent
	s.Blurred = s.Focused
	s.Blurred.Text = th.Faint
	s.Blurred.Prompt = th.Faint
	return s
}

func (m *model) fitInput() {
	width := m.width - 4
	if width < 12 {
		width = 12
	}
	lines := 1
	for _, r := range m.input.Value() {
		if r == '\n' {
			lines++
		}
	}
	if lines > 6 {
		lines = 6
	}
	m.input.SetWidth(width)
	m.input.SetHeight(lines)
	m.syncCommandCursor()
}
