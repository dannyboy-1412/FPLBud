# FPLBud UI Design Spec 02: "Floodlight"

> A dark, cinematic, night-match direction. The app feels like a stadium under floodlights at 19:45 on a Tuesday: deep turf in shadow, sodium-amber light, chalk-white lines, and a scoreboard that counts down to the deadline.

Source of truth for features and data: `docs/ARCHITECTURE.md` (§2A tiers, §6A agent, §7 endpoints, §8 pages). This document only defines **how it looks and behaves**.

---

## 1. Concept

| | |
|---|---|
| **Metaphor** | Stadium at night. Light falls from four corner pylons onto the pitch, and whatever is lit is what matters. |
| **Personality** | Atmospheric, dramatic, focused. A "big-match" feeling every deadline. |
| **Signature moves** | 1) **Light pools**: soft amber radial glows behind the focal element of each screen. 2) **Scoreboard** typography (condensed caps plus an LED-style countdown). 3) **Mown-stripe pitch** in near-black greens. 4) Agent progress shown as **six floodlights switching on**. |
| **Avoid** | Pure black `#000`, neon lime, purple, blue-tinted "dashboard dark" greys, glassmorphism blur panels, and rainbow charts. |

Design principles:
1. **Light means attention.** Only the primary decision on a screen gets the amber glow. Everything else sits in shade.
2. **Dark, but warm.** Neutrals are green-black, never blue-grey.
3. **Read from the stands.** Big, condensed, uppercase labels that scan at a glance on a phone.
4. **Calm motion.** Light fades in like a floodlight warming up, slowly, and never flickers.

---

## 2. Colour

### 2.1 Core palette (dark-only product; there's no light mode in v1)

| Token | Hex | Use |
|---|---|---|
| `night` | `#0B1110` | App background |
| `turf-900` | `#0F1A16` | Base surfaces (panels) |
| `turf-800` | `#14231D` | Raised surfaces (cards, popovers) |
| `turf-700` | `#1C2F27` | Hover, inputs, table zebra |
| `turf-600` | `#284036` | Borders (strong) |
| `line` | `#22352D` | Hairline borders |
| `chalk` | `#E9EEE8` | Primary text, pitch lines |
| `chalk-dim` | `#A7B5AD` | Secondary text |
| `chalk-faint` | `#6B7C73` | Captions, disabled |
| `sodium` | `#FFB547` | Primary accent: CTA, captain, recommended, focus |
| `sodium-deep` | `#E08F1B` | Pressed state, borders on sodium |
| `sodium-glow` | `rgba(255,181,71,0.18)` | Light pools |
| `haze` | `#7FD1AE` | Positive: gain, "play now", available chips |
| `haze-bg` | `rgba(127,209,174,0.12)` | Positive backgrounds |
| `flare` | `#FF6B5B` | Negative: hits, out/injured, errors |
| `flare-bg` | `rgba(255,107,91,0.12)` | Negative backgrounds |
| `dusk` | `#F2D16B` | Warning: doubtful, expiring chip |
| `dusk-bg` | `rgba(242,209,107,0.12)` | Warning backgrounds |
| `steel` | `#8FB3D9` | Info: links, neutral highlights, vice-captain |

### 2.2 Domain colours

**Positions.** A thin 3px top bar on the player token plus a text code:

| Position | Colour |
|---|---|
| GKP | `#F2D16B` (dusk) |
| DEF | `#7FD1AE` (haze) |
| MID | `#8FB3D9` (steel) |
| FWD | `#FF8E6E` (ember) |

**FDR 1–5** uses a "light level" scale. Easy fixtures are lit, hard fixtures are in shadow. Each swatch also prints the number:

| FDR | Background | Text | Border |
|---|---|---|---|
| 1 | `#FFD48A` | `#1A1206` | none |
| 2 | `#C9A160` | `#1A1206` | none |
| 3 | `#5E5A48` | `#E9EEE8` | none |
| 4 | `#2E2B24` | `#E9EEE8` | 1px `#4A453A` |
| 5 | `#151412` | `#A7B5AD` | 1px `#3A362E` |

