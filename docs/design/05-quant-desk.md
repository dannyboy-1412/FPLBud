# FPLBud UI Design Spec 05: "Quant Desk"

> A dense, keyboard-first, trading-terminal direction. FPL is treated as a portfolio: players are positions, transfers are orders, the gain vs rolling is P&L, and the agent is a quant model publishing signals. Built for power users who want every number on one screen.

Source of truth for features and data: `docs/ARCHITECTURE.md` (§2A tiers, §6A agent, §7 endpoints, §8 pages). This document only defines **how it looks and behaves**.

---

## 1. Concept

| | |
|---|---|
| **Metaphor** | A quant trading desk. Multi-pane layout, an order ticket, a P&L readout, and model logs. |
| **Personality** | Precise, fast, unapologetically dense. Zero fluff and zero mascots. Respects the user's time and intelligence. |
| **Signature moves** | 1) **Pane-based layout** with 1px gutters (no cards, no margins between panes). 2) **Order tickets** for transfers (`SELL` / `BUY`). 3) **Command palette** (`⌘K` / `Ctrl K`) and single-key shortcuts for everything. 4) **Sparklines** of `projected_points_by_gw` everywhere. 5) **Model log** for agent progress. |
| **Avoid** | Bloomberg orange-on-black cliché, matrix green, purple, rounded "friendly" cards, illustrations, emoji, and big empty whitespace. |

Design principles:
1. **Density with order.** Many numbers, but on a strict baseline grid with consistent alignment (numbers right-aligned, labels left).
2. **Keyboard first, mouse friendly.** Every action has a shortcut that's shown in the UI.
3. **Signal colours mean one thing.** Teal = better, coral = worse, magenta = *you are here* (selection and focus), amber = attention. Nothing else is coloured.
4. **Model transparency.** Inputs (weights, data version, margins) are always visible in a status bar.

---

## 2. Colour

### 2.1 Core palette (dark-only in v1)

| Token | Hex | Use |
|---|---|---|
| `void` | `#0C0D0F` | Gutters between panes (1px "lines" are the void showing through) |
| `pane` | `#14161A` | Pane background |
| `pane-alt` | `#191C21` | Zebra rows, pane headers |
| `pane-raised` | `#20242A` | Popovers, command palette, hovered rows |
| `edge` | `#2A2F37` | Borders inside panes, input borders |
| `text` | `#D7DCE2` | Primary text |
| `text-dim` | `#8B94A0` | Secondary text, labels |
| `text-faint` | `#5A626D` | Tertiary, gridline labels, disabled |
| `select` | `#E0408A` | **Selection and focus only**: active tab, focused row, cursor, primary button |
| `select-bg` | `rgba(224,64,138,0.14)` | Selected row background |
| `up` | `#2EC4B6` | Positive delta, gain, available, play now |
| `up-bg` | `rgba(46,196,182,0.12)` | |
| `down` | `#FF6F59` | Negative delta, hits, out/injured, errors |
| `down-bg` | `rgba(255,111,89,0.12)` | |
| `amber` | `#F2B84B` | Attention: estimates, doubtful, expiring chip, deadline soon |
| `amber-bg` | `rgba(242,184,75,0.12)` | |
| `cool` | `#7AA2F7` | Neutral info: links, vice-captain, secondary series in charts |

### 2.2 Domain colours

**Positions** are a two-letter monospace code in `text-dim` inside a 1px `edge` box (`GK`, `DF`, `MF`, `FW`). There's no colour, by design. Position is a category, not a signal.

**FDR 1–5** is a **diverging heat cell** built from the signal colours. It's a 22×16 cell with the number printed:

| FDR | Background | Text |
|---|---|---|
| 1 | `#1F6F68` | `#E6FFFB` |
| 2 | `#1A4C49` | `#BFF3EE` |
| 3 | `#2A2F37` | `#D7DCE2` |
| 4 | `#5A2E28` | `#FFD9D2` |
| 5 | `#8A3426` | `#FFE8E3` |

The opponent code is uppercase for home and lowercase for away, plus a tooltip "(H)" or "(A)".

