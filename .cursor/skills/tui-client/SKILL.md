---
name: tui-client
description: >-
  Guides changes to the fplbud terminal client. Use when editing tui/, the
  slash-command menu, the chat transcript, sign-in, streaming, or when the user
  mentions fplbud, the TUI, or terminal chat.
---

# fplbud terminal client

Read `tui/AGENTS.md` before editing. The client is a window onto the server chat. Do not reimplement FPL rules, tools, or the model here.

## Commands

The menu the user opens with `/` is `commandList()` in `tui/internal/ui/slash.go`. Each name needs a matching case in `slash()` in `tui/internal/ui/update.go`. Keep both in sync. New chat goes through `startNewChat()` so Ctrl+N, `/new`, and the menu row behave the same way.

Launch stays a blank chat. Do not load the newest thread in `loadDesk` or `gotDesk`.

## After a change

From `tui/`, run `go test ./...`. If the menu, keys, or layout moved, the tests in `internal/ui/slash_test.go` and `internal/ui/view_test.go` are the ones that should fail first.
