# FPLBud TUI: Design (draft 1, 31 Oct 2026)

**What this is:** the design for `fplbud`, a terminal client written in Go that lives in this monorepo. A signed-in FPLBud user can chat with the FPLBud Assistant (the harness in `docs/CHATBOT_HARNESS_SPEC.md`), see their squad and saved plans, and watch the deadline without opening a browser.
**Status:** design only. The read-only views can start any time because they use endpoints that already exist. Chat needs harness phase H0, and is worth shipping once H2 (plan and optimiser tools) is live. Anything marked **[verify]** must be checked at build time.
**Core principle:** the TUI is a thin client. Every rule, limit, safety check and FPL calculation stays on the server. The TUI never talks to Postgres, the FPL API or the LLM provider.

---

## 1. Goals and non-goals

### Goals
1. Chat with the assistant from a terminal with the same behaviour as the web: streamed drafts, a validated final answer, player citations, tool status, "How I got this", feedback and the daily cap.
2. Keep the context a manager needs next to the chat: decision GW and deadline countdown, squad (XI, bench, captain, flags), the saved 1/3/5-GW plans, and turns left today.
3. Sign in with the same Google account through Supabase. Tokens live in the OS keychain.
4. Work in Windows Terminal (PowerShell), macOS Terminal and iTerm2, and common Linux terminals, in light and dark themes.
5. Offer a scriptable one-shot mode (`fplbud ask`) that also works as a smoke test for the harness.

### Non-goals (v1)
- No squad, weights or settings editing. Those stay on the web (`/settings`, `/onboarding`). The only write besides chat is `/rerun`, which calls the existing capped endpoint.
- No guest mode (see Q3).
- No offline mode, local model, or on-disk cache of chat content or squad data.
- No terminal hyperlinks, inline images or clipboard writes driven by server content (§6).
- No plugins or themes beyond light, dark and plain.

---

## 2. Where it lives

```
tui/
  go.mod                  module github.com/dannyboy-1412/FPLBud/tui
  cmd/fplbud/main.go      subcommands: chat (default), ask, login, logout, whoami, version
  internal/config/        config file + env overrides
  internal/auth/          PKCE loopback login, token store, refresh, cross-process lock
  internal/api/           HTTP client, typed endpoints, SSE reader
  internal/protocol/      chat event types (mirrors contracts/chat/events.schema.json)
  internal/chat/          pure reducer: events -> conversation state
  internal/render/        sanitiser, restricted markdown, player chips, wrapping
  internal/ui/            Bubble Tea models: app, header, threads, transcript, composer, squad, help
  internal/theme/         palette, adaptive colours, NO_COLOR, plain mode
  testdata/               fake API responses
```

`tui/` has its own `go.mod`, so Go tooling stays separate from the uv workspace and the pnpm app. One module means no `go.work`. The repo map in `.cursor/rules/codebase-map.mdc` gets a `tui/` row, and `.gitignore` gets `tui/dist/`.

Shared fixtures come from `contracts/chat/` at the repo root, which the harness produces (§10): the event JSON Schema and golden SSE transcripts. The Go tests read them by relative path.

---

## 3. Stack

| Concern | Choice | Why |
|---|---|---|
| Language | Go, current stable, pinned with `go` and `toolchain` lines in `go.mod` **[verify version]** | single static binary per OS, good terminal ecosystem |
| TUI framework | Bubble Tea + Bubbles (textarea, viewport, spinner, list, key, help) + Lip Gloss | Elm-style model/update/view fits a pure event reducer. Use v2 if it is stable at build time **[verify import paths]** |
| Markdown | Small in-house renderer, **not Glamour** | Glamour renders full markdown including links. The harness emits a restricted subset plus `[[p:ID\|Name]]` chips, so we render exactly that and nothing else |
| HTTP | stdlib `net/http` | no SDK needed |
| SSE | hand-written reader (about 80 lines) | the format is simple, and owning it lets us test every chunk boundary |
| Token storage | `github.com/zalando/go-keyring` **[verify maintenance]** | Windows Credential Manager, macOS Keychain, Secret Service |
| Browser launch | `github.com/pkg/browser` or `os/exec` per OS | only ever opens the login URL the TUI built |
| Tests | stdlib `testing`, `net/http/httptest`, `teatest` (`github.com/charmbracelet/x/exp/teatest`) **[verify]** | golden view snapshots without a real terminal |
| Lint | `go vet` + `staticcheck` (or `golangci-lint`) | |
| Release | GoReleaser | Windows/macOS/Linux binaries (see Q1) |

