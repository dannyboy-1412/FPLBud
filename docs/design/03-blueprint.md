# FPLBud UI Design Spec 03: "Blueprint"

> A technical-drawing direction. Every plan is an engineering drawing of your squad: cyanotype blue paper, white line work, a measured grid, dimension lines for point gains, and a coach's orange marker scribbling the transfers on top.

Source of truth for features and data: `docs/ARCHITECTURE.md` (§2A tiers, §6A agent, §7 endpoints, §8 pages). This document only defines **how it looks and behaves**.

---

## 1. Concept

| | |
|---|---|
| **Metaphor** | An architect's blueprint crossed with a manager's tactics board. The maths is precise (drawn in ink), and the agent's call is marked up by hand in orange marker. |
| **Personality** | Precise, nerdy in a good way, transparent about the numbers. It celebrates the deterministic maths (§6A). |
| **Signature moves** | 1) A **measured grid background** (8px minor and 40px major lines). 2) A **title block** in the corner of each plan, showing revision = agent run and data version. 3) **Dimension lines** (`|←── +6.4 ──→|`) to show gains. 4) **Marker annotations** with hand-drawn arrows from OUT to IN players on the pitch. |
| **Avoid** | Generic "SaaS blue" (`#3B82F6`-style), soft shadows, rounded bubbly cards, gradients, emoji, photography. |

Design principles:
1. **Show the working.** Numbers, formulas and margins are first-class UI, not hidden in tooltips.
2. **Two voices.** The *drawing* (white line, mono type) is the data. The *marker* (orange, handwritten) is the recommendation. Don't mix them.
3. **Everything aligns to the grid.** Components snap to 8px. Major blocks align to 40px.
4. **Revisions, not refreshes.** Each agent run is a numbered revision of the drawing.

---

## 2. Colour

### 2.1 Core palette ("Cyanotype" is the default theme)

| Token | Hex | Use |
|---|---|---|
| `prussian` | `#123A6B` | Page background (cyanotype paper) |
| `prussian-deep` | `#0C2C54` | Insets, wells, table header |
| `prussian-lift` | `#1A4A85` | Raised panels, hover |
| `grid-minor` | `rgba(241,244,238,0.06)` | 8px grid lines |
| `grid-major` | `rgba(241,244,238,0.12)` | 40px grid lines |
| `linework` | `#F1F4EE` | Primary text, outlines, pitch lines |
| `linework-dim` | `#B7C6DA` | Secondary text |
| `linework-faint` | `#7F97B8` | Captions, placeholders, disabled |
| `marker` | `#FF6A1F` | Primary accent: recommendation, captain, CTA, transfer arrows |
| `marker-deep` | `#D9520D` | Pressed/hover |
| `highlighter` | `#FFD23F` | Highlights: estimates, warnings, expiring chips |
| `gain` | `#7CE0C3` | Positive values (mint) |
| `loss` | `#FF8FA3` | Negative values, hits, injuries (rose) |

### 2.2 Light theme ("Whiteprint")
Offered as a toggle and useful for printing or sharing:

| Token | Hex |
|---|---|
| `prussian` (bg) | `#F3F1EA` |
| `prussian-deep` | `#E7E4D9` |
| `prussian-lift` | `#FFFFFF` |
| `grid-minor` | `rgba(18,58,107,0.06)` |
| `grid-major` | `rgba(18,58,107,0.12)` |
| `linework` (text) | `#123A6B` |
| `linework-dim` | `#3E5F8A` |
| `linework-faint` | `#7F8FA6` |
| `marker` | `#E2540E` |
| `highlighter` | `#F5C000` (fills only, never text) |
| `gain` | `#13795B` |
| `loss` | `#B4233F` |

### 2.3 Domain colours

**Positions** are shown as an outline-shape **glyph**, not colour. Shape is the primary signal and colour is secondary:

| Position | Glyph | Colour |
|---|---|---|
| GKP | ◇ diamond | `#FFD23F` |
| DEF | □ square | `#7CE0C3` |
| MID | ○ circle | `#F1F4EE` |
| FWD | △ triangle | `#FF6A1F` |

**FDR 1–5** uses a **hatch-density** scale, drawn with SVG patterns inside a 28×18 swatch with a 1px linework border:

| FDR | Pattern |
|---|---|
| 1 | empty |
| 2 | sparse diagonal hatch (6px spacing) |
| 3 | diagonal hatch (4px) |
| 4 | cross-hatch (4px) |
| 5 | solid `linework` fill, with the number in `prussian` |