Home is marked with a small filled dot `•` before the opponent code. Away has no dot.

**Flags:**

| State | Treatment |
|---|---|
| 75% | `dusk` text `75%` with a half-lit ring around the token |
| 50% / 25% | `dusk` on `dusk-bg` chip |
| out (`i`, `s`, `u`, 0%) | `flare` on `flare-bg` chip, token desaturated to 40% |

### 2.3 Light pools (the signature gradient)
Only gradient type allowed. Applied as a pseudo-element behind the focal block:

```css
.light-pool::before {
  content: "";
  position: absolute; inset: -20% -10% auto -10%; height: 140%;
  background: radial-gradient(60% 50% at 50% 0%, rgba(255,181,71,0.18), transparent 70%);
  pointer-events: none;
}
```
- One light pool per viewport, max. Use it on the landing hero, the recommended plan card, and the onboarding confirmation.
- The page background has four very faint corner pools (6% opacity), like pylons out of shot. They are static.

### 2.4 shadcn/ui variable mapping

```css
:root {
  --background: 165 21% 5%;       /* night */
  --foreground: 105 14% 92%;      /* chalk */
  --card: 155 27% 11%;            /* turf-800 */
  --card-foreground: 105 14% 92%;
  --popover: 155 27% 11%;
  --popover-foreground: 105 14% 92%;
  --primary: 36 100% 64%;         /* sodium */
  --primary-foreground: 30 60% 6%;
  --secondary: 153 25% 15%;       /* turf-700 */
  --secondary-foreground: 105 14% 92%;
  --muted: 153 25% 15%;
  --muted-foreground: 146 10% 68%;/* chalk-dim */
  --accent: 155 47% 66%;          /* haze */
  --accent-foreground: 165 21% 5%;
  --destructive: 6 100% 68%;      /* flare */
  --destructive-foreground: 165 21% 5%;
  --border: 153 21% 17%;          /* line */
  --input: 153 25% 15%;
  --ring: 36 100% 64%;
  --radius: 10px;
}
```

---

## 3. Typography

| Role | Font (Google Fonts) | Notes |
|---|---|---|
| Display / labels | **Barlow Condensed** (600, 700, 800) | Uppercase headings, tabs, scoreboard labels |
| Body / UI | **Barlow** (400, 500, 600) | Paragraphs, controls |
| Numbers / LED | **Martian Mono** (400, 600; width 87.5 if variable) | Countdown, projections, prices, all tabular figures |

| Token | Size / LH | Font | Use |
|---|---|---|---|
| `hero` | 5 / 0.9, tracking −0.01em, UPPERCASE | Barlow Condensed 800 | Landing headline |
| `h1` | 2.5 / 1, UPPERCASE | Barlow Condensed 700 | Page title |
| `h2` | 1.5 / 1.1, UPPERCASE, tracking 0.02em | Barlow Condensed 700 | Section title |
| `label` | 0.75 / 1, UPPERCASE, tracking 0.16em | Barlow Condensed 600 | Field labels, kickers |
| `body` | 1 / 1.6 | Barlow 400 | Prose |
| `ui` | 0.9375 / 1.4 | Barlow 500 | Buttons, cells |
| `num-xl` | 3.25 / 1 | Martian Mono 600 | Gain vs roll |
| `num` | 1.125 / 1 | Martian Mono 400 | Inline stats |
| `led` | 2 / 1, tracking 0.08em | Martian Mono 600 | Deadline countdown |

Wordmark: `FPLBUD` in Barlow Condensed 800, with the **"O"-shaped floodlight icon** (a circle with four short rays at 45°) replacing the dot of an implied "i". If that's awkward, place it as a separate glyph before the wordmark. Colour chalk, icon sodium.

---

## 4. Layout, spacing and shape