**Flags** are compact status cells in the player row:
- `75` amber text
- `50` / `25` amber on amber-bg
- `OUT` / `INJ` / `SUS` / `N/A` down on down-bg

### 2.3 Chart rules
- Sparklines: a 1.25px stroke in `text-dim`, with the last point dotted in `up` or `down` depending on the trend. The area fill is the stroke colour at 8%.
- Bars: `up` for positive and `down` for negative, with a zero baseline in `edge`.
- Gridlines: `edge` at 50%. Axis labels: `text-faint` 10px.
- No legends where a direct label works.

### 2.4 shadcn/ui variable mapping

```css
:root {
  --background: 220 11% 5%;       /* void */
  --foreground: 213 15% 86%;      /* text */
  --card: 220 13% 9%;             /* pane */
  --card-foreground: 213 15% 86%;
  --popover: 214 13% 15%;         /* pane-raised */
  --popover-foreground: 213 15% 86%;
  --primary: 331 72% 56%;         /* select */
  --primary-foreground: 0 0% 100%;
  --secondary: 216 14% 11%;       /* pane-alt */
  --secondary-foreground: 213 15% 86%;
  --muted: 216 14% 11%;
  --muted-foreground: 214 9% 59%; /* text-dim */
  --accent: 174 62% 47%;          /* up */
  --accent-foreground: 220 11% 5%;
  --destructive: 8 100% 67%;      /* down */
  --destructive-foreground: 220 11% 5%;
  --border: 216 13% 19%;          /* edge */
  --input: 216 13% 19%;
  --ring: 331 72% 56%;
  --radius: 3px;
}
```

---

## 3. Typography

| Role | Font (Google Fonts) | Notes |
|---|---|---|
| UI / labels | **Chivo** (400, 500, 700) | Compact grotesque for labels, headings and prose |
| Data | **JetBrains Mono** (400, 500, 700) | All numbers, codes, tables, logs, shortcuts |

The base font size is **13px** (dense). Root stays at 16px for accessibility; components use explicit sizes.

| Token | Size / LH | Font | Use |
|---|---|---|---|
| `title` | 18px / 24px | Chivo 700 | Page and pane titles (sparingly) |
| `pane-head` | 11px / 16px, UPPERCASE, tracking 0.1em | Chivo 700 | Pane header labels |
| `ui` | 13px / 20px | Chivo 400/500 | Controls, prose |
| `data` | 12.5px / 20px | JetBrains Mono 400 | Table cells, stats |
| `data-strong` | 12.5px / 20px | JetBrains Mono 700 | Key values |
| `pnl` | 32px / 36px | JetBrains Mono 700 | Gain vs roll readout |
| `kbd` | 10.5px / 14px | JetBrains Mono 500 | Shortcut hints |
| `prose` | 14px / 22px | Chivo 400 | Explanation, how-it-works |

Numbers are always right-aligned in tables and always signed for deltas (`+1.80`, `−0.05`). Projections use 1 decimal place, metric scores 2, and prices `£10.1m`.

Wordmark: `fplbud` in JetBrains Mono 700 lowercase, followed by a magenta block cursor `▌` that blinks only on the landing page.

---

## 4. Layout, spacing and shape

- **Pane system:** the app is a CSS grid of panes separated by **1px gutters** (the `void` background shows through `gap: 1px`). Panes have no radius, no shadow, and no outer margin. The app fills the viewport (`100dvh`) on desktop, and each pane scrolls internally.
- **Baseline:** 4px. Row height is 28px in tables (compact) or 36px (comfortable, a user setting).
- **Spacing:** 4, 8, 12, 16, 24. Pane inner padding is 12px.
- **Radius:** 3px for buttons, inputs, chips and the command palette. 0 for panes.
- **Borders:** 1px `edge` inside panes. The focused pane has a 1px `select` top border (2px on the header).
- **Elevation:** only the command palette, popovers and modals: `pane-raised` with a 1px `edge` border and `0 16px 48px rgba(0,0,0,0.5)`.
- **Breakpoints:**
  - `xl` (≥1280): full multi-pane desk.
  - `lg` (1024–1279): 2 columns, with the right column panes stacked.
  - `< lg`: a single column of collapsible panes with a bottom tab bar. The desk becomes a feed.

