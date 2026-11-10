// Package render turns harness text into terminal-safe lines.
package render

import "strings"

// Sanitize strips characters that could change the terminal. The server
// already cleans text; the terminal is a separate trust boundary.
func Sanitize(s string) string {
	var b strings.Builder
	b.Grow(len(s))
	r := []rune(s)
	for i := 0; i < len(r); i++ {
		ch := r[i]
		if ch == '\n' || ch == '\t' {
			b.WriteRune(ch)
			continue
		}
		if ch < 0x20 || (ch >= 0x7f && ch <= 0x9f) {
			if ch == 0x1b {
				i = skipEscape(r, i)
			}
			continue
		}
		if isHidden(ch) {
			continue
		}
		b.WriteRune(ch)
	}
	return b.String()
}

func skipEscape(r []rune, i int) int {
	if i+1 >= len(r) {
		return i
	}
	switch r[i+1] {
	case '[':
		for j := i + 2; j < len(r); j++ {
			if r[j] >= 0x40 && r[j] <= 0x7e {
				return j
			}
		}
		return len(r) - 1
	case ']':
		for j := i + 2; j < len(r); j++ {
			if r[j] == 0x07 {
				return j
			}
			if r[j] == 0x1b && j+1 < len(r) && r[j+1] == '\\' {
				return j + 1
			}
		}
		return len(r) - 1
	default:
		return i + 1
	}
}

func isHidden(ch rune) bool {
	switch ch {
	case 0x200b, 0x200c, 0x200d, 0x200e, 0x200f, 0x2060, 0xfeff:
		return true
	}
	if ch >= 0x202a && ch <= 0x202e {
		return true
	}
	if ch >= 0x2066 && ch <= 0x2069 {
		return true
	}
	return false
}
