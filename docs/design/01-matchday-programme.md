# FPLBud UI Design Spec 01: "Matchday Programme"

> An editorial, print-inspired direction. FPLBud reads like a matchday programme or broadsheet sports page, with the agent as the paper's tactics columnist. Light-first, warm, typographic, and calm.

Source of truth for features and data: `docs/ARCHITECTURE.md` (§2A tiers, §6A agent, §7 endpoints, §8 pages). This document only defines **how it looks and behaves**.

---

## 1. Concept

| | |
|---|---|
| **Metaphor** | A Saturday matchday programme. Newsprint paper, ink, one hot spot colour, column rules, and big numbers set in a serif. |
| **Personality** | Considered, authoritative, a bit old-school British football. Never "techy". |
| **Signature moves** | 1) Hairline column rules and double rules instead of cards with shadows. 2) Oversized serif numerals for projected points. 3) Explanations are set as a **pull-quote column** with a drop cap. 4) A vermilion "stamp" for the recommended plan. |
| **Avoid** | Drop shadows, gradients, glassmorphism, rounded pill-heavy UI, emoji, purple, neon green, shadcn default slate/zinc greys. |

Design principles:
1. **Type does the work.** Hierarchy comes from size, weight and serif/sans contrast, not from colour or boxes.
2. **One hot colour.** Vermilion is rare and meaningful: the recommended action, the captain, the deadline.
3. **Numbers are headlines.** Gains, projections and bank are always the largest thing in their block.
4. **Honesty in small print.** Estimates (FT, selling prices, bank) get a footnote-style dagger (†) and a caption, like a newspaper correction.

---

## 2. Colour

### 2.1 Core palette

| Token | Hex | Use |
|---|---|---|
| `paper` | `#F4EFE4` | Page background (warm newsprint) |
| `paper-deep` | `#EAE3D3` | Inset areas, table zebra, pitch surround |
| `paper-bright` | `#FBF8F1` | Raised surfaces (popovers, inputs) |
| `ink` | `#161412` | Primary text, rules |
| `ink-soft` | `#4A453E` | Secondary text |
| `ink-faint` | `#8C857A` | Captions, disabled, placeholder |
| `rule` | `#CFC6B4` | Hairlines and dividers |
| `vermilion` | `#D9381E` | Primary accent: recommended plan, captain, CTA, deadline |
| `vermilion-ink` | `#A82813` | Vermilion text on paper (AA-safe at body sizes) |
| `racing` | `#1F4D3A` | Secondary accent: positive gain, "play now" chips, pitch lines |
| `racing-tint` | `#DCE5DC` | Positive backgrounds |
| `ochre` | `#B8860B` | Warnings: doubtful players, "use it or lose it" |
| `ochre-tint` | `#F3E6C4` | Warning backgrounds |
| `claret` | `#7A1F2B` | Negative: hits, injured/out, errors |
| `claret-tint` | `#F0DADB` | Negative backgrounds |

### 2.2 Dark mode ("Evening Edition")
Optional, toggled in settings. Keep the warmth and don't invert to pure black.

| Token | Dark hex |
|---|---|
| `paper` | `#1A1814` |
| `paper-deep` | `#12110E` |
| `paper-bright` | `#24211B` |
| `ink` | `#EDE6D6` |
| `ink-soft` | `#B9B09F` |
| `ink-faint` | `#7D7567` |
| `rule` | `#3A352C` |
| `vermilion` | `#F0553A` |
| `racing` | `#6FAE8C` |
| `ochre` | `#D9A93A` |
| `claret` | `#E06A78` |

### 2.3 Domain colours

**Positions** are shown as small-caps text labels with a coloured left rule (2px), never as filled blobs:

| Position | Rule colour |
|---|---|
| GKP | `#B8860B` (ochre) |
| DEF | `#1F4D3A` (racing) |
| MID | `#2B4C7E` (programme blue) |
| FWD | `#D9381E` (vermilion) |

**Fixture difficulty (FDR 1–5).** A monochrome ink-density scale, so it reads like a printed table and never copies FPL's green/red:

| FDR | Background | Text |
|---|---|---|
| 1 | `#FBF8F1` with 1px `ink` border | `ink` |
| 2 | `#E3DCCB` | `ink` |
| 3 | `#BDB4A1` | `ink` |
| 4 | `#5E574B` | `paper` |
| 5 | `#161412` | `paper` |

Home fixtures show the opponent in CAPS (`ARS`), away fixtures in lowercase (`ars`). This is a programme convention, and it means colour is not the only signal.

**Player availability flags** (from `status` / `chance_of_playing_next_round`):

| Flag | Treatment |
|---|---|
| `a`, 100% | none |
| 75% | ochre `◐ 75` |
| 50% / 25% | ochre-on-ochre-tint `◑ 50` |
| `d` 0%, `i`, `s`, `u` | claret-on-claret-tint, text `OUT`, `INJ`, `SUS`, `N/A` |

### 2.4 shadcn/ui variable mapping (`globals.css`)

```css
:root {
  --background: 40 33% 93%;        /* paper */
  --foreground: 30 10% 8%;         /* ink */
  --card: 40 33% 93%;              /* cards are paper; separated by rules, not fill */
  --card-foreground: 30 10% 8%;
  --popover: 43 52% 96%;           /* paper-bright */
  --popover-foreground: 30 10% 8%;
  --primary: 9 76% 48%;            /* vermilion */
  --primary-foreground: 43 52% 96%;
  --secondary: 43 27% 87%;         /* paper-deep */
  --secondary-foreground: 30 10% 8%;
  --muted: 43 27% 87%;
  --muted-foreground: 35 9% 26%;   /* ink-soft */
  --accent: 154 43% 21%;           /* racing */
  --accent-foreground: 43 52% 96%;
  --destructive: 352 60% 30%;      /* claret */
  --destructive-foreground: 43 52% 96%;
  --border: 40 22% 76%;            /* rule */
  --input: 40 22% 76%;
  --ring: 9 76% 48%;
  --radius: 2px;
}
```

---

## 3. Typography

| Role | Font (Google Fonts) | Notes |
|---|---|---|
| Display / numerals | **Fraunces** (variable; opsz 72–144, wght 600–800, SOFT 0) | Mastheads, page titles, big projected points |
| Body / reading | **Newsreader** (opsz 6–72, wght 400/500, italic) | Explanations, how-it-works prose |
| UI / labels / tables | **Instrument Sans** (400/500/600) | Buttons, tabs, table cells, form labels |

All numbers in tables and stats use `font-variant-numeric: tabular-nums lining-nums`. Big headline numbers use Fraunces with `oldstyle-nums` turned **off**.

Type scale (rem at 16px root):

| Token | Size / line-height | Font | Use |
|---|---|---|---|
| `masthead` | 4.5 / 0.95, tracking −0.02em | Fraunces 800 | Landing hero, "FPLBud" wordmark |
| `h1` | 2.75 / 1.05 | Fraunces 700 | Page titles |
| `h2` | 1.75 / 1.15 | Fraunces 600 | Section heads |
| `kicker` | 0.75 / 1, tracking 0.14em, UPPERCASE | Instrument Sans 600 | Small labels above headings ("NEXT 3 GAMEWEEKS") |
| `stat-xl` | 3.5 / 1 | Fraunces 700 | `+6.4` gain vs roll |
| `stat` | 1.5 / 1 | Fraunces 600 | Bank, FT, captain projection |
| `body` | 1.0625 / 1.6 | Newsreader 400 | Prose |
| `ui` | 0.875 / 1.4 | Instrument Sans 500 | Controls, table cells |
| `caption` | 0.75 / 1.35, italic | Newsreader 400 | Footnotes, estimates, caveats |

Wordmark: "FPL" in Fraunces 800 roman plus "Bud" in Fraunces 700 *italic*, with a vermilion full stop: **FPL*Bud*.**

---

## 4. Layout, spacing and shape