- **Grid:** 12 columns, max width 1280px, 24px gutters, 32px page padding (16px on mobile).
- **Spacing:** 4, 8, 12, 16, 20, 24, 32, 40, 56, 80.
- **Radius:** 10px for cards, 8px for inputs and buttons, 999px for chips and tokens.
- **Borders:** 1px `line` by default. The recommended card has a 1px `sodium` border at 50% opacity plus a light pool.
- **Elevation:** no grey shadows. Raised = lighter turf surface. Modals get `0 24px 80px rgba(0,0,0,0.6)` plus a 1px `turf-600` border.
- **Breakpoints:** 640 / 768 / 1024 / 1280. The dashboard uses a two-column layout from `lg`.

---

## 5. Iconography and imagery

- Icons: **Tabler Icons**, 1.75px stroke, 20px, `chalk-dim`, and `sodium` when active.
- Player tokens: a 48px **disc** in `turf-700` with the club's 3-letter code in Barlow Condensed 700, and a 3px position-colour arc on top. No photos, no club crests (licensing).
- Pitch: SVG with alternating mown stripes `#10201A` / `#0D1B16`, 8 stripes vertical, and chalk lines at 60% opacity, 1.5px. A single soft light pool falls from the top centre.
- Empty states: a simple line drawing of a floodlight pylon (chalk-faint, 1.5px stroke).

---

## 6. Motion

- Durations: 150ms (hover), 240ms (tabs), 600ms ("warm up" light pools), 900ms (floodlight switch-on).
- Easing: `cubic-bezier(0.16, 1, 0.3, 1)` (ease-out-expo) for entrances. `ease-in-out` for glows.
- **Warm-up:** light pools fade from 0 to target opacity over 600ms while scaling from 0.92 to 1.
- **Number change:** digits roll vertically, one digit at a time, like a mechanical scoreboard (only on gain, bank, and countdown minutes). Each digit takes 180ms.
- Pitch plan change (switching tabs): transferred-in tokens fade out and back in with a 300ms sodium ring pulse, once.
- `prefers-reduced-motion`: no scale, no roll, no pulse. Opacity fades at 150ms only.

---

## 7. Components

### 7.1 Top bar ("Scoreboard")
- 64px tall, background `night` with a 1px `line` bottom border.
- Left: wordmark. Centre: a **scoreboard module**, a `turf-900` rounded 8px panel containing `GW7` (label style), a divider, and an LED countdown `2D 14:06:31` (Martian Mono, sodium). Under 2 hours the countdown turns `flare` and gains a slow 2s glow pulse. Reduced motion disables the pulse.
- Right: nav (Barlow Condensed 600 uppercase, `chalk-dim`, active = chalk with a 2px sodium underline), then the avatar (32px disc) or `SIGN IN`.
- Mobile: the countdown stays visible, and nav moves to a bottom tab bar (Dashboard, Players, Settings) at 64px with icons and labels.

### 7.2 Team ID input
- A single `turf-800` field, 64px tall, 10px radius, Martian Mono 600 at 1.75rem, centred digits, placeholder `1234567` in `chalk-faint`.
- On focus: 1px sodium border plus a soft outer glow `0 0 0 4px rgba(255,181,71,0.15)`.
- The button attaches to the right edge: sodium fill, night text, `GO`.
- Help is below the field as a **"Where's my ID?"** disclosure. It expands to show a mock browser URL bar: `fantasy.premierleague.com/entry/` **`1234567`** `/event/6`, with the ID highlighted in sodium.
- Not found (404): the field border turns flare, the field shakes once horizontally (4px, 3 cycles, 300ms; disabled under reduced motion), and the message reads *"No team with that ID. Double-check the number in your Points page URL."*