---

## 5. Iconography and imagery

- Icons: **Lucide is not allowed** (too default). Use **Remix Icon "line"** at 16px, `text-dim`.
- No images, crests or illustrations.
- Pitch: an abstract **formation matrix**. Rows are GK, DF, MF and FW, drawn as a compact 4-row grid inside a pane, with pitch lines as `edge` 1px strokes only. It fits in 320px height at `xl`.
- Shortcut hints render as `<kbd>`: a 1px `edge` border, `pane-alt` fill, `kbd` font.

---

## 6. Motion

Minimal and functional.
- Durations: 80ms (hover), 120ms (selection), 160ms (pane content swap).
- Easing: `linear` for value flashes, `cubic-bezier(0.2, 0, 0, 1)` for panels.
- **Value flash:** when a number changes (slider preview, new run), the cell background flashes `up-bg` or `down-bg` for 600ms, then fades. This is the main "motion" in the product.
- **Log lines** append with no animation, like a real terminal. Auto-scroll to the bottom.
- The command palette opens with a 120ms opacity change and a 4px drop.
- `prefers-reduced-motion`: value flashes become a static 1px outline for 600ms instead of a colour animation.

---

## 7. Components

### 7.1 Top bar ("Ticker")
- 36px tall `pane` with a 1px gutter below.
- Left: wordmark, then the **instrument line**: `GW07 · DL 17 OCT 21:00 AEDT · T−2d 14:06:31` in JetBrains Mono. The `T−` block turns amber under 24h and down-colour under 2h.
- Centre: a search box (`Search players, commands…` with `⌘K`), which opens the palette.
- Right: nav as text tabs (`Desk`, `Screener`, `Model`, `Docs`) with the active tab underlined in 2px magenta. Then the user chip (initials in a 20px square) or `Sign in`.
- **Ticker tape** (optional, `xl` only): a 24px strip below the top bar that scrolls flagged and news items for the user's squad and the top-owned players (`SAKA 75% knock · ISAK OUT hamstring…`). It pauses on hover and is static under reduced motion.

### 7.2 Command palette
- Opened with `⌘K` / `Ctrl K` or `/`. It's 640px wide, `pane-raised`, and shows an input with a result list grouped as `Players`, `Actions` and `Navigate`.
- Actions: `Re-run agent` (R), `Switch horizon 1/3/5` (1/3/5), `Edit overrides` (E), `Open settings` (,), `Toggle density` (D), `Sign out`.
- Player results show code, name, club, price and `proj`. Enter opens the player inspector.
- The selected result has a `select-bg` fill and a magenta left bar of 2px.

### 7.3 Team ID input (landing and onboarding)
- A compact terminal-style prompt: `entry_id >` label in `text-dim`, then a 44px input in JetBrains Mono 18px, with a magenta block cursor. Then `[Enter] Import`.
- Help (always visible, small): `find it in fantasy.premierleague.com/entry/`**`1234567`**`/event/6`, with the ID highlighted on amber-bg.
- 404: an inline log line `ERR 404 entry not found: check the number in your Points page URL` in down.

### 7.4 Formation matrix (pitch view)
- A pane titled `LINEUP · GW07 · 3-5-2`.
- Each row is a position band. Players are compact **position cells** (96×44):
  ```
  ┌────────────────┐
  │ SAKA  ARS   75 │   name · club · flag
  │ 6.4  ars▮4  ▁▃▅│   proj · next FDR · sparkline (next 5)
  └────────────────┘
  ```
- **Captain:** a `C` tag in a magenta square plus a magenta 1px border. **Vice:** a `V` tag in cool outline.
- **Transferred in:** an up-colour left bar of 2px and a `+IN` tag. Hovering shows who was sold.
- **Bench:** a fifth row `BENCH` separated by a dashed `edge` line, with cells prefixed `1`–`4`.
- Arrow keys move the cell focus. `Enter` opens the inspector.

### 7.5 Portfolio pane (context panel)
A key-value grid of two columns, labels left (`text-dim`) and values right (`data-strong`):