- **Grid:** a 12-column "broadsheet" grid, max width 1200px, 24px gutters. On desktop, columns are separated by 1px `rule` vertical lines (column rules), not whitespace alone.
- **Spacing scale:** 4, 8, 12, 16, 24, 32, 48, 72, 96. Section breaks use 48px plus a **double rule** (1px, 3px gap, 1px).
- **Radius:** 2px everywhere. Avatars and captain marks are the only circles.
- **Borders:** 1px `rule` for structure, 1px `ink` for emphasis or focus, 3px `vermilion` top border for the recommended item.
- **Elevation:** none. Popovers use a 1px `ink` border plus `paper-bright` fill. Modals add a 6px solid `ink` offset "print registration" shadow (`box-shadow: 6px 6px 0 #161412`), and that is the only shadow in the system.
- **Breakpoints:** `sm` 640, `md` 768, `lg` 1024, `xl` 1280. Below `lg` the layout collapses to a single column and the column rules become horizontal rules.
- **Texture:** an optional 3% opacity paper-grain SVG noise on `body` background. It must be static and never animated.

---

## 5. Iconography and imagery

- Icons: **Phosphor Icons, "Light" weight** at 20px, in `ink-soft`. Don't use Lucide defaults.
- Avoid player photos (licensing). Represent players with **typographic shirts**: a 40×44 SVG shirt outline (1.5px ink stroke) with the player's position initial inside, and the club's 3-letter code in small caps below.
- Illustrations: none. Use typographic ornaments instead: `❧`, `§`, `†` and a centred `* * *` section break.

---

## 6. Motion

Restrained, like turning a page.
- Durations: 120ms (hover), 200ms (tabs, accordions), 320ms (page/plan reveal).
- Easing: `cubic-bezier(0.2, 0.0, 0, 1)`.
- Plan reveal: blocks fade in and translate up 8px with a 40ms stagger, top to bottom (like reading down a column).
- Numbers: when a gain or projection changes (slider preview), crossfade the old number out and the new one in. Don't use counting animations.
- `prefers-reduced-motion`: disable translate and stagger, keep a 120ms opacity change.

---

## 7. Components

### 7.1 Masthead (global header)
- Height 72px on desktop. Wordmark on the left. Centre shows the **edition line** in `kicker` style: `GAMEWEEK 7 · DEADLINE FRI 17 OCT, 21:00` from `/meta`, plus a live countdown in Instrument Sans tabular. Under 24h the countdown turns `vermilion-ink`.
- Right: nav links (`Dashboard`, `Players`, `How it works`) in Instrument Sans 500, with an active state of a 2px ink underline offset by 6px. Then the avatar (circle, 28px, 1px ink ring) or a "Sign in" text button.
- A double rule sits under the masthead.

### 7.2 Team ID input (landing and onboarding)
- One large input: 64px tall, Fraunces 600 at 2rem, digits only (`inputmode="numeric"`), bottom border only (2px ink), no box.
- The label above is a kicker: `YOUR FPL TEAM ID`.
- The help text below is a caption: *"It's the number in the address bar on your FPL 'Points' page: fantasy.premierleague.com/entry/**1234567**/event/6"*, with the ID part highlighted on a `ochre-tint` background.
- The submit button sits inline to the right: a vermilion square button with a → arrow.
- **Team not found (404):** the bottom border turns claret and a caption appears: *"No team with that ID. Check the number in your Points page URL."*

### 7.3 Pitch view
- The pitch is **not green**. It's a `paper-deep` rectangle with `racing` 1px line markings (halfway line, centre circle, boxes) drawn in SVG, like a programme's formation diagram.
- Rows run GKP → DEF → MID → FWD from the bottom up. Each player token is a typographic shirt plus:
  - surname (Instrument Sans 600, 13px, truncate at 10ch)
  - `proj` for GW+1 in Fraunces 600, 18px
  - next fixture code (CAPS for home, lowercase for away) on its FDR swatch, 18px tall