### 7.3 Pitch view
- Aspect ratio 4:5 on desktop, 3:4 on mobile, 16px radius, `turf-900` frame.
- Rows are GKP → FWD bottom to top, evenly distributed by formation.
- **Token:** 48px disc, club code inside, then below it the surname (Barlow 600, 13px, chalk) and a mini-row `6.4` (Martian Mono) plus the FDR swatch for the next fixture (16px tall, 6px radius).
- **Captain:** a sodium ring 2px around the disc, a `C` badge (16px sodium disc, night text), and a light pool under the token at 25% opacity. **Vice:** a steel ring 1px and a `V` badge (steel outline).
- **Transferred in:** a haze ring and an `IN` tag above the token.
- **Flagged:** see 2.2.
- **Bench:** a "dugout" strip below the pitch: `turf-800` panel, label `BENCH`, four tokens at 40px with order numbers 1–4 in Martian Mono.

### 7.4 Context panel ("Matchday Info")
A `turf-800` card with a 2×2 stat grid:
- `BANK` `£1.4m` · `FREE TRANSFERS` `1` · `TEAM VALUE` `£101.2m` · `CHIPS` `3 left`
- Estimated values (bank, FT, selling prices) get a dashed underline in `chalk-faint` and a small `EST` tag (label style, `dusk` text, `dusk-bg`). The tooltip reads: *"Estimated. FPL doesn't share this publicly. Tap Edit if it's wrong."*
- Chips row: four chip pills (`WC`, `FH`, `BB`, `TC`) with the full name in a tooltip. Available = haze outline. Used = `chalk-faint` with strike-through. Expiring (≤3 GWs) = dusk outline with `EXP GW19`.
- Flags list: token-sized club disc, name, flag chip, and `news` text in `chalk-dim` 13px.
- Caveat box (`turf-900`, 13px, `chalk-dim`, info icon): *"Transfers already made for GW7 stay hidden until the deadline. Edit your squad if you've made any."*
- `EDIT` button (secondary) opens the overrides sheet.

### 7.5 Horizon tabs
- A segmented control on a `turf-900` track, 48px tall, 999px radius.
- Segments: `NEXT GW`, `NEXT 3`, `NEXT 5` in Barlow Condensed 700.
- The active segment has a `turf-700` fill, chalk text, and a 2px sodium bar along the bottom inside the pill. Its indicator slides between tabs over 240ms.
- Each segment also shows the plan's gain in Martian Mono 12px under the label (`+2.1`, `+6.4`, `+9.0`) so users can compare horizons without switching.

### 7.6 Plan card (per horizon)
`turf-800` card with a 10px radius, and a light pool if it's the recommended plan.

1. Header row: label `RECOMMENDED` (sodium) or `ALTERNATIVE` (chalk-dim). On the right, the action summary in h2 (`1 TRANSFER · NO HIT` or `ROLL · 2 FT NEXT WEEK`).
2. **Big number:** `+6.4` in `num-xl` haze, with the label `PROJECTED VS ROLLING`. Next to it are the hits (`−4` in flare with `1 HIT`, or `NO HIT`) and the bank after.
3. Transfer cards (7.7).
4. Captain row: `C` and `V` badges with names and projections. Show the captain's margin over the vice in a chip: `+1.9 CLEAR`.
5. "Why" panel (7.8).
6. Chip tips (7.9).
7. `OTHER PLANS` accordion with alternatives as compact rows: action, gain, hits, and a `VIEW` button that swaps the pitch.

### 7.7 Transfer card
```
┌──────────────────────────────────────────────────────────┐
│ (ARS) SAKA      £10.1m EST  ──►  (CHE) PALMER   £10.6m   │
│  75%  •mun 3  ars 4               •BRE 2  lei 2          │
│ ─────────────────────────────────────────────────────── │
│ FORM ▮▮▮ +.12  FIXTURES ▮▮▮▮▮ +.31  xGI ▮ +.08  H/A ▯ −.05│
└──────────────────────────────────────────────────────────┘
```
- The OUT side is dimmed to 60% opacity. The IN side is full chalk. The arrow is sodium, 20px.
- Metric deltas are tiny horizontal bars made of 4px segments: haze for positive, flare for negative, with values in Martian Mono 12px.
- `cost_delta` sits in the top-right in Martian Mono (`+£0.5m`).
- On N=3/5, a `PER GW` toggle shows `projected_points_by_gw` as a 3- or 5-column mini bar chart: haze bars, with the GW number below each bar.