```
BANK            £1.4m  ~      FT            1  ~
TEAM VALUE    £101.2m          SELL VALUE  £99.8m ~
CHIPS     WC ●  FH ●  BB ●  TC ○        (half 1, until GW19)
DATA            v128           RUN         #a1f3 · 06:42
```
- `~` marks an estimate in amber. Its tooltip reads: *"Estimated. FPL doesn't expose this publicly. Press E to override."*
- Chips: `●` available (up), `○` used (text-faint), and amber `●` with `exp GW19` when ≤ 3 GWs remain.
- The **Flags** sub-table lists player, status cell, and `news` (truncated, full text on hover).
- A footer note in `text-faint`: `Transfers made for GW07 are hidden until the deadline. [E] edit squad`.

### 7.6 Horizon tabs
- Tabs in the plan pane header: `[1] NEXT GW`, `[3] NEXT 3`, `[5] NEXT 5`. The keys 1, 3 and 5 switch tabs.
- Each tab label is followed by its P&L in JetBrains Mono (`+2.1`, `+6.4`, `+9.0`) in up or down.
- Active: text colour with a 2px magenta underline. Inactive: text-dim.
- A **compare toggle** `[C] compare` splits the plan pane into three columns, one per horizon, showing their transfers, P&L, hits and captain side by side. This is a signature power-user feature of this direction.

### 7.7 Plan pane
Top to bottom:
1. **P&L readout:** `+6.4` in `pnl` up-colour, labelled `vs ROLL`. Next to it: `HITS 0 (−0.0)`, `NET +6.4`, `BANK AFTER £0.3m`, `MARGIN REQ +1.0 (N=3)`. Every hit decision shows its maths inline.
2. **Order ticket** (7.8).
3. **Captaincy row:** `CPT HAALAND 8.1 · VC PALMER 6.2 · Δ +1.9`.
4. **XI and bench** summary line: `XI 3-5-2 · BENCH ORDER RAMSDALE, GVARDIOL, WHARTON, MUÑOZ`.
5. **Projection chart:** for N=3/5, a small multi-bar chart of `projected_points_by_gw`, plan (up) vs roll (cool), per GW.
6. **Signals** (7.9) and **Model notes** (7.10).
7. **Alternatives table:** columns `PLAN`, `TRANSFERS`, `HITS`, `P&L`, `NET`, and a `VIEW` action. The selected row loads into the formation matrix.

### 7.8 Order ticket (transfers)
A compact table, one row per transfer:

| SIDE | PLAYER | POS | CLUB | PRICE | Δ£ | FORM | FIX | H/A | xGI | NEXT 5 |
|---|---|---|---|---|---|---|---|---|---|---|
| `SELL` (down) | Saka | MF | ARS | 10.1~ | | | | | | `▮4 ▮3 ▮2 ▮4 ▮3` |
| `BUY` (up) | Palmer | MF | CHE | 10.6 | +0.5 | +0.12 | +0.31 | −0.05 | +0.08 | `▮2 ▮2 ▮3 ▮1 ▮4` |

- Metric delta columns come straight from `metric_deltas`. They're signed and coloured, with a value flash on preview changes.
- `NEXT 5` holds FDR heat cells.
- If there are no transfers: one row `ROLL · FT carries to 2 next GW` in text-dim.
- Summary footer: `NET COST +£0.5m · FT USED 1/1 · HITS 0`.

### 7.9 Signals (chip tips)
A table titled `SIGNALS`:

| CHIP | SIGNAL | EV | THRESH | NOTE |
|---|---|---|---|---|
| BB | `PLAY NOW` (up-bg) | +13.2 | 12.0 | 2 bench DGW |
| TC | `GW09` (cool) | +10.4 | 10.0 | Haaland DGW |
| FH | `HOLD` (text-faint) | +4.1 | 12.0 | |
| WC | `HOLD` | +11.0 | 20.0 | `exp GW19` amber |

Expiring chips (`stop_event` ≤ 3 GWs away) get an amber `EXP` tag in the NOTE column.

