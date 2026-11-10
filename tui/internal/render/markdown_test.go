package render

import (
	"strings"
	"testing"

	"github.com/dannyboy-1412/FPLBud/tui/internal/protocol"
)

func TestPlainMarkdownAndChips(t *testing.T) {
	team := "MCI"
	price := 15.0
	got := Plain("Captain **[[p:13|Haaland]]** is it.\n\n- Home to Wolves\n- Projected 7.4\n\nSee [docs](https://example.com)", []protocol.Citation{{
		PlayerID: 13, Name: "Haaland", Team: &team, PriceM: &price,
	}}, 80)
	if strings.Contains(got, "**") || strings.Contains(got, "[[p:") {
		t.Fatalf("%q", got)
	}
	if !strings.Contains(got, "Haaland MCI £15.0m") {
		t.Fatalf("%q", got)
	}
	if !strings.Contains(got, "• Home to Wolves") || !strings.Contains(got, "[docs](https://example.com)") {
		t.Fatalf("%q", got)
	}
}

func TestDraftChipIsBareName(t *testing.T) {
	lines := LayOut("[[p:13|Haaland]]", nil, true, 40)
	got := lines[0].Spans[0].Text
	if got != "Haaland" || lines[0].Spans[0].Kind != KindText {
		t.Fatalf("%#v", lines)
	}
}

func TestWrapsWords(t *testing.T) {
	got := Plain("one two three four", nil, 10)
	if strings.Contains(got, "three four") && !strings.Contains(got, "\n") {
		t.Fatalf("%q", got)
	}
	for _, line := range strings.Split(got, "\n") {
		if len(line) > 10 {
			t.Fatalf("line too wide %q", line)
		}
	}
}