### 7.8 "Why" panel (explanation)
- A `turf-900` inset with a 3px sodium left border and the label `THE GAFFER'S CALL`.
- The explanation is in Barlow 400 at 1rem/1.65, max 65ch. Player names in the text are wrapped in `chalk` 600, numbers in Martian Mono.
- `reason_codes` render below as small chips: `FIXTURE SWING`, `xGI UPGRADE`, `HIT NOT WORTH IT` (label style, `turf-700` fill, `chalk-dim` text).

### 7.9 Chip tip
- `play_now`: a haze-bg card, a haze 1px border, and a chip icon disc in haze with the text `PLAY BENCH BOOST NOW` and `+13.2` in Martian Mono.
- `consider_gw_X`: a steel outline card, `CONSIDER TRIPLE CAPTAIN · GW9`.
- `hold`: a single line in `chalk-faint`: `HOLD FREE HIT · +4.1 BELOW THRESHOLD`.
- Expiring: a dusk strip `USE IT OR LOSE IT · EXPIRES AFTER GW19`.

### 7.10 Agent progress ("Lights On")
- Six floodlight icons in a row (a pylon with a lamp head), each labelled underneath:
  `TEAM SHEET` (context) · `NEXT GW` (horizon_1) · `NEXT 3` (horizon_3) · `NEXT 5` (horizon_5) · `CHIPS` (chips) · `WRITE-UP` (explain).
- **Off:** lamp `turf-600`. **Current:** lamp sodium at 50% opacity with a breathing glow (1.6s). **Done:** lamp full sodium plus a small static light cone below it (sodium-glow). The cones overlap as stages complete, so the area "lights up".
- Below the lamps is a 4px progress track (`turf-700`) with a sodium fill bound to `progress`, plus copy: *"Running the numbers for 3 gameweeks…"*
- When all six are done, the panel cross-fades (400ms) into the plan cards.
- **Failed:** the current lamp turns flare, with copy *"Lights out. The agent hit a problem."* and the `error` in `chalk-dim`, plus a `TRY AGAIN` sodium button.
- **Slow (over 2 minutes):** *"Still warming up. We'll keep working in the background."* and stop polling.

### 7.11 "Plans updated" banner
- A slide-down bar under the top bar with a `turf-800` background, a 1px sodium bottom border, and a lamp icon.
- Copy: `NEW PLANS · Updated after late injury news` (the reason is from the trigger, as in the architecture), with `SHOW` (sodium text button) and `×`.

### 7.12 Weight sliders ("Tactics Board")
- Each metric is a row with the label (Barlow Condensed 600 uppercase), an info icon (tooltip with the plain-English formula from `/meta`), the slider, and the **effective share** `30%` in Martian Mono.
- Slider: a 6px `turf-700` track. The fill is a sodium gradient from `sodium-deep` to `sodium` (the only linear gradient allowed). The thumb is a 20px chalk disc with a 2px sodium ring, and glows on drag.
- A **share donut** at the top (120px, 14px stroke) shows each metric's renormalised share in a fixed sequence of tints: sodium, haze, steel, dusk, ember, `#C7A2E0` (lilac, only here), and `#9AA89F`. Hovering a segment highlights its slider row.
- Optional metrics: a toggle switch (track `turf-700`, on = haze) next to each label. Turning one on animates the slider to 0.15.
- Live preview chip next to `SAVE`: `PREVIEW +6.8 (was +6.4)`, from debounced `POST /suggestions` (400ms).
- **Guest:** all controls disabled at 35% opacity, covered by an overlay card: lock icon, *"Set your own tactics"*, *"Sign in with Google to choose what matters."*, and a `SIGN IN WITH GOOGLE` button.