- **Captain:** a vermilion circle with "C" in paper colour, 18px, top-right of the shirt. **Vice:** a 1px vermilion ring with "V" in vermilion-ink.
- **Flagged player:** the shirt stroke becomes ochre or claret and a flag badge sits top-left.
- **Transfer in (on plan view):** the shirt gets a vermilion fill at 12% and an "IN" kicker label. The outgoing player is shown struck-through in the transfer card, not on the pitch.
- **Bench:** a ruled strip below the pitch labelled `BENCH` with four tokens numbered 1–4 in order (GK first per FPL rules, then the outfield order from `bench[4]`).

### 7.4 Context panel ("Team Sheet")
A narrow column beside the pitch, set like a programme's team-sheet box:
- Rows of label (kicker) plus value (`stat`): `BANK £1.4m†`, `FREE TRANSFERS 1†`, `TEAM VALUE £101.2m`.
- `CHIPS`: each available chip as small-caps text (`WILDCARD`, `FREE HIT`, `BENCH BOOST`, `TRIPLE CAPTAIN`) with "until GW19" in caption style. Used chips are struck through in `ink-faint`.
- `FLAGS`: a list of flagged squad players with their flag badge and the `news` text in italic caption.
- The † footnote at the bottom reads: *"† Estimated. FPL doesn't publish selling prices or free transfers publicly. Edit if ours are wrong."*, followed by an `Edit` link that opens the overrides sheet (FT, bank, squad).
- Permanent caveat in caption style: *"Transfers you've already made for GW7 aren't visible until the deadline passes."*

### 7.5 Horizon tabs
- Three tabs set as **section headings**, not pills: `Next GW` · `Next 3` · `Next 5`, in Fraunces 600 at 1.5rem.
- Inactive tabs are `ink-faint`. The active tab is `ink` with a 3px vermilion bar *above* the word (like a newspaper section flag).
- A thin `rule` sits under the tab row. Keyboard: arrow keys move between tabs (WAI-ARIA tabs pattern).

### 7.6 Plan "article" (one per horizon)
Laid out like a short newspaper article:
1. **Kicker:** `NEXT 3 GAMEWEEKS · RECOMMENDED`
2. **Headline (h2):** a generated summary, e.g. *"Sell Saka, buy Palmer"* or *"Roll the transfer"*.
3. **Stat row:** `stat-xl` gain vs roll (`+6.4`) in racing, with a caption "projected points vs rolling". Next to it: hits (`−4` in claret, or `No hit`), and bank after (`£0.3m`).
4. **Transfer cards** (see 7.7).
5. **Captain line:** `CAPTAIN Haaland 8.1 · VICE Palmer 6.2`. The captain's name is in vermilion-ink.
6. **The column** (see 7.8).
7. **Chip notes** (see 7.9).
8. **Alternatives:** "Other plans" in a collapsible list with the same layout at smaller size. Shows `roll_alternative` and "one fewer transfer" for N=3/5.

The recommended plan has a **vermilion stamp** at the top-right: a rotated (−6°) rectangle, 2px vermilion border, with `AGENT'S PICK` in Instrument Sans 700 uppercase, tracking 0.12em. It's static with no animation.

### 7.7 Transfer card
A two-column ruled row, not a boxed card:

```
OUT                         │ IN
Saka  ARS · MID · £10.1m†   │ Palmer  CHE · MID · £10.6m
◑ 75  · ars ▮4  mun ▮3      │ BRE ▮2  lei ▮2
──────────────────────────────────────────────────────
Why  Form +0.12  Fixtures +0.31  Expected stats +0.08  Home −0.05
```
- The OUT name is struck through (1px ink line) in `ink-soft`. The IN name is `ink` 600.
- "Why" shows `metric_deltas` as small inline **ink bars**: 40px max width, racing for positive and claret for negative, with the signed value in tabular numerals.
- `cost_delta` is shown on the far right as `−£0.5m` or `+£0.5m`.
- For N=3/5, an expandable "By gameweek" line shows `projected_points_by_gw` as a mini table of numerals.

