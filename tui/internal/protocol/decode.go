package protocol

import "encoding/json"

// Decode turns an SSE payload into a typed event. Unknown names return nil.
func Decode(name, data string) (any, error) {
	switch name {
	case "turn.start":
		return unmarshal[TurnStart](data)
	case "status":
		return unmarshal[Status](data)
	case "tool.start":
		return unmarshal[ToolStart](data)
	case "tool.end":
		return unmarshal[ToolEnd](data)
	case "message.delta":
		var ev MessageDelta
		if err := json.Unmarshal([]byte(data), &ev); err != nil {
			return nil, err
		}
		if ev.Attempt == 0 {
			ev.Attempt = 1
		}
		return ev, nil
	case "message.final":
		return unmarshal[MessageFinal](data)
	case "memory.proposal":
		return unmarshal[MemoryProposal](data)
	case "usage":
		return unmarshal[Usage](data)
	case "error":
		return unmarshal[ErrorEvent](data)
	case "done":
		return unmarshal[Done](data)
	default:
		return nil, nil
	}
}

func unmarshal[T any](data string) (any, error) {
	var ev T
	if err := json.Unmarshal([]byte(data), &ev); err != nil {
		return nil, err
	}
	return ev, nil
}
