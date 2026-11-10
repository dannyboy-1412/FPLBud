package ui

import (
	"fmt"
	"io"
	"os"

	tea "charm.land/bubbletea/v2"

	"github.com/dannyboy-1412/FPLBud/tui/internal/config"
)

// Run starts the full-screen chat. It returns when the user quits.
func Run(cfg config.Config, plain bool, themeName string, output io.Writer) error {
	m := newModel(cfg, plain, themeName)
	program := tea.NewProgram(m)
	if output != nil && output != os.Stdout {
		program = tea.NewProgram(m, tea.WithOutput(output))
	}
	if _, err := program.Run(); err != nil {
		return fmt.Errorf("fplbud: %w", err)
	}
	return nil
}
