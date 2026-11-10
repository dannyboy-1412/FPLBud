package render

import (
	"strings"
	"testing"
	"unicode/utf8"
)

func TestSanitizeStripsTerminalControls(t *testing.T) {
	in := "Haaland\x1b[2J\x1b]52;c;eA==\x07\u202ebad\u200bname"
	got := Sanitize(in)
	if strings.Contains(got, "\x1b") || strings.Contains(got, "[2J") || strings.Contains(got, "52;") {
		t.Fatalf("%q", got)
	}
	if strings.ContainsRune(got, '\u202e') || strings.ContainsRune(got, '\u200b') {
		t.Fatalf("%q", got)
	}
	if !strings.Contains(got, "Haaland") || !strings.Contains(got, "badname") {
		t.Fatalf("%q", got)
	}
}

func TestSanitizeKeepsNewlines(t *testing.T) {
	if Sanitize("a\nb\tc") != "a\nb\tc" {
		t.Fatal(Sanitize("a\nb\tc"))
	}
}

func FuzzSanitize(f *testing.F) {
	f.Add("plain")
	f.Add("\x1b[31mred\x1b[0m")
	f.Add("\x1b]0;title\x07")
	f.Add("\u202eoverride")
	f.Fuzz(func(t *testing.T, s string) {
		if !utf8.ValidString(s) {
			t.Skip()
		}
		got := Sanitize(s)
		for _, r := range got {
			if r == 0x1b || (r >= 0x7f && r <= 0x9f) || isHidden(r) {
				t.Fatalf("unsafe %q in %q", string(r), got)
			}
		}
	})
}