---

## 4. Authentication

The TUI uses the same Supabase project and Google provider as the web. FastAPI already accepts `Authorization: Bearer <access_token>` on every `/me`, `/agent` and `/chat` route, so the TUI only needs a valid Supabase session. Google login gives no FPL access, and FPL credentials are never asked for (same as the web, `docs/ARCHITECTURE.md` §2A).

### 4.1 Login: authorization code with PKCE and a loopback redirect (RFC 8252)
1. Generate `code_verifier` (32 random bytes, base64url) and `code_challenge = BASE64URL(SHA256(code_verifier))`.
2. Listen on `127.0.0.1:<port>`, trying a short fixed list (for example 53682, 53683, 53684) so the ports can be allow-listed.
3. Open the browser at
   `{SUPABASE_URL}/auth/v1/authorize?provider=google&redirect_to=http://127.0.0.1:<port>/callback&code_challenge=<challenge>&code_challenge_method=s256`.
4. Google redirects to Supabase's own callback (already configured for the web), and Supabase redirects to the loopback URL with `?code=…`.
5. Exchange the code: `POST {SUPABASE_URL}/auth/v1/token?grant_type=pkce` with body `{"auth_code": "<code>", "code_verifier": "<verifier>"}` and header `apikey: <anon key>`. The response carries `access_token`, `refresh_token`, `expires_in` and `user`.
6. Serve a short "Signed in. You can close this tab." page, close the listener, and store the session.

These endpoint names and fields match what supabase-js sends for its PKCE flow at the time of writing **[verify against current Supabase Auth docs]**.

**Supabase config:** add the loopback callback URLs under Auth → URL Configuration → Redirect URLs. Use one wildcard-port pattern if Supabase supports it; otherwise list the fixed ports **[verify wildcard support]**. Google's console needs no change because Google only ever redirects to Supabase.

**Headless or SSH fallback:** `fplbud login --no-browser` prints the authorize URL. The user opens it on any device and signs in. The final redirect to `127.0.0.1` fails in that browser, so the user copies the full URL from the address bar and pastes it into the TUI. The TUI pulls out `code` and exchanges it with the verifier it kept. The code is useless without that verifier.

### 4.2 Session lifecycle
- **Refresh** before any request when the access token expires within 60 s: `POST /auth/v1/token?grant_type=refresh_token` with `{"refresh_token": …}`. Supabase rotates refresh tokens and detects reuse **[verify reuse window]**, so the TUI saves the new refresh token before it uses the new access token, and serialises refreshes across concurrent `fplbud` processes with a lock file in the config dir.
- **401 from FastAPI:** refresh once and retry once. A second 401, or `invalid_grant` on refresh, clears the session and shows the login screen.
- **Storage:** one keychain item (service `fplbud`, account = Supabase project ref) holding `{access_token, refresh_token, expires_at, user_id, email}`. Where no keychain is available (some Linux servers), the fallback is `os.UserConfigDir()/fplbud/session.json` with 0600 permissions and a one-line warning.
- **Logout:** `POST /auth/v1/logout` with the access token **[verify]**, then delete the stored session.

### 4.3 Public configuration
The Supabase URL and anon key are public by design (every browser already gets them). Bake production defaults in with `-ldflags` at build time. Allow overrides through `os.UserConfigDir()/fplbud/config.toml` or env (`FPLBUD_API_URL`, `FPLBUD_SUPABASE_URL`, `FPLBUD_SUPABASE_ANON_KEY`) for local development against `http://localhost:8000`. No secret ships in the binary.

---

## 5. Talking to the API

The TUI calls FastAPI directly (`FPLBUD_API_URL`, default the Render URL), not the Next.js proxy.

