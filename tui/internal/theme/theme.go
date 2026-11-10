// Package theme is the Matchday Programme palette, mapped onto the terminal.
package theme

import (
	"image/color"
	"os"

	"charm.land/lipgloss/v2"
)

type Theme struct {
	Dark   bool
	Plain  bool
	Ink    lipgloss.Style
	Soft   lipgloss.Style
	Faint  lipgloss.Style
	Accent lipgloss.Style
	Good   lipgloss.Style
	Warn   lipgloss.Style
	Bad    lipgloss.Style
	Bold   lipgloss.Style
	Paper  color.Color
	Fore   color.Color
}

func New(mode string, plain bool) Theme {
	if os.Getenv("NO_COLOR") != "" {
		plain = true
	}
	dark := mode != "light"
	if mode == "auto" || mode == "" {
		dark = true
	}
	t := Theme{Dark: dark, Plain: plain}
	if plain {
		empty := lipgloss.NewStyle()
		t.Ink, t.Soft, t.Faint, t.Accent, t.Good, t.Warn, t.Bad, t.Bold = empty, empty, empty, empty, empty, empty, empty, empty
		return t
	}
	ink, soft, faint := "#e7f6ec", "#b7d0c0", "#7f9d8c"
	paper, fore := "#0c1612", "#e7f6ec"
	accent, good, warn, bad := "#f0553a", "#3ddc97", "#d9a93a", "#e06a78"
	if !dark {
		ink, soft, faint = "#10241a", "#3c5a49", "#4f6b5c"
		paper, fore = "#e7f4ec", "#10241a"
		accent, good, warn, bad = "#d9381e", "#0e7a43", "#b8860b", "#7a1f2b"
	}
	t.Ink = lipgloss.NewStyle().Foreground(lipgloss.Color(ink))
	t.Soft = lipgloss.NewStyle().Foreground(lipgloss.Color(soft))
	t.Faint = lipgloss.NewStyle().Foreground(lipgloss.Color(faint))
	t.Accent = lipgloss.NewStyle().Foreground(lipgloss.Color(accent))
	t.Good = lipgloss.NewStyle().Foreground(lipgloss.Color(good))
	t.Warn = lipgloss.NewStyle().Foreground(lipgloss.Color(warn))
	t.Bad = lipgloss.NewStyle().Foreground(lipgloss.Color(bad))
	t.Bold = t.Ink.Bold(true)
	t.Paper = hex(paper)
	t.Fore = hex(fore)
	return t
}

func (t Theme) Paint(style lipgloss.Style, text string) string {
	if t.Plain || text == "" {
		return text
	}
	return style.Render(text)
}

func hex(s string) color.RGBA {
	var c color.RGBA
	c.A = 255
	if len(s) == 7 && s[0] == '#' {
		_, _ = parseByte(s[1:3], &c.R)
		_, _ = parseByte(s[3:5], &c.G)
		_, _ = parseByte(s[5:7], &c.B)
	}
	return c
}

func parseByte(s string, dest *uint8) (int, error) {
	var n int
	for _, ch := range s {
		n *= 16
		switch {
		case ch >= '0' && ch <= '9':
			n += int(ch - '0')
		case ch >= 'a' && ch <= 'f':
			n += int(ch-'a') + 10
		case ch >= 'A' && ch <= 'F':
			n += int(ch-'A') + 10
		}
	}
	*dest = uint8(n)
	return n, nil
}
