# FPLBud UI Design Spec 04: "Sticker Album"

> A playful, retro, neo-brutalist direction inspired by 90s football sticker albums and kit design. Players are stickers, transfers are swaps, chips are shiny collectibles, and locked features are sealed packs. Loud, tactile and fun, but it still prints the numbers clearly.

Source of truth for features and data: `docs/ARCHITECTURE.md` (§2A tiers, §6A agent, §7 endpoints, §8 pages). This document only defines **how it looks and behaves**.

---

## 1. Concept

| | |
|---|---|
| **Metaphor** | A schoolyard sticker album. You open your album (your squad), the agent suggests swaps ("got, got, need"), and premium content comes in a sealed pack. |
| **Personality** | Cheerful, cheeky, high-energy, nostalgic. It talks like a mate at the playground, but the maths stays exact. |
| **Signature moves** | 1) **Hard offset shadows** (4px solid ink, no blur) on everything clickable. 2) **Sticker tokens** with a white die-cut border and a peeling corner. 3) **Kit-pattern bands** (pinstripe, halves, sash, chevrons) as section dividers. 4) A **"SWAP!" starburst** on transfers. 5) **Sealed pack** for the locked guest tabs. |
| **Avoid** | Soft shadows, blur, gradients (except the shiny chip foil, 7.9), muted greys, thin hairline UI, purple, and FPL's own green/purple. |

Design principles:
1. **Chunky and tactile.** Thick 2px ink borders, big hit areas, buttons that visibly press down.
2. **Four bold inks, plus cream.** The palette is limited like a 4-colour print run.
3. **Fun copy, honest numbers.** Personality lives in headings and microcopy. Numbers are never hidden or rounded away.
4. **Every state has a character.** Empty, loading, error and locked states each have their own playful treatment.

---

## 2. Colour

### 2.1 Core palette (light-first)

| Token | Hex | Use |
|---|---|---|
| `cream` | `#FBF3E0` | Page background (album paper) |
| `cream-dark` | `#F2E6C9` | Album "slots", insets, zebra |
| `white` | `#FFFDF8` | Sticker die-cut border, cards |
| `ink` | `#1B1B1B` | Text, borders, shadows |
| `ink-soft` | `#4D4A44` | Secondary text |
| `ink-faint` | `#8E887C` | Captions, disabled |
| `cobalt` | `#2340C8` | Primary: CTAs, links, active tab, focus |
| `cobalt-dark` | `#172C93` | Pressed |
| `tomato` | `#EE4B2B` | Highlight: captain, SWAP, deadline, hits |
| `mustard` | `#F4B400` | Secondary highlight: estimates, warnings, "consider" |
| `pitch` | `#1E9E6A` | Positive: gains, available chips, play now |
| `pitch-dark` | `#137A50` | Pitch stripes, positive text on cream |
| `bubblegum` | `#FF9EC4` | Fun accent: badges, the confetti in celebrations only |

### 2.2 Dark mode ("Album at night")
Optional toggle.

| Token | Dark hex |
|---|---|
| `cream` (bg) | `#1C1A17` |
| `cream-dark` | `#26231E` |
| `white` (cards) | `#2E2A24` |
| `ink` (text) | `#FBF3E0` |
| borders and shadows | `#0B0A09` (shadows) and `#FBF3E0` (borders, 2px) |
| `cobalt` | `#6B82FF` |
| `tomato` | `#FF6B4D` |
| `mustard` | `#FFC93C` |
| `pitch` | `#3FD196` |

### 2.3 Domain colours

**Positions** use kit-style band colours on the sticker's top strip, plus a text code:

| Position | Band | Text on band |
|---|---|---|
| GKP | `mustard` | ink |
| DEF | `pitch` | white |
| MID | `cobalt` | white |
| FWD | `tomato` | white |

**FDR 1–5** uses "sticker rarity". These are pill-shaped mini stickers with a 2px ink border and the number printed:

| FDR | Fill | Text | Label (tooltip) |
|---|---|---|---|
| 1 | `pitch` | white | "Easy peasy" |
| 2 | `#8FD3A9` | ink | "Kind" |
| 3 | `cream-dark` | ink | "Fair" |
| 4 | `#F59A7E` | ink | "Tough" |
| 5 | `tomato` | white | "Nightmare" |

Home fixtures get a small house glyph (⌂) before the opponent code. Away fixtures get a bus glyph. Use icon-set equivalents, not emoji.

**Flags** are "damaged sticker" treatments:
- 75%: a mustard corner tag `75%`
- 50% / 25%: a mustard tag plus the sticker tilted 3°
- out (`i`, `s`, `u`, 0%): a tomato "torn" diagonal tape across the sticker reading `OUT`, `INJURED`, `BANNED` or `GONE`, with the sticker at 50% saturation

### 2.4 shadcn/ui variable mapping

```css
:root {
  --background: 43 82% 93%;       /* cream */
  --foreground: 0 0% 11%;         /* ink */
  --card: 40 100% 99%;            /* white */
  --card-foreground: 0 0% 11%;
  --popover: 40 100% 99%;
  --popover-foreground: 0 0% 11%;
  --primary: 230 70% 46%;         /* cobalt */
  --primary-foreground: 40 100% 99%;
  --secondary: 42 64% 87%;        /* cream-dark */
  --secondary-foreground: 0 0% 11%;
  --muted: 42 64% 87%;
  --muted-foreground: 40 5% 29%;
  --accent: 10 85% 55%;           /* tomato */
  --accent-foreground: 40 100% 99%;
  --destructive: 10 85% 55%;
  --destructive-foreground: 40 100% 99%;
  --border: 0 0% 11%;             /* borders are ink */
  --input: 0 0% 11%;
  --ring: 230 70% 46%;
  --radius: 14px;
}
```

---

## 3. Typography

| Role | Font (Google Fonts) | Notes |
|---|---|---|
| Display | **Bricolage Grotesque** (opsz 96, wght 700–800, width 75 condensed for big headlines) | Chunky, characterful headlines |
| Body / UI | **Bricolage Grotesque** (opsz 14, wght 400–600) | Same family at text optical size, for cohesion |
| Numbers | **Azeret Mono** (500, 700) | Stats, prices, projections, countdown |

| Token | Size / LH | Font | Use |
|---|---|---|---|
| `shout` | 4.5 / 0.9, tracking −0.03em | Bricolage 800, wdth 75 | Landing headline |
| `h1` | 2.5 / 1 | Bricolage 800 | Page titles |
| `h2` | 1.625 / 1.1 | Bricolage 700 | Section titles |
| `tag` | 0.75 / 1, UPPERCASE, tracking 0.08em | Bricolage 700 | Sticker tags, badges |
| `body` | 1 / 1.55 | Bricolage 400 | Prose |
| `ui` | 0.9375 / 1.3 | Bricolage 600 | Buttons, labels |
| `num-xl` | 3.5 / 1 | Azeret Mono 700 | Gain vs roll |
| `num` | 1 / 1 | Azeret Mono 500 | Inline numbers |

Wordmark: `FPLBud` in Bricolage 800 condensed, cobalt with a 3px ink stroke (`paint-order: stroke`) and a 4px ink offset shadow, inside a tomato starburst on the landing page only.

---

## 4. Layout, spacing and shape

- **Grid:** 12 columns, max width 1200px, 24px gutters, 24px page padding (16px on mobile).
- **Spacing:** 4, 8, 12, 16, 24, 32, 48, 64.
- **Radius:** 14px cards, 10px buttons and inputs, 999px pills and FDR stickers. Stickers are 12px.
- **Borders:** 2px `ink` on every card, input, button and sticker. No hairlines.
- **Shadows** (hard offset only):
  - `shadow-sm`: `3px 3px 0 #1B1B1B`
  - `shadow-md`: `5px 5px 0 #1B1B1B`
  - `shadow-lg`: `8px 8px 0 #1B1B1B` (modals, the recommended plan)
  - Pressed: shadow drops to `0 0 0` and the element translates `(3px, 3px)`.