### 7.13 Locked horizon overlay (guest `/try`)
- The Next 3 and Next 5 segments show a lock icon instead of the gain number.
- Their panel renders a placeholder plan card blurred (`filter: blur(8px) saturate(0.6)`) under a `night` 55% scrim.
- Centred card with a light pool behind it: h2 `YOUR 5-WEEK PLAN IS IN THE DARK`, body *"Sign in with Google to unlock your 5-week plan."*, primary `SIGN IN WITH GOOGLE`, and a secondary link `What do I get?` that scrolls to the tier comparison on `/`.

### 7.14 Buttons
| Variant | Style |
|---|---|
| Primary | Sodium fill, `#1A1206` text, Barlow Condensed 700 uppercase, 48px, 8px radius. Hover: brighten 6% plus a glow `0 0 24px rgba(255,181,71,0.35)`. Pressed: sodium-deep. |
| Secondary | `turf-700` fill, chalk text, 1px `turf-600` border. |
| Ghost | Chalk-dim text. Hover: `turf-800`. |
| Destructive | Flare outline that becomes a flare fill on hover, with night text. |
| Google | Chalk fill, night text, the official Google "G" mark. Follow Google's branding guidelines. |

Focus ring: 2px sodium, 2px offset, on every interactive element.

### 7.15 Player explorer table
- Sticky header in `turf-900`, label style. Rows are 52px with `line` dividers. Hover = `turf-700`.
- Columns: `#`, player (club disc and name, position code), `£`, `PROJ` (Martian Mono 600, sodium for the top 3 in view), metric mini-bars (5 segments each), and the next 5 FDR swatches.
- Clicking a row opens a right-side drawer (560px) with a player header, a per-GW metric grid (rows = metrics, columns = GW+1…+6, cells shaded by score using haze at alpha 0.1–0.9), and match history.

### 7.16 Feedback
- Toasts: top-centre, `turf-800`, 10px radius, with a 3px left border coloured by status.
- Skeletons: `turf-800` blocks with a slow **sweep of light** (a 2.4s left-to-right gradient with sodium at 4%). Reduced motion makes it static.
- 429: *"Whoa, too many requests. Give it a minute."*

---

## 8. Pages

### 8.1 `/` Landing
- Full-viewport hero on `night` with a large light pool from the top centre and a faint pitch-line illustration (centre circle) at 8% opacity behind it.
- `hero` headline: **"SEE YOUR NEXT MOVE CLEARLY."** Sub (Barlow 1.25rem chalk-dim): *"Transfers, captain and chips for your FPL team, worked out in under a second."*
- Below: the Team ID input (7.2) and, on a separate line, `or SIGN IN WITH GOOGLE for a saved team and 5-week plans`.
- Section 2: a three-step strip (Import → Score → Plan) with numbers in Martian Mono sodium.
- Section 3: a guest vs signed-in comparison as two cards. The signed-in card has the light pool.
- The scoreboard countdown is visible in the top bar.

### 8.2 `/try/[entryId]`
- Header: label `PREVIEW`, h1 team name, manager name in chalk-dim.
- `lg`+: left 7 columns hold the pitch plus dugout, and the right 5 hold Matchday Info. Below, full width: horizon segmented control, then the plan card, with the Next 3/5 lock (7.13).
- Tactics Board disabled (7.12) at the bottom.

### 8.3 `/login`
A centred card (440px) with a light pool above it, the wordmark, h2 `SIGN IN`, the Google button, and fine print: *"Google sign-in only remembers your team. We never ask for your FPL password."*

### 8.4 `/auth/callback`
A single lamp icon warming up (breathing sodium) with *"Signing you in…"*.

### 8.5 `/onboarding`
- h1 `WHAT'S YOUR TEAM ID?` with the input (7.2).
- On valid lookup, a confirmation card rises in with a light pool: team name (h2), manager, overall rank, current GW points, and `THAT'S MY TEAM` (primary) or `NOT MINE` (ghost).
- On confirm, route to `/dashboard`, where the Lights On panel shows immediately.