The FDR number always prints inside or next to the swatch. Home = opponent code with an underline. Away = no underline. The legend lives in the title block.

**Flags** look like engineering **revision clouds**: a scalloped outline around the player token.
- 75%: highlighter cloud plus `75`
- 50% / 25%: highlighter cloud, dashed, plus `50` / `25`
- out/injured/suspended/unavailable: loss cloud plus `OUT` / `INJ` / `SUS` / `N/A`

### 2.4 shadcn/ui variable mapping (Cyanotype)

```css
:root {
  --background: 213 71% 25%;      /* prussian */
  --foreground: 90 18% 94%;       /* linework */
  --card: 213 71% 25%;            /* cards are outlined, not filled */
  --card-foreground: 90 18% 94%;
  --popover: 213 75% 19%;         /* prussian-deep */
  --popover-foreground: 90 18% 94%;
  --primary: 21 100% 56%;         /* marker */
  --primary-foreground: 213 75% 12%;
  --secondary: 213 67% 31%;       /* prussian-lift */
  --secondary-foreground: 90 18% 94%;
  --muted: 213 75% 19%;
  --muted-foreground: 214 34% 79%;/* linework-dim */
  --accent: 162 63% 68%;          /* gain */
  --accent-foreground: 213 75% 12%;
  --destructive: 350 100% 78%;    /* loss */
  --destructive-foreground: 213 75% 12%;
  --border: 90 18% 94% / 0.35;
  --input: 90 18% 94% / 0.5;
  --ring: 21 100% 56%;
  --radius: 0px;
}
```

---

## 3. Typography

| Role | Font (Google Fonts) | Notes |
|---|---|---|
| Labels / headings | **IBM Plex Sans Condensed** (500, 600, 700) | Uppercase drawing labels, headings |
| Body / UI | **IBM Plex Sans** (400, 500) | Prose, controls |
| Data | **IBM Plex Mono** (400, 500, 600) | All numbers, IDs, formulas, table cells |
| Marker (annotations) | **Kalam** (400, 700) | Only for the agent's recommendation annotations, short phrases of ≤ 8 words |

| Token | Size / LH | Font | Use |
|---|---|---|---|
| `title` | 2.5 / 1.05, UPPERCASE, tracking 0.04em | Plex Sans Condensed 700 | Page titles |
| `h2` | 1.25 / 1.2, UPPERCASE, tracking 0.08em | Plex Sans Condensed 600 | Section headings |
| `label` | 0.6875 / 1, UPPERCASE, tracking 0.18em | Plex Sans Condensed 600 | Field labels, title-block keys |
| `body` | 0.9375 / 1.6 | Plex Sans 400 | Prose |
| `data` | 0.875 / 1.3 | Plex Mono 400 | Tables, stats |
| `data-xl` | 2.75 / 1 | Plex Mono 600 | Gain vs roll |
| `marker-lg` | 1.75 / 1.1, rotate −2° | Kalam 700 | Headline annotations ("Sell Saka → Palmer") |
| `marker` | 1.125 / 1.2 | Kalam 400 | Inline annotations ("hit not worth it") |

Wordmark: `FPLBUD` in Plex Sans Condensed 700, letter-spaced 0.12em, inside a 1px linework rectangle, with `REV.1` in Plex Mono 10px at the bottom-right, like a drawing number.

---

## 4. Layout, spacing and shape

- **Grid background:** two layered `linear-gradient` backgrounds on `body` for the 8px minor and 40px major lines. It's static and stays fixed when scrolling (`background-attachment: fixed`).
- **Layout grid:** 12 columns, max width 1280px, 24px gutters. Block edges align to the 40px major lines where practical.
- **Spacing:** multiples of 8 only: 8, 16, 24, 32, 40, 48, 64, 80.
- **Radius: 0.** Everything is square. The only exceptions are circles for the MID glyph, the captain mark and avatars.
- **Borders:** 1px linework at 35% for panels. 1px at 100% for focused or active panels. A **double-line border** (1px, 2px gap, 1px) for the recommended plan.
- **Corner ticks:** panels show 8px "crop marks" at each corner (an L-shape at 100% linework) instead of a full border when they are *read-only* data blocks.
- **Elevation:** none. Popovers = `prussian-deep` fill with a 1px linework border. Modals = the same plus a full-screen `prussian` 80% scrim with the grid showing through.
- **Breakpoints:** 640 / 768 / 1024 / 1280.