| Endpoint | Used for |
|---|---|
| `GET /meta` | decision GW, deadline, `data_version`, last ingest |
| `GET /me` | profile, latest snapshot, `latest_run_id` |
| `GET /me/agent/latest` | saved plans for horizons 1, 3 and 5 |
| `POST /me/agent/rerun` | `/rerun` (server caps apply) |
| `GET /chat/usage` | turns left, reset time |
| `GET /chat/threads`, `GET /chat/threads/{id}`, `DELETE /chat/threads/{id}` | thread list, history, delete |
| `POST /chat/threads/{id}/messages` | send a message; response is `text/event-stream` |
| `POST /chat/messages/{id}/feedback` | thumbs up or down with an optional reason |
| `GET /chat/memory`, `DELETE /chat/memory`, `POST /chat/memory/confirm` | preferences (H3) |

**Client identity:** every request sends `User-Agent: fplbud-tui/<version> (<os>/<arch>)` and `X-FPLBud-Client: tui/<version>`. The harness stores the client on each `chat_turns` row so metrics can be split by web, TUI and eval traffic.

**Timeouts and retries:**
- JSON requests: 10 s timeout. GETs retry twice on network errors and 502/503/504 with backoff (Render free instances can be cold).
- The stream has no total timeout, but it has a 45 s idle timeout. The server sends a `: ping` comment every 15 s.
- Sending a message is only ever retried with the same `client_msg_id`. The server dedupes it, so a retry never double-charges.
- 429 shows the server's message and reset time. 503 `BUSY` waits for `Retry-After`. A 404 on a thread drops it from the list.

**SSE reader:** reads bytes with `bufio.Reader` (not `Scanner` with its 64 KB default) and caps a line at 1 MB. It handles `event:`, `data:` (multi-line) and `id:` fields, ignores `:` comment lines, dispatches on a blank line, accepts LF and CRLF, and ignores unknown event types so newer servers don't break older clients. Bytes accumulate until a line ends, so a UTF-8 character split across network chunks is safe.

**Cancel:** Ctrl+C during a turn closes the response body. The server sees the disconnect, cancels the turn, records it as `abandoned` with the usage so far, and the TUI marks the draft "stopped".

---

## 6. Event contract and rendering

### 6.1 Contract
The harness defines the stream once in Python (`fplcore/chat/events.py`) and exports `contracts/chat/events.schema.json`, plus golden transcripts in `contracts/chat/sse/*.txt` recorded from real harness runs. The TUI:
- mirrors the event types in `internal/protocol` (hand-written structs, see Q4);
- has a contract test that runs every golden transcript through the SSE reader and the reducer and checks the final state, so a protocol change fails Go CI before it reaches users;
- reads `protocol_version` from `turn.start`. On a different major version it shows "Update fplbud to keep chatting" and stops sending.

### 6.2 Reducer
`internal/chat` is a pure function `Apply(state, event) state`, the same model as the web client:

| Event | Effect |
|---|---|
| `turn.start` | add a pending assistant message; lock the composer |
| `status`, `tool.start`, `tool.end` | update the status line ("Checking fixtures…") and the tool list for "How I got this" |
| `message.delta` | append to the draft. The draft resets when the delta's `round` or `attempt` changes, so a preamble from an earlier round or a retried generation does not pile up |
| `message.final` | replace the draft with the validated text and attach `citations`, `data_as_of`, `tools_used` and `grounding`. On `repaired` or `fallback`, show "adjusted to match FPLBud's data" |
| `memory.proposal` | inline confirm card: `y` saves, `n` dismisses |
| `usage` | update the header badge |
| `error` | show the user-safe message, plus a retry hint when `retryable` |
| `done` | unlock the composer |

### 6.3 Rendering rules
- **Sanitise every server string before layout.** Strip ESC and all other C0/C1 control characters except `\n` and `\t`, plus bidi overrides and zero-width characters. This blocks terminal escape injection: a hostile FPL team name or a model output carrying OSC 8 hyperlinks, OSC 52 clipboard writes or title changes. The server already sanitises; the client does it again because the terminal is its own trust boundary.
- **Restricted markdown only:** paragraphs, `**bold**`, and `-` or `1.` lists. Anything else prints literally.
- **Player chips:** `[[p:ID|Name]]` becomes the bold accent name followed by `TEAM £x.xm`, taken from the `citations` in `message.final`. Draft text shows the plain name.
- **No hyperlinks, no images, no clipboard writes** from server content. This keeps the harness's "no egress channel" property in the terminal. The only URL the TUI ever opens is the login URL it built.
- Wrap to the viewport width and re-flow on resize.