- **Tilt:** decorative elements (tags, stamps, starbursts) can rotate between −4° and 4°. Data blocks never tilt.
- **Kit-pattern dividers:** 16px-tall bands between page sections, chosen from four CSS patterns: pinstripes (`repeating-linear-gradient` ink on cream, 2px/10px), halves (cobalt | tomato), sash (diagonal mustard band), and chevrons. Use a different one per section, deterministically.
- **Breakpoints:** 640 / 768 / 1024 / 1280.

---

## 5. Iconography and imagery

- Icons: **Phosphor "Bold"** weight, 22px, ink.
- **Sticker token:** a 64×80 card with a 4px white die-cut border, a 2px ink outline and `shadow-sm`. The top 14px band is the position colour with the club code. The centre shows a **generated shirt**: a simple SVG shirt in a kit pattern (stripes, halves, plain), with colours taken from a small per-club palette map. If a club isn't mapped, use plain cream-dark with an ink outline. Below the shirt: surname, `proj`, and the FDR sticker.
- Peel corner: the bottom-right corner of the sticker is folded (a CSS clip plus a small triangle in cream-dark) on hover.
- Mascot (optional, for empty and error states only): a simple ball character with eyes, drawn in 2px ink lines, named "Buddy". Keep it to 3 to 4 poses: waving, thinking, sad, celebrating.

---

## 6. Motion

Bouncy, physical, quick.
- Durations: 120ms (press), 220ms (hover and lift), 380ms (sticker slap), 600ms (pack open).
- Springs: entrance `cubic-bezier(0.34, 1.56, 0.64, 1)` (overshoot). Exit `ease-in`.
- **Hover lift:** cards move `translate(-2px, -2px)` and the shadow grows from sm to md.
- **Sticker slap:** when a plan reveals, new IN stickers scale 1.15 → 1 with a −6° to 0° rotation. Stagger 60ms.
- **SWAP starburst** pops in (scale 0 → 1.1 → 1) at the transfer arrow.
- **Celebration:** the first time a user sees a plan with gain ≥ 5, a short bubblegum, mustard and cobalt confetti burst runs for 900ms. It's shown once per run and never under reduced motion.
- `prefers-reduced-motion`: no overshoot, rotation, confetti or slap. Opacity only, 120ms.

---

## 7. Components

### 7.1 Header
- 68px tall, cream background with a 2px ink bottom border. Wordmark at the left.
- Centre: a **deadline ticket**, a tomato pill with a 2px ink border and `shadow-sm`, reading `GW7 DEADLINE · 2d 14h 06m` in Azeret Mono with white text. Under 2 hours it gently wiggles every 10s (±2°, disabled under reduced motion).
- Nav: pill buttons, where the active one has a cobalt fill and white text.
- Avatar: a circle with a 2px ink border and `shadow-sm`. Guests see a `Sign in` cobalt button instead.
- Mobile: bottom nav with 3 chunky tabs and icons.

### 7.2 Team ID input
- A big white input, 64px tall, 2px ink border, `shadow-md`, in Azeret Mono 700 at 1.75rem with placeholder `1234567`.
- The attached button `Open album →` has a cobalt fill.
- Help: a "Where's my ID?" mustard sticky note (rotated −2°, `shadow-sm`) showing the URL `fantasy.premierleague.com/entry/` **`1234567`** `/event/6`, with the number circled in tomato.
- 404: the input shakes (6px, 300ms), the border turns tomato, and Buddy (sad) appears with *"Can't find that team! Double-check the number in your Points page URL."*

### 7.3 Pitch view ("The Album Page")
- A green album page: `pitch-dark` and `pitch` stripes (horizontal, 10 stripes), cream pitch lines at 2px, a 2px ink outer border, a 14px radius and `shadow-md`.
- Stickers are placed by formation, GKP at the bottom.
- **Captain:** a tomato circular `C` badge (24px, 2px ink border) slapped at the top-right, plus a tomato die-cut border instead of white. **Vice:** a cobalt `V` badge.
- **Transferred in:** a `NEW!` tomato starburst tag at the top-left.
- **Bench ("Swaps pile"):** a cream-dark tray below with a 2px ink border and the title `Subs bench`, holding four smaller stickers (52×66) with order badges `1`–`4`.