### 8.6 `/dashboard`
```
Scoreboard top bar
[Plans updated banner]
┌ h1 TEAM NAME · label GW7 ─────────────────────── [RE-RUN AGENT] ┐
├──────── 7 cols ─────────────────────┬──────── 5 cols ───────────┤
│ Pitch (reflects active horizon)     │ Horizon segmented control │
│ Dugout (bench)                      │ Plan card (recommended)   │
│                                     │  ...transfers, captain,   │
│ Matchday Info (collapsible on lg)   │  why, chips               │
│                                     │ Other plans accordion     │
└─────────────────────────────────────┴───────────────────────────┘
```
- While running: the right column shows Lights On (7.10). The pitch shows the current squad dimmed to 70%.
- Mobile order: segmented control (sticky), plan big number, pitch, transfers, why, chips, matchday info.
- `RE-RUN AGENT`: a secondary button with a refresh icon. While active it shows `RUNNING` and a spinning lamp. On 429 the toast reads: *"You've re-run a lot this hour. Try again later."*

### 8.7 `/settings`
Vertical tabs on the left at `lg`: `TACTICS`, `DEFAULTS`, `TEAM`, `ACCOUNT`.
- **Tactics:** the Tactics Board (7.12) with `SAVE & RE-RUN`.
- **Defaults:** default horizon as a segmented control (1/3/5), and max hits as a stepper with Martian Mono value and −/+ buttons (0–3).
- **Team:** the current ID, name, and `CHANGE TEAM`, which opens the input inline.
- **Account:** sign out, and delete account in a flare-bordered "danger zone" card. The confirm modal needs the user to type `DELETE`.

### 8.8 `/players`
- Filter bar: position segmented control (`ALL GKP DEF MID FWD`), team select, max price range slider, and a horizon select (1–6).
- The table follows 7.15. A label above it reads `RANKED BY YOUR TACTICS`, or `RANKED BY DEFAULT TACTICS · SIGN IN TO CUSTOMISE`.

### 8.9 `/how-it-works`
- A single column at 720px. Each section is a `turf-800` card with h2.
- Formulas are in Martian Mono on a `turf-900` inset.
- The hit-margin and chip-threshold tables use the explorer table style.
- A sticky in-page nav on the left at `xl`.

### 8.10 Error and empty states
- 404: a pylon illustration with lamp off and `NOTHING UNDER THESE LIGHTS`, plus a link home.
- API unreachable: *"Floodlight failure. We can't reach the server."* plus `TRY AGAIN`.
- No plans yet: an unlit lamp row and `RUN THE AGENT`.

---

## 9. Accessibility
- The dark palette needs checking: **verify `chalk-dim` and `chalk-faint` on `turf-800`** (chalk-faint is for non-essential captions only). Target WCAG AA 4.5:1 for text and 3:1 for UI.
- Sodium is never used as text on light backgrounds (there are none). Sodium buttons use dark text.
- Colour is never the only signal: FDR swatches print the number, flags print a percentage or code, and gains print a sign.
- Glows and pulses respect `prefers-reduced-motion`. The countdown announces only at thresholds (24h, 2h, 30m) through `aria-live="polite"`, not every second.
- Pitch tokens are focusable buttons with full `aria-label`. Arrow keys move between tokens in the same row.

## 10. Implementation notes
- Fonts with `next/font/google`: `Barlow_Condensed`, `Barlow`, `Martian_Mono`.
- Tailwind theme colours: `night`, `turf-{600..900}`, `line`, `chalk`, `chalk-dim`, `chalk-faint`, `sodium`, `haze`, `flare`, `dusk`, `steel`, `fdr-{1..5}`, `pos-{gkp,def,mid,fwd}`.
- A `<LightPool intensity="md" />` utility component wraps focal blocks. Enforce one per view in review.
- Pitch is a single SVG component with props for stripe count and line opacity.
- Set `color-scheme: dark` on `html`.