### 7.10 Model notes (explanation)
- A pane section titled `MODEL NOTES` with a source tag on the right: `src: template` (or in the future `src: llm`).
- Prose in Chivo 14px/22px, max 72ch, in `text`. Player names are in `text` 500, and numbers are wrapped in JetBrains Mono.
- `reason_codes` render as monospace tags in `edge` boxes, with plain-English tooltips: `FLAG_INJURED_OUT`, `FIXTURE_SWING`, `XGI_UPGRADE`, `HIT_NOT_WORTH`.

### 7.11 Agent progress ("Model log")
A pane that replaces the plan pane while a run is queued or running:

```
MODEL RUN #a1f3 · trigger=import · data v128           [■■■■■■■■■□□□□□]  62%
06:42:01.204  queued
06:42:01.511  running   stage=context     snapshot ok · 15 picks · FT 1~ · bank £1.4m~
06:42:01.902  running   stage=horizon_1   solved · best +2.1 · roll +0.0
06:42:02.377  running   stage=horizon_3   solving…▌
```
- A new line is printed each time a poll returns a new `stage`. The client timestamp is shown. Detail text is optional and filled from whatever the poll response provides; if nothing is available, print only the stage.
- The progress bar is a 6px track in `edge` with a magenta fill bound to `progress`.
- **Succeeded:** print `succeeded · 3 plans` in up and swap to the plan pane after 400ms.
- **Failed:** print `failed · <error>` in down, followed by `[R] retry`.
- **Polling timeout (2 minutes):** print `poll timeout · run continues server-side · [F5] refresh` in amber.

### 7.12 "Plans updated" notice
- A 28px strip at the top of the plan pane with an amber left bar and the text: `NEW RUN #b7c2 · trigger=pre_deadline (injury news) · P&L +6.4 → +7.9 · [U] load`.
- Showing the before/after P&L is a requirement for this direction.

### 7.13 Weight sliders ("Model parameters")
- A table-like form: `PARAM`, `WEIGHT`, `SHARE`, `SLIDER`, `DESC`.
- Weight values are editable inline numeric inputs (step 0.05, arrow keys nudge it, Shift+arrow nudges by 0.25).
- Slider: a 4px `edge` track with a magenta fill and a 12px square magenta thumb.
- `SHARE` shows the renormalised percentage, which updates live.
- Optional params sit below a dashed divider with checkboxes (`[x]` style, JetBrains Mono). Checking one sets 0.15 and flashes the row.
- A footer **diff bar**: `PREVIEW vs SAVED · N=1 +0.3 · N=3 +0.4 · N=5 −0.1` (from debounced `POST /suggestions` at horizons 1/3/5 for signed-in users), then `[Ctrl+S] save & re-run` and `[Esc] revert`.
- **Guest:** the table renders with values but inputs are disabled. An inline row at the top reads `READ-ONLY · default parameters · Sign in with Google to edit` with a button.

### 7.14 Locked horizon state (guest `/try`)
- Tabs `[3]` and `[5]` show a lock icon instead of the P&L.
- The pane renders the order ticket skeleton with values blurred (`filter: blur(5px)`), with row structure and headers left visible so users see what they'd get.
- Overlay box centred (`pane-raised`, 1px edge): `RESTRICTED · multi-GW plans`, then *"Sign in with Google to unlock your 5-week plan."* and `[Enter] Sign in with Google`.

### 7.15 Buttons and inputs
| Variant | Style |
|---|---|
| Primary | Magenta fill, white text, Chivo 500 13px, 28px tall (32px comfortable), 3px radius, with a trailing `<kbd>` hint. |
| Secondary | `pane-alt` fill, `edge` border, text colour. |
| Ghost | text-dim. Hover: text plus `pane-alt`. |
| Destructive | down text plus down border. Hover: down-bg. |
| Google | White fill, `#1F1F1F` text, official Google "G", 36px. It's the one deliberately larger button, for brand compliance. |

Inputs: 28px, `pane-alt` fill, 1px edge border. Focus: 1px magenta border plus a 3px `select-bg` ring.
Minimum touch target on `< lg` layouts is 44px. Compact sizes are for pointer devices only (`@media (pointer: fine)`).