### 7.4 Context panel ("Album Stats")
A white card with a 2px border and `shadow-md`, holding a grid of **stat stickers** (each a small rounded card with a 2px border):
- `Bank` **£1.4m** · `Free transfers` **1** · `Team value` **£101.2m**
- Estimates get a mustard `≈ guess` tag stuck on the corner. Its tooltip reads: *"Our best guess. FPL keeps this one secret. Tap Edit to fix it."*
- **Chips ("Shinies")**: four collectible badges (see 7.9 for the foil). Available = full colour foil. Used = greyscale with a `USED` stamp. Expiring = a mustard ribbon `Use by GW19!`.
- **Flags:** a row of mini damaged stickers with player name, status and news.
- Caveat note on a mustard sticky note: *"Heads up: transfers you've already made for GW7 stay hidden until the deadline. Fix your squad with Edit."*
- `Edit` secondary button opens the overrides sheet (FT, bank, squad).

### 7.5 Horizon tabs
- Three chunky tab buttons that sit **on top of** the plan card like folder tabs: `Next GW`, `Next 3`, `Next 5`.
- Inactive: cream-dark fill, 2px ink border with no bottom border. Active: white fill matching the card, cobalt text, and a cobalt 4px top band.
- Each tab carries a tiny Azeret Mono gain pill, `+6.4`, on a pitch fill.
- Guest-locked tabs show a padlock and a `SEALED` tag.

### 7.6 Plan card
A white card with a 2px border and `shadow-lg` for the recommended plan.

1. Top row: a tilted tag, `Buddy's pick!` (cobalt) or `Plan B` (cream-dark). On the right, an h2 summary: *"One swap, no hit"* or *"Stick! Roll your transfer"*.
2. **Gain block:** a pitch-filled rounded box containing `+6.4` in `num-xl` white with an ink stroke, and the label `points vs rolling`. Next to it, a hits sticker (tomato `−4 hit`, or a pitch `No hit` with a tick) and bank after (`£0.3m left`).
3. **Swap rows** (7.7).
4. **Captain row:** two stickers side by side with large C and V badges, and a speech-bubble chip *"1.9 pts clear"*.
5. **Buddy says** (7.8).
6. **Shinies to play** (7.9).
7. `Other plans`: an accordion of small cards with the summary, gain, hits and a `Try it` button that swaps the pitch.

### 7.7 Swap row ("Got → Need")
```
┌──────────────────────────────────────────────────────────────┐
│ [sticker SAKA]   ✸SWAP!✸   [sticker PALMER]      +£0.5m      │
│  GOT · £10.1m ≈                NEED · £10.6m                  │
│ ──────────────────────────────────────────────────────────── │
│ Why: [Form +0.12] [Fixtures +0.31] [xGI +0.08] [Home −0.05]  │
└──────────────────────────────────────────────────────────────┘
```
- The OUT sticker is desaturated and slightly tilted (−3°), labelled `GOT`. The IN sticker is full colour and labelled `NEED`.
- The SWAP starburst is a tomato 12-point star, 56px, with a 2px ink stroke and white text.
- The "Why" chips are pills with a 2px border: pitch fill for positive, tomato tint `#FCD3C8` for negative, with Azeret Mono values.
- For N=3/5, `Per gameweek` expands a mini bar chart: chunky 16px bars with a 2px ink border and pitch fill, with GW labels below.

### 7.8 "Buddy says" (explanation)
- A speech bubble: white fill, 2px ink border, a tail pointing to a small Buddy avatar (thinking pose) on the left, and `shadow-sm`.
- The explanation is in Bricolage 400, 1rem/1.6, max 62ch. Player names are bold, numbers are in Azeret Mono.
- `reason_codes` appear as tiny stickers below: `Fixture swing`, `xGI upgrade`, `Hit not worth it`.