---

## 5. Iconography and imagery

- Icons: **Iconoir**, 1.5px stroke, 20px, linework colour.
- Annotations: hand-drawn SVG arrows, circles and underlines in `marker`, 2.5px stroke, round caps, with slight wobble. Keep a small library of 4 to 6 pre-drawn paths per shape and pick one deterministically from the player ID, so it's stable across renders.
- Player tokens: the position glyph (32px outline, 1.5px stroke) with the club code in Plex Mono inside it.
- Pitch: drawn as a technical plan with dimension lines along the sides (`105 m`, `68 m` in label style). That's decoration only and is hidden on mobile.

---

## 6. Motion

- Durations: 100ms (hover), 200ms (tabs), 450ms ("pen draw").
- Easing: `cubic-bezier(0.65, 0, 0.35, 1)` (ease-in-out-cubic).
- **Pen draw:** annotations and transfer arrows animate in with `stroke-dashoffset` from full length to 0 over 450ms, after the data has rendered. The handwriting text fades in at the end.
- **Plot:** bar charts draw bottom to top over 300ms.
- Tab change: the drawing cross-fades in 200ms and the annotations redraw.
- `prefers-reduced-motion`: annotations appear instantly with no draw.

---

## 7. Components

### 7.1 Header ("Drawing border")
- 56px tall with a 1px linework bottom border. Left: wordmark. Nav in `label` style, where the active item is wrapped in a 1px linework box.
- Right: the **deadline readout** `GW07 DEADLINE  T−2D 14:06` in Plex Mono, with the `T−` in marker when under 24h. Then the avatar (a square 28px with a 1px border) or `SIGN IN`.

### 7.2 Team ID input
- Label `ENTRY ID` with a 1px-bordered field, 56px tall, in Plex Mono 1.5rem. The field has **tick marks** under it every 8px, like a ruler.
- Inline button `IMPORT →` on a marker fill.
- Help: an annotated diagram of the FPL URL in Plex Mono, `fantasy.premierleague.com/entry/1234567/event/6`. A marker circle is drawn around `1234567` with the handwritten note *"this number"*.
- 404: the field border becomes loss and the note reads *"No entry with that ID. Check the URL on your Points page."* The marker note changes to *"not found?"*.

### 7.3 Pitch view ("Plan view")
- The pitch is outlined in linework at 1.5px with no fill on the grid. Use standard markings, plus a centre-line label `HALFWAY` in label style.
- Tokens are positioned by formation. Under each glyph: surname (Plex Sans 500, 12px), then `6.4` (Plex Mono 500) and the FDR swatch.
- **Captain:** a marker circle hand-drawn around the token (pen-draw animation) with a handwritten `C`. **Vice:** a dashed linework circle with `V` in Plex Mono.
- **Transfers on the pitch:** the outgoing player's ghost (25% opacity, struck through) sits in the slot, with the incoming player drawn on top and a marker arrow from a small OUT label to the token. A Kalam annotation `+1.8 over 3 GWs` sits beside it.
- **Bench:** a row below the pitch labelled `RESERVES` with order numbers `R1`–`R4` in Plex Mono.
- **Formation** label at the bottom-left of the pitch: `FORMATION 3-5-2`.

### 7.4 Title block (context panel)
Placed at the bottom-right of the dashboard drawing, in the style of an engineering title block (a grid of cells with 1px borders):

```
┌───────────────┬───────────────┬───────────────┐
│ PROJECT       │ ENTRY         │ GAMEWEEK      │
│ Danny's XI    │ 1234567       │ 07            │
├───────────────┼───────────────┼───────────────┤
│ BANK          │ FREE TRANSF.  │ VALUE         │
│ £1.4m ▲EST    │ 1 ▲EST        │ £101.2m       │
├───────────────┴───────────────┼───────────────┤
│ CHIPS  WC ✓  FH ✓  BB ✓  TC ✕ │ REV   R12     │
│ (first half, until GW19)      │ DATA  v128    │
├───────────────────────────────┴───────────────┤
│ NOTES  Transfers made for GW07 are hidden by   │
│ FPL until the deadline. Edit if needed. [EDIT] │
└────────────────────────────────────────────────┘
```
- Keys use `label` style and values use `data`.
- `▲EST` is a small highlighter-filled triangle tag. Its tooltip reads: *"Estimated. FPL doesn't publish this. Edit to override."*
- `REV` = a sequence number of successful agent runs for this user (display-only; derive from run history or show the short run ID). `DATA` = `data_version`.
- The flags list sits in a separate block above the title block: `FLAGGED` with each player's glyph, a revision cloud, and the news text.

