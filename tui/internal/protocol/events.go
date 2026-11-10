// Package protocol is the chat event contract shared with the harness.
package protocol

import "strings"

const Version = "1"

// Major is the leading component of a protocol version. "1" and "1.2" are the same major.
func Major(v string) string {
	v = strings.TrimSpace(v)
	if v == "" {
		return Version
	}
	if i := strings.IndexByte(v, '.'); i >= 0 {
		return v[:i]
	}
	return v
}

func Compatible(v string) bool {
	return Major(v) == Major(Version)
}

type Citation struct {
	PlayerID int      `json:"player_id"`
	Name     string   `json:"name"`
	Team     *string  `json:"team"`
	PriceM   *float64 `json:"price_m"`
}

type ToolUse struct {
	Name      string `json:"name"`
	ArgsBrief string `json:"args_brief"`
}

type TurnStart struct {
	TurnID          int    `json:"turn_id"`
	ThreadID        string `json:"thread_id"`
	UserMessageID   int    `json:"user_message_id"`
	PromptVersion   string `json:"prompt_version"`
	Model           string `json:"model"`
	ProtocolVersion string `json:"protocol_version"`
}

type Status struct {
	Phase string `json:"phase"`
}

type ToolStart struct {
	CallID string `json:"call_id"`
	Name   string `json:"name"`
	Label  string `json:"label"`
}

type ToolEnd struct {
	CallID  string  `json:"call_id"`
	OK      bool    `json:"ok"`
	MS      int     `json:"ms"`
	Summary *string `json:"summary"`
}

type MessageDelta struct {
	Text    string `json:"text"`
	Round   int    `json:"round"`
	Attempt int    `json:"attempt"`
}

type MessageFinal struct {
	MessageID   int        `json:"message_id"`
	Text        string     `json:"text"`
	Citations   []Citation `json:"citations"`
	DataAsOf    *string    `json:"data_as_of"`
	ToolsUsed   []ToolUse  `json:"tools_used"`
	Grounding   string     `json:"grounding"`
	Disclaimers []string   `json:"disclaimers"`
}

type MemoryProposal struct {
	ProposalID int    `json:"proposal_id"`
	Key        string `json:"key"`
	Value      string `json:"value"`
	Label      string `json:"label"`
}

type Usage struct {
	TurnsLeftToday int            `json:"turns_left_today"`
	Tokens         map[string]int `json:"tokens"`
}

type ErrorEvent struct {
	Code           string `json:"code"`
	Message        string `json:"message"`
	Retryable      bool   `json:"retryable"`
	TurnsLeftToday *int   `json:"turns_left_today"`
}

type Done struct {
	TurnID int    `json:"turn_id"`
	Status string `json:"status"`
}

// Raw is one SSE event before it is decoded.
type Raw struct {
	Name string
	Data string
	ID   string
}