### 7.9 Chip tip ("Shiny")
- The chip badge is a 56px circle with a **holographic foil** fill. This is the only gradient in the system: `conic-gradient(from 0deg, #FF9EC4, #F4B400, #1E9E6A, #2340C8, #FF9EC4)` at 35% opacity over white, with a 2px ink border. It slowly rotates on hover (4s). Reduced motion: static.
- Chip initials in the centre: `WC`, `FH`, `BB`, `TC` in Bricolage 800.
- Recommendation:
  - `play_now`: a pitch card with `Play Bench Boost NOW!` and `+13.2 pts`.
  - `consider_gw_X`: a mustard card with `Save Triple Captain for GW9`.
  - `hold`: a cream-dark compact row, `Keep Free Hit in the album (+4.1 isn't enough)`.
- Expiring: a tomato ribbon across the badge, `Use by GW19!`.

### 7.10 Agent progress ("Filling the album")
- Six **empty sticker slots** in a row (dashed 2px ink border, cream-dark fill, a number in the centre), labelled underneath:
  1 `Team sheet` (context) · 2 `Next GW` (horizon_1) · 3 `Next 3` (horizon_3) · 4 `Next 5` (horizon_5) · 5 `Shinies` (chips) · 6 `Buddy's notes` (explain).
- As each stage completes, a sticker **slaps** into its slot (7.6 motion) with a coloured shirt illustration. The current slot wobbles gently.
- A chunky progress bar sits below: 16px tall, 2px ink border, with a pitch fill bound to `progress` and a pinstripe pattern on the fill.
- Microcopy rotates by stage: "Checking your squad…", "Crunching next week…", "Looking 3 weeks ahead…", "Looking 5 weeks ahead…", "Polishing your shinies…", "Buddy's writing it up…".
- **Failed:** the current slot shows a torn sticker and sad Buddy. Copy: *"Oops, the agent tripped over. Want another go?"* plus the `error` text in small ink-soft, and a `Try again` cobalt button.
- **Slow (over 2 minutes):** *"This one's taking ages! We'll keep going. Pop back in a minute."*

### 7.11 "Plans updated" banner
- A mustard banner with a 2px ink border and `shadow-sm`, slid down below the header with a bounce, plus a `NEW!` tomato starburst.
- Copy: *"Fresh plans! Updated after late injury news."* (reason from trigger). Buttons: `Show me` (cobalt) and `×`.

### 7.12 Weight sliders ("Build your formula")
- Each metric is a white card row with a 2px border: the metric name (Bricolage 700), a one-line plain-English blurb, the slider, the weight `0.30` and the share pill `30%`.
- Slider: a 12px-tall track with a 2px ink border and cream-dark fill, filled cobalt up to the value. The thumb is a 28px ball icon (a simple pentagon-pattern football in white and ink) with `shadow-sm`. It rotates as it moves (rotation ∝ value), disabled under reduced motion.
- At the top, a **"recipe" stacked bar** shows each metric's share as chunky colour segments (cobalt, tomato, mustard, pitch, bubblegum, `#7FC8F8` sky, `#B08968` tan), each with a 2px ink divider and a label.
- Optional metrics are in a `Bonus ingredients` section with chunky toggles (40×24, ink border, cobalt when on). Turning one on bounces the slider to 0.15.
- Live preview pill next to `Save & re-run`: `Preview: +6.8 (was +6.4)`.
- **Guest:** the sliders are covered by a **sealed-pack** overlay (see 7.13), smaller variant, labelled *"Sign in to mix your own formula"*.

### 7.13 Locked horizon overlay ("Sealed pack")
- The Next 3 and Next 5 panels render a placeholder plan blurred (`filter: blur(7px)`) under a cream 50% scrim.
- In the centre is a **sticker-pack illustration**: a tall foil packet, cobalt with a tomato band, with `FPLBud 5-WEEK PLAN` printed on it, a tear notch at the top, 2px ink and `shadow-lg`.
- Below: the h2 *"Unlock your 5-week plan"*, body *"Sign in with Google to unlock your 5-week plan."* and a `Sign in with Google` button.
- On hover the pack wiggles. After sign-in, the first visit to the dashboard plays a 600ms **pack-open** animation (the top tears off and the plan slides up) once.