### 7.5 Horizon tabs ("Sheets")
- Look like drawing sheet tabs: `SHEET 1 · NEXT GW`, `SHEET 2 · NEXT 3`, `SHEET 3 · NEXT 5`.
- Each tab is a square 1px-bordered cell. The active tab has its bottom border removed so it joins the panel below (a physical tab feel), and a 3px marker bar on top.
- Each tab shows `+6.4` in Plex Mono 12px under its label.

### 7.6 Plan panel
1. The **marker headline** at the top-left (`marker-lg`, rotated −2°): *"Sell Saka → buy Palmer"* or *"Roll it."*
2. A **dimension line** for gain vs roll:
   ```
   ROLL ├────────────────── +6.4 ──────────────────┤ PLAN
   ```
   The line length is proportional to the gain relative to the largest gain among the three horizons (min 120px). It's drawn in linework with the value in `data-xl` gain colour, centred.
3. The **hit maths** block in Plex Mono, set like a calculation:
   ```
   GAIN (2 transfers)      +9.1
   HIT  (1 × −4)           −4.0
   MARGIN REQUIRED (N=3)   +1.0
   ─────────────────────────────
   NET vs ROLL             +5.1  ✓ worth it
   ```
   The `✓ worth it` or `✕ not worth it` is a Kalam annotation in marker.
4. Transfer rows (7.7).
5. Captain and vice row, with the margin shown as a small dimension line.
6. The explanation (7.8).
7. Chip specs (7.9).
8. `ALTERNATIVES` table: rows for roll and the one-fewer-transfer plan, with columns transfers, hits, gain, and `VIEW`.

The recommended plan's panel gets the double border and a marker stamp `APPROVED` (Kalam 700, marker, inside a hand-drawn rectangle, rotated 4°).

### 7.7 Transfer row
A table row with 1px separators:

| Col | Content |
|---|---|
| OUT | glyph, name (struck through), club, `£10.1m` with the `▲EST` tag |
| → | a marker arrow |
| IN | glyph, name, club, `£10.6m` |
| Δ£ | `+0.5` in Plex Mono |
| WHY | a mini **stacked delta chart**: one 8px-tall bar per metric, width ∝ |delta|, gain/loss colour, with labels on hover. A text fallback is always shown below at `sm`. |

For N=3/5, an expandable sub-row shows `projected_points_by_gw` as a small **column chart** on the grid (each bar is 8px wide on the 8px grid, with the GW label below).

### 7.8 Explanation ("Notes")
- A block with corner ticks and the label `ENGINEER'S NOTES`.
- Plex Sans body at 0.9375rem, max 68ch. Player names are underlined with a 1px marker line.
- `reason_codes` print as Plex Mono tags in square brackets after the notes: `[FIXTURE_SWING] [XGI_UPGRADE]`. Give them human-readable tooltips.

### 7.9 Chip spec
A small spec card with corner ticks:
- `play_now`: a marker border and a Kalam annotation *"play it now!"*, with `CHIP: BENCH BOOST · EXPECTED +13.2 · THRESHOLD 12.0`.
- `consider_gw_X`: a linework border, `CONSIDER GW09`.
- `hold`: linework-faint, one line.
- Expiring: a highlighter tab on the card's top edge, `EXPIRES GW19`.
- Showing the threshold beside the expected value is a requirement for this direction, because it shows the working.

### 7.10 Agent progress ("Drafting")
- A **technical checklist** in Plex Mono, with each line printed as if it were being plotted:
  ```
  [■■■■■■■■■■■■■■■■□□□□□□□□]  62%
  01  CONTEXT      read team sheet         ✓  0.2s
  02  HORIZON_1    solve N=1               ✓  0.4s
  03  HORIZON_3    solve N=3               ▸  ...
  04  HORIZON_5    solve N=5               ·
  05  CHIPS        check WC/FH/BB/TC       ·
  06  EXPLAIN      write notes             ·
  ```
- Stage codes match the API `stage` values exactly. The friendly label is shown next to each.
- The current line has a blinking block cursor `▸` (1s blink, disabled under reduced motion).
- Elapsed times per stage are optional. Show them only if derivable client-side (time between polls when the stage changed).
- **Failed:** the line ends with `✕ FAILED` in loss and the `error` text is printed below it, indented. Add a `RETRY` button.
- **Slow (over 2 minutes):** print `NOTE: taking longer than expected. Results will appear when ready.`

