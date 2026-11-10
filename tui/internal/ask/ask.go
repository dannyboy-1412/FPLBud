// Package ask runs one chat turn without the interactive screen.
package ask

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"time"

	"github.com/dannyboy-1412/FPLBud/tui/internal/api"
	"github.com/dannyboy-1412/FPLBud/tui/internal/chat"
	"github.com/dannyboy-1412/FPLBud/tui/internal/protocol"
	"github.com/dannyboy-1412/FPLBud/tui/internal/render"
)

// Run sends one question. Draft text goes to stderr and the validated answer to stdout.
func Run(ctx context.Context, client *api.Client, threadID, question string, jsonOut bool, stdout, stderr io.Writer) error {
	if threadID == "" {
		thread, err := client.CreateThread(ctx)
		if err != nil {
			return err
		}
		threadID = thread.ID
	}
	ch, err := client.OpenStream(ctx, threadID, question, newID(), 45*time.Second)
	if err != nil {
		return err
	}
	var state chat.Turn
	for msg := range ch {
		if msg.Done {
			if msg.Err != nil && !errors.Is(msg.Err, context.Canceled) {
				return msg.Err
			}
			break
		}
		if jsonOut {
			raw, err := json.Marshal(msg.Event)
			if err != nil {
				return err
			}
			fmt.Fprintf(stdout, "%s\n", raw)
		}
		state = chat.Apply(state, msg.Event)
		if delta, ok := msg.Event.(protocol.MessageDelta); ok && !jsonOut {
			_, _ = io.WriteString(stderr, delta.Text)
		}
	}
	if state.Error != "" {
		return errors.New(state.Error)
	}
	if !jsonOut {
		_, _ = io.WriteString(stderr, "\n")
		answer := render.Plain(state.Text(), state.Citations, 80)
		if answer != "" {
			fmt.Fprintln(stdout, answer)
		}
	}
	return nil
}

func newID() string {
	return protocolID()
}