### 7.16 Screener (player explorer table)
- Full-pane virtualised table, with a sticky header in `pane-alt` and `pane-head` labels.
- Columns (all sortable, all resizable): `#`, `PLAYER`, `POS`, `CLUB`, `£`, `PROJ`, `FORM`, `FIX`, `H/A`, `xGI`, `VAL`*, `MIN`*, `TRD`* (* = only when the optional metric is enabled), `OWN%`, `NEXT 6` (heat cells) and `SPARK` (projection sparkline).
- Keyboard: `j`/`k` move rows, `Enter` opens the inspector, `/` focuses the filter, and `s` cycles the sort column.
- A filter row above uses chips: `POS:MF`, `CLUB:ARS`, `£≤8.0`, `H=3`. Click a chip to edit it, or `Backspace` to remove the last chip.
- **Inspector** (right pane, 480px, or a full-screen sheet on mobile): header (name, club, pos, price, flag, news), then a **metric × GW matrix** (rows = metrics, columns = GW+1…+6, heat cells from `pane` to `up` by score 0→1, with values printed), then recent match history as a table.

### 7.17 Status bar
- A 24px bottom bar across the whole app in `pane-alt`, JetBrains Mono 11px, `text-faint`.
- Content: `DATA v128 · ingest 06:10 · weights F.30 X.25 H.10 G.35 · max hits 1 · API ok 84ms` plus `? shortcuts` at the right.
- `?` opens a shortcuts cheat-sheet modal.

### 7.18 Feedback
- Toasts are not used. Messages go to the status bar's left area for 5s (with `aria-live`), and errors also go to the model log when relevant.
- Skeletons: rows of `pane-alt` bars matching the real column widths. They don't shimmer.
- 429: status bar message in amber, `RATE LIMITED · retry in 60s`, with a countdown.

---

## 8. Pages

### 8.1 `/` Landing
The landing is the one "non-desk" page, but it stays in the same language:
- A centred column (720px) on `void`.
- Wordmark with the blinking cursor, then the headline (Chivo 700, 40px): **"Your FPL team, run like a portfolio."** The sub (Chivo 16px text-dim) reads: *"Transfers, captaincy and chips from a deterministic model. Sub-second, with every number shown."*
- The Team ID prompt (7.3).
- `or [G] Sign in with Google: saved team, 3- and 5-GW plans, custom parameters`.
- Below: a **static demo desk screenshot** rendered as live components with sample data in a 1px-guttered frame, showing the order ticket, P&L and signals.
- A comparison table, Guest vs Signed in, as a compact pane table.

### 8.2 `/try/[entryId]`
- The desk layout at reduced capability:
  ```
  ┌ Ticker ─────────────────────────────────────────────────────────┐
  ├ LINEUP (formation matrix) ───┬ PLAN [1] [3🔒] [5🔒] ─────────────┤
  ├ PORTFOLIO ───────────────────┤ P&L · order ticket · captaincy   │
  │                              │ model notes                       │
  ├ PARAMETERS (read-only) ──────┴───────────────────────────────────┤
  └ Status bar ─────────────────────────────────────────────────────┘
  ```
- The title in the pane header is `PREVIEW · <TEAM NAME> · <MANAGER>`.

### 8.3 `/login`
A centred 400px pane: `fplbud▌`, the title `Sign in`, the Google button, and a note in text-dim: *"Google sign-in only stores your team ID. FPL credentials are never requested."*

### 8.4 `/auth/callback`
A single log line, centred: `auth · exchanging code…▌`.

### 8.5 `/onboarding`
- A centred pane with `SETUP 1/1 · ENTRY ID` and the prompt (7.3).
- On lookup, a key-value preview appears: `TEAM`, `MANAGER`, `OVERALL RANK`, `GW POINTS`, `CURRENT GW`. Then `[Enter] Confirm` (primary) and `[Esc] Change` (ghost).
- Confirm, then go to `/dashboard`, where the Model log is active.