### 7.11 "Plans updated" banner ("Revision notice")
- A highlighter-filled strip with `prussian` text in Plex Mono: `REVISION R13 ISSUED · reason: injury news (pre-deadline) · [VIEW R13]`. Dismissible.

### 7.12 Weight sliders ("Specification")
- Each row: label in Plex Sans Condensed 600, the formula shown inline in Plex Mono 12px `linework-faint` (e.g. `0.5×form + 0.5×EWMA(pts, 5)`), the slider, the raw weight `0.30`, and the **normalised share** `30%`.
- Slider: a 1px linework track with **ruler ticks** every 0.05 (minor) and 0.25 (major). The thumb is a 16px square with a marker outline, and a value tooltip above it while dragging.
- Above the sliders is a **normalisation equation** that updates live: `S = (0.30·form + 0.25·fixture + 0.10·home + 0.35·xGI) / 1.00`.
- Optional metrics live in a section `OPTIONAL COMPONENTS` with checkboxes (square, 1px border, marker check). Checking one sets the weight to 0.15.
- Live preview: `PREVIEW Δ vs saved: +0.4` next to `SAVE REVISION`.
- **Guest:** sliders are drawn but locked. A diagonal hatch overlay sits on the panel with the stamp `SIGN IN TO EDIT SPEC` and a Google button.

### 7.13 Locked horizon overlay (guest `/try`)
- Sheets 2 and 3 show a padlock glyph.
- The panel renders a placeholder plan with `filter: blur(6px)` and a **diagonal hatch overlay** (linework at 15%).
- Centred card with a double border: label `RESTRICTED SHEET`, h2 `5-WEEK PLAN`, body *"Sign in with Google to unlock your 5-week plan."*, and a primary button.

### 7.14 Buttons
| Variant | Style |
|---|---|
| Primary | Marker fill, `#0C2C54` text, Plex Sans Condensed 600 uppercase, tracking 0.08em, 44px, square corners. Hover: marker-deep. |
| Secondary | Transparent, 1px linework border, linework text. Hover: `prussian-lift`. |
| Ghost | Linework-dim text. Hover: underline. |
| Destructive | 1px loss border with loss text. Hover: loss fill with prussian text. |
| Google | White fill, `#1F1F1F` text, official Google "G". Follow Google branding (square corners are allowed). |

Focus: 2px marker outline plus a 2px offset. Inputs also show a 1px marker inner border.

### 7.15 Player explorer ("Schedule")
- A dense table on `prussian-deep`, with a header in label style and rows 40px tall separated by 1px linework at 15%.
- Columns: `#`, glyph, name, club, `£`, `PROJ`, the score for each metric as a 0–1 value in Plex Mono with a 40px track bar beneath, and the next 5 FDR hatch swatches.
- The sort indicator is a small marker triangle.
- Drawer (right, 560px): a player "detail drawing" with a metric × GW matrix where cells hold numbers plus hatch density, and match history in a Plex Mono table.

### 7.16 Feedback
- Toasts: bottom-right, `prussian-deep` with a 1px linework border and a left marker bar for success or info (loss bar for errors).
- Skeletons: outlined boxes with dashed linework borders and a `PLOTTING…` label. They don't shimmer.
- 429: *"Rate limit reached. Try again in a minute."*

---

## 8. Pages

### 8.1 `/` Landing
- The hero is a full-width drawing: a large pitch plan view in linework with three sample tokens and marker annotations already drawn (pen-draw on load).
- Overlaid title block at the bottom-right with the `title` text **"FPL, DRAWN TO SCALE."** and the sub *"Import your team and get transfers, captain and chips, with all the working shown."*
- Below: the Team ID input with the annotated URL help, plus `SIGN IN WITH GOOGLE` (secondary) and the note *"for 3- and 5-week plans and your own weights"*.
- Section: "THE METHOD": three spec cards (Ingest → Score → Optimise), each with a tiny formula.

### 8.2 `/try/[entryId]`
- Title `PREVIEW: <TEAM NAME>`. Layout: the pitch (cols 1–8) and the title block plus flags (cols 9–12).
- Sheets: Sheet 1 open, Sheets 2 and 3 restricted (7.13).
- Specification panel in its locked state.

