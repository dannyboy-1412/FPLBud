// Package chat reduces a stream of harness events into one turn.
package chat

import "github.com/dannyboy-1412/FPLBud/tui/internal/protocol"

const checkingLabel = "Checking the answer"

type Step struct {
	Label string
	Done  bool
}

type Proposal struct {
	ID    int
	Key   string
	Value string
	Label string
}

// Turn is the live assistant message for one send.
type Turn struct {
	Draft       string
	FinalText   string
	Round       int
	Attempt     int
	HasDraft    bool
	Phase       string
	ToolLabel   string
	Steps       []Step
	Citations   []protocol.Citation
	Tools       []protocol.ToolUse
	Grounding   string
	DataAsOf    string
	Disclaimers []string
	Error       string
	Retryable   bool
	TurnsLeft   *int
	Done        bool
	MessageID   int
	Proposal    *Proposal
	Stopped     bool
}

func (t Turn) Text() string {
	if t.FinalText != "" {
		return t.FinalText
	}
	return t.Draft
}

func (t Turn) Pending() bool {
	return !t.Done && !t.Stopped && t.Error == ""
}

// Apply folds one decoded event into the turn. Unknown events leave it unchanged.
func Apply(state Turn, event any) Turn {
	switch ev := event.(type) {
	case protocol.Status:
		state.Phase = ev.Phase
		if ev.Phase == "checking" && !hasOpen(state.Steps, checkingLabel) {
			state.Steps = appendStep(state.Steps, checkingLabel)
		}
		return state
	case protocol.ToolStart:
		state.Phase = "tool"
		state.ToolLabel = ev.Label
		if ev.Label != "" {
			state.Steps = appendStep(state.Steps, ev.Label)
			return state
		}
		state.Steps = finishSteps(state.Steps)
		return state
	case protocol.ToolEnd:
		state.ToolLabel = ""
		state.Steps = finishSteps(state.Steps)
		return state
	case protocol.MessageDelta:
		attempt := ev.Attempt
		if attempt == 0 {
			attempt = 1
		}
		same := state.HasDraft && state.Round == ev.Round && state.Attempt == attempt
		if !same {
			state.Draft = ""
		}
		state.Round = ev.Round
		state.Attempt = attempt
		state.HasDraft = true
		state.Draft += ev.Text
		return state
	case protocol.MessageFinal:
		state.Draft = ""
		state.FinalText = ev.Text
		state.Citations = ev.Citations
		state.Tools = ev.ToolsUsed
		state.Grounding = ev.Grounding
		state.MessageID = ev.MessageID
		state.Disclaimers = ev.Disclaimers
		if ev.DataAsOf != nil {
			state.DataAsOf = *ev.DataAsOf
		}
		state.Steps = finishSteps(state.Steps)
		return state
	case protocol.Usage:
		left := ev.TurnsLeftToday
		state.TurnsLeft = &left
		return state
	case protocol.ErrorEvent:
		state.Error = ev.Message
		state.Retryable = ev.Retryable
		state.Draft = ""
		if ev.TurnsLeftToday != nil {
			state.TurnsLeft = ev.TurnsLeftToday
		}
		return state
	case protocol.Done:
		state.Done = true
		state.Steps = finishSteps(state.Steps)
		return state
	case protocol.MemoryProposal:
		state.Proposal = &Proposal{ID: ev.ProposalID, Key: ev.Key, Value: ev.Value, Label: ev.Label}
		return state
	default:
		return state
	}
}

func hasOpen(steps []Step, label string) bool {
	for _, step := range steps {
		if !step.Done && step.Label == label {
			return true
		}
	}
	return false
}

func finishSteps(steps []Step) []Step {
	if len(steps) == 0 {
		return steps
	}
	out := make([]Step, len(steps))
	for i, step := range steps {
		step.Done = true
		out[i] = step
	}
	return out
}

func appendStep(steps []Step, label string) []Step {
	return append(finishSteps(steps), Step{Label: label})
}