### 7.8 Explanation column ("The Column")
- Newsreader 400, 1.0625rem, max 62ch, with a **3-line drop cap** in Fraunces 700 vermilion.
- A left border of 1px `rule` and 24px padding. The byline above is a kicker: `THE AGENT'S VIEW`.
- `explanation_source = template` shows no badge. In the future, `llm` shows a caption "Written with AI from the agent's numbers."

### 7.9 Chip note
Set as a sidebar box: a 1px ink border with a kicker header.
- `play_now`: header on a racing background with paper text, `PLAY BENCH BOOST NOW`, plus expected gain `+13.2`.
- `consider_gw_X`: ink border, `CONSIDER TRIPLE CAPTAIN IN GW9`.
- `hold`: `ink-faint` text, collapsed to a single line: `Hold Free Hit: +4.1 isn't worth it`.
- **Use it or lose it** (`stop_event` ≤ 3 GWs away): an ochre-tint strip on top: `EXPIRES AFTER GW19`.

### 7.10 Agent progress ("Going to Press")
Shown while polling `GET /agent/runs/{id}`. It's a vertical list of six stages, styled like a print checklist:

```
✓  Reading your team sheet          context
✓  Next gameweek                    horizon_1
●  Next 3 gameweeks                 horizon_3      (current; vermilion dot pulsing at 1.2s)
○  Next 5 gameweeks                 horizon_5
○  Chip check                       chips
○  Writing it up                    explain
```
- Above the list sits a 2px ink progress rule filling left to right from `progress` (0–100).
- Done stages are `ink`, the current stage is `ink` 600 with a vermilion dot, and future stages are `ink-faint`.
- **Failed:** the current stage turns claret with "Something went wrong" plus the `error` text in caption, and a `Try again` button (POST `/me/agent/rerun`).
- **Timeout (2 minutes of polling):** *"This is taking longer than usual. We'll keep working, so check back shortly."* plus a `Refresh` link.

### 7.11 "Plans updated" banner ("Stop Press")
- A full-width strip under the masthead with a vermilion background and paper text: `STOP PRESS — Plans updated after injury news. [Show new plans]`.
- The reason comes from the run `trigger`: `pre_deadline` → "injury news", `data_refresh` → "a data refresh", `post_deadline` → "the deadline".
- Can be dismissed, and doesn't reappear for the same run.

### 7.12 Weight sliders ("Selection Criteria")
- One row per metric: label (Instrument Sans 600), a one-line description in caption, the slider, and the **effective share** after renormalisation (e.g. `30%`) in Fraunces 600.
- Slider: a 2px ink track with a filled portion in ink and a **square** 14px vermilion thumb. Steps of 0.05, range 0–1.
- Optional metrics (`Value for money`, `Minutes security`, `Price/ownership trend`) sit under the kicker `OPTIONAL`, each with a toggle. Switching one on sets it to 0.15 and animates the thumb there.
- A small horizontal **stacked bar** above all sliders shows each metric's share, using ink-density fills with labels. It reads like a printed pie chart flattened into a bar.
- `Reset to defaults` text button.
- **Guest (disabled) state:** sliders at 40% opacity with a centred overlay caption: *"Sign in with Google to set your own criteria."* and a `Sign in` button.

### 7.13 Locked horizon overlay (guest `/try`)
- The Next 3 and Next 5 tab panels render a realistic placeholder plan with `filter: blur(6px)` and `paper` at 60% over it.
- Centred on top: a boxed notice (1px ink border, `paper-bright`, 6px offset ink shadow) containing a kicker `MEMBERS' EDITION`, the h2 *"Your 5-week plan is one sign-in away"*, the body copy "Sign in with Google to unlock your 5-week plan", and a primary button `Sign in with Google`.
- The tabs themselves stay clickable and show a small lock glyph after the label.

### 7.14 Buttons
| Variant | Style |
|---|---|
| Primary | Vermilion fill, paper text, Instrument Sans 600, 44px tall, 2px radius. Hover: `#C23017`. Active: translate 1px down. |
| Secondary | Transparent, 1px ink border, ink text. Hover: `paper-deep` fill. |
| Text | Ink text with a 1px underline offset 3px. Hover: vermilion-ink. |
| Destructive | Claret fill, paper text. |
| Google sign-in | Paper-bright fill, 1px ink border, the official Google "G" mark (follow Google branding rules), and the text "Sign in with Google". |

