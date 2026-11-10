package chat

import (
	"testing"

	"github.com/dannyboy-1412/FPLBud/tui/internal/protocol"
)

func TestApplyResetsDraftOnNewRound(t *testing.T) {
	state := Apply(Turn{}, protocol.MessageDelta{Text: "Hello", Round: 1, Attempt: 1})
	state = Apply(state, protocol.MessageDelta{Text: " there", Round: 1, Attempt: 1})
	if state.Draft != "Hello there" {
		t.Fatalf("draft %q", state.Draft)
	}
	state = Apply(state, protocol.MessageDelta{Text: "Fixed", Round: 2, Attempt: 1})
	if state.Draft != "Fixed" {
		t.Fatalf("draft %q", state.Draft)
	}
}

func TestApplyFinalReplacesDraft(t *testing.T) {
	team := "MCI"
	price := 15.0
	state := Apply(Turn{}, protocol.MessageDelta{Text: "draft", Round: 1, Attempt: 1})
	state = Apply(state, protocol.MessageFinal{
		MessageID: 3,
		Text:      "Captain [[p:13|Haaland]]",
		Citations: []protocol.Citation{{PlayerID: 13, Name: "Haaland", Team: &team, PriceM: &price}},
		ToolsUsed: []protocol.ToolUse{{Name: "get_my_team", ArgsBrief: "{}"}},
		Grounding: "repaired",
	})
	state = Apply(state, protocol.Done{TurnID: 1, Status: "ok"})
	if state.Text() != "Captain [[p:13|Haaland]]" || state.Draft != "" || !state.Done {
		t.Fatalf("%#v", state)
	}
	if state.Grounding != "repaired" || state.MessageID != 3 || len(state.Tools) != 1 {
		t.Fatalf("%#v", state)
	}
}

func TestApplyToolSteps(t *testing.T) {
	state := Apply(Turn{}, protocol.ToolStart{CallID: "1", Name: "fixtures", Label: "Checking fixtures"})
	state = Apply(state, protocol.Status{Phase: "checking"})
	if len(state.Steps) != 2 || state.Steps[0].Done != true || state.Steps[1].Done != false {
		t.Fatalf("%#v", state.Steps)
	}
	state = Apply(state, protocol.ToolEnd{CallID: "1", OK: true, MS: 10})
	if !state.Steps[1].Done {
		t.Fatalf("%#v", state.Steps)
	}
}

func TestApplyIgnoresUnknown(t *testing.T) {
	state := Apply(Turn{Draft: "keep"}, "nope")
	if state.Draft != "keep" {
		t.Fatal(state.Draft)
	}
}