---

## 7. Screens

```
 FPLBud  GW 9 · deadline Sat 31 Oct 21:00 (5d 4h) · data as of 05:10 · 14 left today
┌ Threads ──────────┐┌ Danny FC ────────────────────────────────┐┌ Squad ──────────────────┐
│ > Captain GW9     ││ You  Who should I captain this week?     ││ GKP Raya      ARS  5.9  │
│   Hit for Watkins ││                                          ││ DEF Gabriel   ARS  6.2  │
│   Chip timing     ││ FPLBud  Captain Haaland MCI £15.0m,      ││ ...                     │
│                   ││ vice Saka ARS £10.1m.                    ││ C Haaland   V Saka      │
│                   ││ - Projected 7.4 at home to ...           ││ ! Mitoma 75% (knock)    │
│                   ││ Data as of 25 Oct 05:10.                 ││ Bank £0.6m · FT 1 (est) │
│                   ││ > How I got this (2 tools)               ││ Plan 3GW: roll          │
│                   ││ ⠋ Checking fixtures…                     ││                         │
└───────────────────┘└──────────────────────────────────────────┘└─────────────────────────┘
 > Ask about your team…                                   1,500 · Enter send · Ctrl+J newline
 ? help   Tab focus   Ctrl+N new   Ctrl+T threads   Ctrl+S squad   Ctrl+C stop/quit
```

**Responsive layout:** below about 100 columns the side panels become toggled overlays. Below about 60 columns only the transcript and composer show.

**Panels:**
- **Header:** wordmark, decision GW and a deadline countdown that ticks each minute and turns vermilion under 2 hours, data as-of with a "stale" marker, turns left today.
- **Threads** (toggle): from `GET /chat/threads`. Enter opens a thread. `d` deletes it after a confirm.
- **Transcript:** a viewport that sticks to the bottom unless the user has scrolled up. Enter on "How I got this" expands tools, brief args, `data_version` and `prompt_version`. `+` and `-` give feedback on the focused answer; `-` asks for an optional reason.
- **Composer:** textarea with the server's 1,500-character limit shown as a counter. It is disabled during a turn. Up recalls the last message when the composer is empty.
- **Squad** (toggle): XI by position, bench order, captain and vice, bank, free transfers (marked estimated), chips, flags. A second tab shows the saved 1/3/5-GW plans: headline, transfers, hits, captain.
- **Help** overlay on `?`.

**Slash commands:** `/new`, `/threads`, `/squad`, `/plan 1|3|5`, `/rerun`, `/usage`, `/memory` (list and forget), `/logout`, `/help`. An empty thread shows the same suggested prompts as the web.

**States:**
- Not signed in: login screen with the browser and `--no-browser` options.
- Signed in, no saved team: banner "Add your team at <site>/onboarding". General chat still works, matching the harness tiers.
- Chat disabled (`CHAT_ENABLED=false`, or 404 on `/chat/*`): "Chat isn't available yet". Squad and plan views still work.
- Capped: the composer is replaced by the reset time.
- Server waking up (Render cold start): "Waking the server…" after 5 s.

**Theme:** the Matchday Programme palette (`docs/design/01-matchday-programme.md`, tokens in `web/app/globals.css`) mapped to Lip Gloss adaptive colours. Ink and paper for text, vermilion for accent and urgency, racing green for positive numbers, ochre for doubtful flags, claret for errors. The background is detected automatically, `--theme light|dark|auto` overrides it, and `NO_COLOR` is respected.

**Accessibility:** everything works from the keyboard. No signal is colour-only (flags also show `!` and the percentage). `--plain` prints a linear transcript with no boxes or cursor movement, for screen readers and logs.

---

## 8. Commands

| Command | Behaviour |
|---|---|
| `fplbud` or `fplbud chat` | interactive TUI |
| `fplbud ask "who should I captain?" [--thread ID] [--json]` | one turn. Streams the draft to stderr, prints the validated final text to stdout, exits non-zero on `error`. `--json` prints raw events as JSON lines |
| `fplbud login [--no-browser]`, `fplbud logout`, `fplbud whoami` | session management |
| `fplbud version` | binary version and the protocol version it speaks |

