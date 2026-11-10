# Terminal client

`fplbud` is a thin chat client. It talks to Supabase Auth and the FastAPI chat routes. FPL maths, squad rules, tool execution, and the model stay on the server. Do not add a database driver, an FPL client, or a direct LLM call to this module.

`docs/TUI_DESIGN.md` is the original spec. When it disagrees with this file, follow the code:

- The screen is one column. Threads open as an overlay, not a side panel.
- Launch always starts a blank chat. The latest thread is not restored.
- The API default is `https://fplbud.onrender.com`. `FPLBUD_API_URL` or `config.toml` overrides it. `NEXT_PUBLIC_API_URL` from the website `.env` is ignored because that file points at localhost.

## Where to edit

| Change | File |
|---|---|
| Slash commands and the `/` menu | `internal/ui/slash.go`, then the `switch` in `internal/ui/update.go` `slash()` |
| Keys, mouse, streaming | `internal/ui/update.go` |
| Layout, help text, footer | `internal/ui/view.go` |
| Composer | `internal/ui/input.go` |
| Sign-in, threads, usage, memory | `internal/ui/commands.go` |
| HTTP and SSE | `internal/api/` |
| What a streamed event does to the turn | `internal/chat/turn.go` |
| Markdown, player chips, escape stripping | `internal/render/` |
| PKCE login and the saved session | `internal/auth/` |
| Which host the binary calls | `internal/config/config.go` |
| `fplbud` subcommands | `cmd/fplbud/main.go` |

The event shapes live in `contracts/chat/`. The reducer should stay aligned with `web/lib/chat.ts`.

## Commands

`commandList()` in `slash.go` is the catalogue. Adding a command means a row there and a case in `slash()`. A test fails if a menu name falls through to "Unknown command".

Typing `/` opens the menu above the composer. `↑` and `↓` move, Enter, Tab, or a click runs the highlighted row, Esc clears the draft. `/memory forget <key>` hides the menu so arguments can be typed. `/new` and Ctrl+N both call `startNewChat()`: stop any stream, drop the transcript, and leave the thread id empty so the next send creates a thread. `/threads` and Ctrl+T open the overlay. `n` there also starts a new chat.

`/squad`, `/plan`, and `/rerun` only say those stay on the website.

## Session and API

Google sign-in is PKCE on `127.0.0.1` ports 53682–53684. Tests must inject a store that fails the keychain; do not write the Windows credential manager.

A desk load (`gotDesk`) clears `threadID` and `messages` on purpose. Do not restore `threads[0]` there.

JSON calls use a short timeout. The chat stream has no total timeout; an idle watchdog ends it. The same `client_msg_id` is reused if a send is retried.

## Checks

From `tui/`:

```bash
go test ./...
go vet ./...
```

Bubble Tea v2: `View` returns `tea.View`, key events are `tea.KeyPressMsg`, and the wheel is `tea.MouseWheelMsg`. Layout tests should assert visible width, not just that the screen renders.