Focus ring for everything: 2px vermilion outline, 2px offset.

### 7.15 Data table (player explorer)
- Header row in kicker style with a 1px ink bottom border. Rows are 44px, with `paper-deep` zebra striping on even rows.
- Columns: rank, player (name plus club/position), price, `proj` for the selected horizon (Fraunces 600), the score bars for each metric (ink-density mini bars), and the next 5 fixtures as FDR swatches.
- The sorted column header is underlined in vermilion. Rows are clickable and open a **player sheet** from the right (520px).

### 7.16 Feedback
- Toasts: bottom-left, a paper-bright box with a 1px ink border, no shadow, auto-dismiss after 4s.
- Skeletons: `paper-deep` blocks with a slow 1.6s opacity pulse (0.6 to 1). Never shimmer.
- Rate-limited (429): *"Easy, gaffer. Too many requests. Try again in a minute."*

---

## 8. Pages

### 8.1 `/` Landing
```
┌──────────────────────────── masthead ────────────────────────────┐
│ KICKER: THE FPL TACTICS COLUMN · GAMEWEEK 7                       │
│ FPLBud.  (masthead size)                                          │
│ "Your transfers, captain and chips, worked out." (Newsreader 1.5) │
│ ════════════════════════════════════════════════════════════════ │
│ [ col 1–7: TEAM ID input + help ]  │ [ col 8–12: Sign in box ]    │
│                                    │  "Members get a 5-week plan, │
│                                    │   saved team and auto        │
│                                    │   re-runs." [Sign in w/Google]│
│ ════════════════════════════════════════════════════════════════ │
│ Three columns "How it works" teaser: 1 Import · 2 Score · 3 Plan  │
│ each with a big Fraunces numeral and two lines of copy            │
└──────────────────────────────────────────────────────────────────┘
```

### 8.2 `/try/[entryId]` Guest preview
- Header: kicker `PREVIEW EDITION`, h1 = the FPL team name, caption = the manager name.
- Desktop: columns 1–7 hold the pitch view and bench. Columns 8–12 hold the Team Sheet.
- Below, full width: horizon tabs with Next GW unlocked (from `POST /suggestions`) and Next 3 / Next 5 locked (7.13).
- Selection Criteria shown disabled (7.12).
- Loading: a pitch skeleton plus a caption *"Fetching the team sheet from FPL…"*.

### 8.3 `/login`
A centred narrow column, 420px. The wordmark, the h2 *"Sign in to keep your team"*, the Google button, and a caption *"We never ask for your FPL password. Google sign-in only remembers your team ID."*

### 8.4 `/auth/callback`
Blank paper with a centred caption *"Signing you in…"* and the pulsing vermilion dot. It redirects automatically.

### 8.5 `/onboarding`
- Step kicker `STEP 1 OF 1`. The team ID input (7.2).
- After validation, a **confirmation slip** appears below: team name (Fraunces 700), manager, overall rank, and a `This is my team` primary button with a `Not you? Try again` text link.
- On submit, transition straight to `/dashboard`, where the agent progress shows.

### 8.6 `/dashboard`
```
masthead + (Stop Press banner if any)
┌ kicker: GAMEWEEK 7 · DEADLINE IN 2d 14h ───────── [Re-run agent] ┐
│ h1: Team Name                                                     │
├──────────────── col 1–7 ───────────────┬──── col 8–12 ───────────┤
│ Pitch (plan view for active tab)       │ Team Sheet (7.4)        │
│ Bench strip                            │                          │
├────────────────────────────────────────┴──────────────────────────┤
│ Horizon tabs  Next GW · Next 3 · Next 5                           │
│ ┌ col 1–8: Plan article (7.6) ──────┬ col 9–12: Chip notes ─────┐│
│ │ headline, stat row, transfers,    │ captain box, chips,        ││
│ │ the column                        │ flags affecting the plan   ││
│ └───────────────────────────────────┴────────────────────────────┘│
└───────────────────────────────────────────────────────────────────┘
```
- While the run is queued or running, the Plan article area is replaced by Going to Press (7.10). The pitch shows the current squad.
- The pitch reflects the **active tab's** plan: transfers in are highlighted, and the XI, bench and captain come from that plan.
- `Re-run agent` is a secondary button. While a run is active it's disabled with the label `Running…`.
- Mobile order: kicker and title, tabs (sticky under the header), plan headline and stat row, pitch, transfers, column, chips, team sheet.