### 7.14 Buttons
| Variant | Style |
|---|---|
| Primary | Cobalt fill, white text, Bricolage 700, 48px, 10px radius, 2px ink border, `shadow-sm`. Hover: lift. Active: pressed (shadow 0, translate 3px). |
| Secondary | White fill, ink text, same border and shadow. |
| Fun / CTA | Tomato fill, white text. For the landing CTA only. |
| Ghost | No border, ink text. Hover: underline 2px offset 3px. |
| Destructive | White fill, tomato text and border. Hover: tomato fill, white text. |
| Google | White fill, ink text, 2px ink border, `shadow-sm`, official Google "G". Keep the Google mark unaltered. |

Focus: a 3px cobalt outline with 3px offset, *plus* the hard shadow, so focus is very visible.

### 7.15 Player explorer ("Sticker catalogue")
- **Two views**, toggled in the toolbar:
  - **Grid** (default on mobile): sticker cards (96×120) with name, club, price, `proj`, and the next 3 FDR stickers.
  - **Table** (default on desktop): white card with a 2px border. Header on cream-dark with tag-style labels. Rows are 52px with 1px ink dividers at 20% (the only thin line allowed, for density). Metric scores show as 5-dot ratings (filled cobalt dots).
- Sort: chunky pill select. Filters: position pills, club select, a price slider using the ball thumb, and a horizon pill group (1–6).
- Player detail: a modal "sticker back". It flips the sticker 180° on the Y axis (320ms; reduced motion = cross-fade) to reveal stats on the back: a metric × GW grid with coloured cells and a match history list.

### 7.16 Feedback
- Toasts: a top-right white card with a 2px border and `shadow-md`. A coloured left band shows status. Auto-dismiss after 4s.
- Skeletons: cream-dark blocks with 2px **dashed** ink borders (empty slots). They don't shimmer.
- 429: Buddy (thinking) with *"Slow down, gaffer! Too many tries. Give it a minute."*

---

## 8. Pages

### 8.1 `/` Landing
- Hero on cream with a giant `shout` headline: **"Got, got, need."** and a sub: *"FPLBud swaps, captains and chips for your Fantasy team. Free, fast, and a bit cheeky."*
- To the right (or below on mobile), a **fanned stack of 5 sample stickers** with a SWAP starburst between two of them.
- The Team ID input (7.2) sits under the headline. Then `or` and a secondary button `Sign in with Google for the full album`.
- A sash kit-pattern divider.
- "How it works" as three numbered sticker cards: `1 Open your album` (import), `2 Score every player`, `3 Get your swaps`.
- Tier comparison: two cards, `Guest: free preview` and `Signed in: full album`, with a feature checklist. The signed-in card has a tomato `BEST` starburst.

### 8.2 `/try/[entryId]`
- Header: tag `Preview`, h1 = team name, manager below.
- `lg`: the album page (pitch) in cols 1–7, Album Stats in cols 8–12.
- Below: folder tabs plus the plan card. Next GW is open, and Next 3/5 are sealed (7.13).
- Formula builder in its sealed state.

### 8.3 `/login`
A centred white card (440px, `shadow-lg`) with waving Buddy, the h2 *"Sign in to save your album"*, the Google button and small print: *"We never ask for your FPL password. Google just remembers your team for you."*

### 8.4 `/auth/callback`
Buddy bouncing (a 3-frame loop) with *"Letting you in…"*.

### 8.5 `/onboarding`
- h1 *"What's your team ID?"* and the input (7.2) with the sticky-note help.
- On lookup, a **team sticker card** slaps in: team name, manager, overall rank, and GW points. Buttons: `That's me!` (primary) and `Nope, try again` (ghost).
- Confirm, then go to the dashboard, where Filling the album shows immediately.