### 8.3 `/login`
A centred 480px panel with a double border and the label `ACCESS`. The h2 reads `SIGN IN TO SAVE YOUR DRAWINGS`, then the Google button and the note *"We only store your team ID. Never your FPL password."*

### 8.4 `/auth/callback`
Centred Plex Mono `AUTHENTICATING ▸` with the blinking cursor.

### 8.5 `/onboarding`
- `title` `NEW PROJECT`, with step label `01 / 01 · ENTRY ID`.
- After lookup, a **confirmation title block** shows team name, manager, overall rank and GW points, with `CONFIRM` (primary) and `CHANGE` (ghost).

### 8.6 `/dashboard`
```
Header
[Revision notice]
┌ title: <TEAM NAME> · label GW07 ─────────────── [RE-RUN AGENT] ┐
│ Sheets: SHEET 1 · NEXT GW | SHEET 2 · NEXT 3 | SHEET 3 · NEXT 5 │
├──────────── cols 1–7 ──────────────┬──────── cols 8–12 ─────────┤
│ Plan view (pitch + annotations)    │ Marker headline            │
│ Reserves                           │ Dimension line + hit maths │
│                                    │ Transfers                  │
│ Flagged block                      │ Captain/vice               │
│ Title block                        │ Notes · Chip specs         │
│                                    │ Alternatives               │
└────────────────────────────────────┴────────────────────────────┘
```
- While running: the right column shows Drafting (7.10). The pitch shows the current squad without annotations.
- Mobile: sheets become a sticky 3-up row. Order: marker headline, dimension line, pitch, transfers, hit maths, notes, chips, alternatives, flags, title block.

### 8.7 `/settings`
Sections with h2 headings and corner-tick panels:
1. `SPECIFICATION` (7.12)
2. `DEFAULTS`: horizon as a 3-cell segmented control (`1 / 3 / 5`), and max hits as a numeric stepper with square − and + buttons.
3. `ENTRY`: change team.
4. `THEME`: Cyanotype / Whiteprint.
5. `ACCOUNT`: sign out, and delete. The delete confirmation modal needs the user to type `DELETE`, and its warning is drawn inside a loss revision cloud.

### 8.8 `/players`
- The filter row is a strip of bordered cells: `POS [ALL|GKP|DEF|MID|FWD]`, `CLUB [select]`, `MAX £ [range]`, `HORIZON [1–6]`.
- A label above the table reads `RANKED BY: YOUR SPEC R12` or `RANKED BY: DEFAULT SPEC (sign in to edit)`.

### 8.9 `/how-it-works`
- Styled as a **technical manual**: numbered sections `4.1`, `4.2` matching the architecture doc, Plex Sans body, and formulas in Plex Mono boxes with corner ticks.
- Diagrams: a simple linework flow `FPL API → INGEST → METRICS → OPTIMISER → PLAN` with marker annotations.

### 8.10 Error and empty states
- 404: `SHEET NOT FOUND` with a crossed-out sheet drawing.
- API down: `CONNECTION LOST`, plus `RETRY`.
- No plans yet: an empty pitch outline with a marker note *"no revisions yet. Run the agent"* and a primary button.

---

## 9. Accessibility
- Kalam is only for short annotations. Every annotation also has an accessible text equivalent in the DOM (`aria-label` on the SVG group, or visually hidden text).
- Position is shown by shape and text, not colour alone. FDR is shown by hatch density and number.
- **Verify contrast for `linework-dim` and `linework-faint` on `prussian`**, and for `gain`/`loss` text. Target WCAG AA. In Whiteprint, highlighter is only ever used as a fill behind dark text.
- Focus is always visible (marker outline). Tabs follow the WAI-ARIA tabs pattern.
- The progress checklist uses `role="status"` with polite live updates per stage.

## 10. Implementation notes
- Fonts with `next/font/google`: `IBM_Plex_Sans_Condensed`, `IBM_Plex_Sans`, `IBM_Plex_Mono`, `Kalam`.
- Grid background as a Tailwind utility (`bg-blueprint-grid`) using `background-image` with two `linear-gradient` layers each way.
- SVG pattern defs for FDR hatches live once in the root layout (`<HatchDefs />`) and are referenced by ID.
- Annotation component: `<MarkerArrow from={rect} to={rect} seed={playerId} />` computes a curved path and animates `stroke-dashoffset`.
- Set shadcn `--radius: 0`. Override `Card` to use corner ticks (`::before`/`::after` plus two extra spans) or a 1px border variant.