### 8.6 `/dashboard` ("Desk")
At `xl`:
```
┌ Ticker (+ ticker tape) ────────────────────────────────────────────────┐
├ LINEUP · GW07 · 3-5-2 ─────────┬ PLAN  [1] [3] [5]  [C] compare  [R] ──┤
│ formation matrix + bench       │ (Plans updated notice)                  │
│                                │ P&L readout                             │
├ PORTFOLIO ─────────────────────┤ Order ticket                            │
│ bank, FT, value, chips, flags  │ Captaincy · XI/bench line               │
│                                │ Projection chart (N=3/5)                │
├ PARAMETERS (collapsed summary) ┤ Signals · Model notes · Alternatives    │
└────────────────────────────────┴─────────────────────────────────────────┘
└ Status bar ────────────────────────────────────────────────────────────┘
```
- Column widths: left 40%, right 60%. The splitter between them is draggable and the width persists in `localStorage`.
- While running, the PLAN pane shows the Model log (7.11). LINEUP shows the current squad.
- The formation matrix reflects the selected horizon's plan or alternative.
- `< lg`: a bottom tab bar with `Plan`, `Lineup`, `Portfolio` and `Params`. The Plan tab opens by default, and horizon tabs are sticky.

### 8.7 `/settings` ("Model")
A two-pane layout: section list on the left (`PARAMETERS`, `DEFAULTS`, `ENTRY`, `DISPLAY`, `ACCOUNT`), content on the right.
- **Parameters:** 7.13.
- **Defaults:** default horizon (radio `1 / 3 / 5` in JetBrains Mono) and max hits (a numeric input 0–3 with stepper).
- **Entry:** the current entry ID and team name, plus `Change entry`.
- **Display:** density (compact or comfortable), ticker tape on/off, and timezone for the deadline (default: browser).
- **Account:** sign out, plus delete in a down-bordered block. The confirmation modal requires typing `DELETE` and lists exactly what is removed (profile, saved team, snapshots, runs, plans).

### 8.8 `/players` ("Screener")
The full-viewport screener (7.16) with the inspector pane on the right. The header shows `RANKED BY: your parameters` or `RANKED BY: default parameters · sign in to customise`.

### 8.9 `/how-it-works` ("Docs")
- A two-column docs layout: a TOC pane on the left, content on the right (max 760px).
- Formulas in JetBrains Mono blocks on `pane-alt`, with the variables explained in a small table under each.
- Horizon rules, hit margins and chip thresholds rendered as the same compact tables used in the app, so the docs and the UI match.

### 8.10 Error and empty states
- 404: a log-style page, `ERR 404 route not found · [H] home`.
- API down: the status bar shows `API unreachable` in down. The affected panes show `NO DATA · retrying in 10s · [R] retry now`.
- No plans yet: the PLAN pane shows `NO RUNS · [R] run agent`.

---

## 9. Accessibility
- Density is a preference: the **comfortable** mode (36px rows, 14px data) must be available and honoured on touch devices automatically.
- **Verify contrast** for `text-dim` and `text-faint` on `pane` and `pane-alt`, and for the up and down text colours. Target WCAG AA. `text-faint` is only for non-essential metadata.
- Colour is never the only signal: deltas are signed, FDR prints numbers, chips use filled/empty glyphs, and flags show text.
- All single-key shortcuts are disabled while focus is in a text input. Provide a setting to turn off single-key shortcuts entirely (WCAG 2.1.4). Every shortcut has a visible button equivalent.
- Tables use proper `<table>` semantics with `aria-sort`. The virtualised screener keeps `aria-rowcount` and `aria-rowindex`.
- The model log uses `role="log"` with `aria-live="polite"`.

## 10. Implementation notes
- Fonts with `next/font/google`: `Chivo`, `JetBrains_Mono`.
- Tailwind theme colours: `void`, `pane`, `pane-alt`, `pane-raised`, `edge`, `text`, `text-dim`, `text-faint`, `select`, `up`, `down`, `amber`, `cool`, `fdr-{1..5}`.
- Pane layout: a root CSS grid with `gap: 1px; background: var(--void)`, where every child pane sets `background: var(--pane)`.
- Shortcuts: one central `useHotkeys` registry so the cheat-sheet modal is generated from the same source.
- Value flash: a `<Num value={n} signed decimals={1} />` component that keeps the previous value and applies the flash class when it changes.
- Sparklines: a tiny inline SVG component with no chart library. Larger charts can use a lightweight lib (e.g. visx), themed with these tokens.
- Replace shadcn's default Lucide icons with Remix Icon in all overridden primitives.