---

## 9. Testing

| Layer | What |
|---|---|
| Pure units | SSE reader: every golden transcript split at every byte offset, CRLF, comments, oversized lines. Reducer. Sanitiser fuzzed with `testing.F` (output never contains ESC or a C1 control). Markdown and chip renderer. PKCE helpers. Refresh logic with a fake clock |
| Contract | golden transcripts from `contracts/chat/sse/` through reader and reducer, with expected final states |
| API client | `httptest.Server` fakes for 401 → refresh → retry, 429, 503 with `Retry-After`, disconnect mid-stream, idle timeout, unknown event types |
| UI | `teatest` golden snapshots of the main screens at 80×24 and 140×40, plus resize |
| Manual | Windows Terminal (PowerShell), macOS Terminal, one Linux terminal; light and dark; `--plain` |

CI: a new `tui` job in `.github/workflows/ci.yml` with `working-directory: tui`. It runs `actions/setup-go`, `go vet ./...`, `staticcheck ./...` and `go test -race ./...`.

---

## 10. What the TUI needs from the harness

The harness plan already covers these. They are listed here so the dependency stays visible:
1. Chat endpoints on FastAPI that accept the Supabase Bearer token directly, not only through the Next.js proxy.
2. A versioned event contract: `protocol_version` on `turn.start`, a JSON Schema export, and golden SSE transcripts under `contracts/chat/`.
3. `round` and `attempt` fields on `message.delta`.
4. Renderer-neutral answers: plain text, the restricted markdown subset, `[[p:ID|Name]]` markup and structured `citations`. No HTML and no links.
5. Idempotent sends keyed by `client_msg_id`, and cancel on disconnect.
6. `: ping` heartbeats every 15 s while the model or tools are working.
7. Stable, documented error codes.
8. A `client` column on `chat_turns`, filled from `X-FPLBud-Client`.

Outside the harness: add the loopback redirect URLs to Supabase's allow-list (§4.1).

---

## 11. Phases

| Phase | Build | Done when |
|---|---|---|
| **U0 Scaffold + auth** (about 1 weekend) | module, config, `login`/`logout`/`whoami`, keychain and file fallback, refresh with lock, CI job | `fplbud whoami` works on Windows and macOS, and a refresh after expiry succeeds without a new login |
| **U1 Read-only views** (about 1 weekend) | header, squad panel, saved plans from `/me` and `/me/agent/latest`, theme, help, resize, `--plain` | squad and plans match the web dashboard for the same account |
| **U2 Chat streaming** (1–2 weekends; needs harness H0) | SSE reader, reducer, transcript, composer, tool status, chips, cancel, `fplbud ask` | golden transcripts pass and a real turn streams end to end with citations |
| **U3 Threads and polish** (about 1 weekend) | thread list and history, feedback, memory confirm, usage badge, slash commands, all states in §7 | every state in §7 has a teatest snapshot |
| **U4 Release** | GoReleaser config, install notes, protocol-version check | a tagged build produces working binaries for Windows, macOS and Linux |

---

## 12. Open questions

| # | Question | Default | Why |
|---|---|---|---|
| Q1 | Distribution while the repo is private | GoReleaser binaries attached to GitHub Releases; `go install` only for you (needs `GOPRIVATE` and git auth) | private release assets need a token, so revisit if the TUI goes public |
| Q2 | Loopback ports | fixed list of three ports unless Supabase accepts a wildcard port **[verify]** | the redirect allow-list is the constraint |
| Q3 | Guest mode (`fplbud try <entryId>` via `GET /public/team/{id}` and `POST /suggestions`) | later, after U1 | cheap to add but outside the chat goal |
| Q4 | Hand-written or generated Go types from the schema | hand-written, held in check by contract tests | the event surface is small, and generated code adds a tool to maintain |
| Q5 | Bubble Tea v1 or v2 | v2 if it is stable at build time **[verify]** | avoid a migration right after launch |
| Q6 | Client telemetry | none; the server's `chat_turns.client` is enough | privacy, and no new infrastructure |