### 8.7 `/settings`
Sections are separated by double rules:
1. **Selection Criteria** (7.12). A `Save` primary button shows the caption "Saving re-runs your agent." The weight preview calls `POST /suggestions` debounced at 400ms and shows the live `+gain` next to the save button.
2. **Defaults:** default horizon (segmented control of 1 / 3 / 5 styled as the tabs) and max hits (a stepper 0–3 with Fraunces numerals).
3. **Your team:** the current team ID and name, plus `Change team`, which reuses the onboarding input inline.
4. **Appearance:** Morning / Evening edition toggle.
5. **Account:** `Sign out` (secondary) and `Delete account` (destructive). Delete opens a modal: *"This deletes your profile, saved team and plans. It can't be undone."* The user has to type `DELETE` to enable the button.

### 8.8 `/players`
- Filter bar as a ruled row: position (GKP/DEF/MID/FWD text toggles), team (select), max price (slider, £3.5m–£15.0m), horizon (1–6).
- The table follows 7.15. A caption above it reads: *"Ranked by your criteria"* for users, or *"Ranked by default criteria. Sign in to use your own"* for guests.
- Player sheet: name (h2), club, position, price, flag and news, then a per-GW metric breakdown table (rows are metrics, columns are GW+1…+6) with ink-density cells, and recent match history (minutes, points, xG, xA).

### 8.9 `/how-it-works`
- A long-form article: Newsreader body, 62ch, Fraunces h2s, a `§` before each section number.
- Formulas set in a ruled box using Instrument Sans tabular. Use `×` and `Σ`, not code syntax.
- Tables for hit margins, roll values and chip thresholds styled like 7.15.

### 8.10 Error and empty pages
- 404: kicker `CORRECTION`, h1 *"That page isn't in this edition."*, and a link home.
- API down: *"We can't reach the press room right now."* plus `Try again`.
- No plans yet (signed in, never run): *"No edition yet."* plus `Run the agent`.

---

## 9. Accessibility
- Body text contrast: `ink` on `paper` is high contrast. **Verify every token pair with a contrast checker before shipping** (target WCAG AA 4.5:1 for text, 3:1 for UI). Use `vermilion-ink` instead of `vermilion` for small text.
- Colour is never the only signal: FDR also has a number tooltip and home/away casing, flags have text codes, and gains have a +/− sign.
- Pitch tokens are buttons with `aria-label` like "Haaland, forward, Man City, captain, 8.1 projected points, next fixture Brentford home".
- Agent progress uses `role="status"` with `aria-live="polite"` and announces each stage change.
- All interactive targets are at least 44×44px. Visible focus ring everywhere.

## 10. Implementation notes
- Load fonts with `next/font/google`: `Fraunces({ axes: ['opsz','SOFT'] })`, `Newsreader({ axes: ['opsz'], style: ['normal','italic'] })`, `Instrument_Sans`.
- Expose the domain tokens as Tailwind theme colours: `paper`, `ink`, `vermilion`, `racing`, `ochre`, `claret`, `fdr-1`…`fdr-5`, `pos-gkp`…`pos-fwd`.
- Override shadcn `Card` to remove shadow and rounding and add a `border-t` rule. Override `Tabs` per 7.5 and `Slider` per 7.12.
- Keep pitch markings as one inline SVG component (`<PitchMarkings variant="programme" />`).