### 8.6 `/dashboard`
```
Header (deadline ticket)
[Plans updated banner]
┌ h1 TEAM NAME · tag GW7 ─────────────────────── [Re-run agent ↻] ┐
├─────────── cols 1–7 ─────────────┬───────── cols 8–12 ───────────┤
│ Album page (pitch, active plan)  │ Folder tabs                    │
│ Subs bench tray                  │ Plan card: gain block, swaps,  │
│                                  │ captain, Buddy says, shinies,  │
│ Album Stats                      │ other plans                    │
└──────────────────────────────────┴────────────────────────────────┘
```
- While running: the right column shows Filling the album (7.10). The pitch shows the current squad.
- Mobile order: folder tabs (sticky), gain block, album page, swaps, captain, Buddy says, shinies, album stats.
- `Re-run agent`: a secondary button with a rotating arrows icon. While running it's disabled and shows `Working…`. On 429 a toast reads *"You've re-run loads this hour! Try again later."*

### 8.7 `/settings`
Cards stacked vertically, separated by kit-pattern dividers:
1. **Build your formula** (7.12), with `Save & re-run`.
2. **Defaults:** horizon as three chunky pills (`1`, `3`, `5` weeks), and max hits as a big stepper (`−` [ 1 ] `+`) with Azeret Mono.
3. **Your team:** a team sticker card with `Change team`.
4. **Look:** Day / Night album toggle.
5. **Account:** `Sign out` (secondary) and `Delete account` (destructive). The confirmation modal shows sad Buddy, the text *"This bins your profile, saved team and plans. No undo!"*, and requires typing `DELETE`.

### 8.8 `/players`
The Sticker catalogue (7.15). A banner above reads *"Sorted by your formula"* or *"Sorted by the default formula. Sign in to make your own!"*.

### 8.9 `/how-it-works`
- An "album guide": each section is a white card with a kit-band header in a different pattern.
- Formulas sit in cream-dark boxes in Azeret Mono with plain-English captions underneath.
- Hit-margin and chip-threshold tables use the explorer table styling.
- Buddy pops up in the margins with tips (non-essential, `aria-hidden`).

### 8.10 Error and empty states
- 404: Buddy (sad) holding a torn sticker, *"This page isn't in the album."*, and `Back home`.
- API down: *"The album's stuck shut. We can't reach our server."* plus `Try again`.
- No plans yet: an empty album page with dashed slots and the button `Fill my album` (run agent).

---

## 9. Accessibility
- Thick borders and hard shadows help structure, but **verify text contrast** for white on `pitch`, white on `tomato` and ink on `mustard`. Target WCAG AA. If white on pitch fails at body size, use it only for large or bold text, or switch to `pitch-dark`.
- Colour is never the only signal: positions have text codes, FDR prints numbers plus tooltip labels, flags have text tape, and gains carry a sign.
- Tilt, wobble, rotation, confetti, foil spin and pack-open are all disabled under `prefers-reduced-motion`.
- Buddy and decorative illustrations are `aria-hidden`. All state messages are real text.
- Hit targets are at least 48px. The focus outline plus hard shadow is always visible.
- The sticker flip modal traps focus, closes on `Esc`, and returns focus to the row.

## 10. Implementation notes
- Fonts with `next/font/google`: `Bricolage_Grotesque({ axes: ['opsz','wdth'] })`, `Azeret_Mono`.
- Tailwind theme: colours `cream`, `cream-dark`, `ink`, `cobalt`, `tomato`, `mustard`, `pitch`, `bubblegum`; `boxShadow` tokens `hard-sm`, `hard-md`, `hard-lg`; and pattern utilities `bg-kit-pinstripe`, `bg-kit-halves`, `bg-kit-sash`, `bg-kit-chevron`.
- Override shadcn primitives to use `border-2 border-ink shadow-hard-sm`. Buttons add `active:translate-x-[3px] active:translate-y-[3px] active:shadow-none`.
- `<Sticker player={...} size="md" state="captain|vice|in|flagged" />` is the core reusable component across pitch, swaps, explorer and progress.
- Club kit colours: a small static map `clubKits[teamCode] = { primary, secondary, pattern }`. Keep it in a design-tokens file, not hard-coded inside components.
