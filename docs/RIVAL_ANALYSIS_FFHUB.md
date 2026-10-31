# Rival analysis: Fantasy Football Hub (fantasyfootballhub.co.uk)

*Draft 1, 31 Oct 2026 (Sydney time). Written for FPLBud product planning. Read-only research: FFH's own pages and help centre, the Google Play listing, Trustpilot, and r/FantasyPL. No FFH content, wording or branding is reused in the FPLBud specs.*

Companion specs:
- [`FEATURE_SPEC_AI_TRANSFERS.md`](FEATURE_SPEC_AI_TRANSFERS.md): AI transfer recommendations, plus the predicted-points model and team rating behind them.
- [`FEATURE_SPEC_TEAM_PLANNER.md`](FEATURE_SPEC_TEAM_PLANNER.md): multi-gameweek team and chip planner.

---

## 1. TL;DR

- **FFH is almost entirely paywalled.** There are three annual plans (Starter, Pro, Ultra), no free trial and no free tool tier. The one exception is a free **AI Team Rating**, which asks for your email. FFH uses it to sell AI Transfers.
- **The two features people actually pay for:**
  1. **AI Transfers with Predicted Points.** These are personalised transfer picks driven by FFH's own points predictions.
  2. **The My Team / Team & Chip Planner.** This shows your squad several gameweeks ahead, lets you model future transfers and chips, and shows predicted points for each gameweek.
- **Why these two:** they come up far more often than anything else in real-user evidence (Trustpilot reviews, r/FantasyPL threads). FFH's own marketing leads with them too. Both are in the cheapest tier (Starter).
- **The FPLBud opportunity:** user complaints are mostly about **opaque, inaccurate predictions and "black box" AI advice**, plus site reliability. FPLBud already has a deterministic, explainable optimiser and a 1/3/5-GW agent. A **backtested points model with published accuracy** and a **true multi-period planner** would beat FFH where its users say it is weakest.

---

## 2. Plans and prices (as of 31 Oct 2026, Sydney)

### 2.1 Live prices from FFH's own join page

Source: https://www.fantasyfootballhub.co.uk/join, rendered on 31 Oct 2026. The page geo-localises prices, and it showed AUD. It also had a "Last chance: 50% off every plan" banner.

| Plan | Shown price (50% off) | Struck-through price | Billing | Approx. yearly charge (derived: monthly × 12) |
|---|---|---|---|---|
| Starter | **A$5.18/mth** | A$10.36/mth | billed yearly | ≈ A$62.16 |
| Pro ("Most Popular") | **A$8.30/mth** | A$16.60/mth | billed yearly | ≈ A$99.60 |
| Ultra | **A$31.19/mth** | A$62.38/mth | billed yearly | ≈ A$374.28 |

### 2.2 GBP prices from a third party

Source: fploracle.team, "Best AI tools for FPL 2026/27" (https://fploracle.team/blog/best-ai-tools-for-fpl-2026-27). Verified by them in Sept 2026, while a 50% promotion was running.
- Starter: £4.98/mth (£59.76/yr)
- Pro: £7.98/mth (£95.76/yr)
- Ultra: £29.98/mth (£359.76/yr)

All are billed yearly, and there is no free tier.

### 2.3 Terms

From the landing page (https://www.fantasyfootballhub.co.uk/landing/LTFPL):
- **No free trial.** Plans are "annual and billed today".
- **Mini-League Promise.** New paying members get a refund if they *"follow the AI's recommendations through the season"* and don't win their named mini-league. Terms apply.
- Renewal can be cancelled at any time. Access runs to the end of the paid period.

### 2.4 What each tier includes

Sources: the /join comparison table (rendered 31 Oct 2026); Freshdesk "differences between tiers" articles 103000409131 and 103000113576 (both modified 13 Aug); the homepage FAQ.

| | Free (email) | Starter | Pro | Ultra |
|---|---|---|---|---|
| AI Team Rating | ✅ ("free and needs no card details"; email required) | ✅ | ✅ | ✅ |
| **Recommended AI transfers** | – | ✅ | ✅ | ✅ |
| **My Team predicted points** | – | ✅ | ✅ | ✅ |
| **Team and chip planning** | – | ✅ | ✅ | ✅ |
| Live rank / live mini-leagues / price changes | – | ✅ | ✅ | ✅ |
| Discord community | – | ✅ | ✅ | ✅ |
| AI Teams of the week, expert team reveals | – | – | ✅ | ✅ |
| OPTA stats package, Predicted Points Tool (all players), player comparison, fixture analyser, player profiler | – | – | ✅ | ✅ |
| 300+ Pro articles, team news, WhatsApp communities, Ben Crellin's planning sheet | – | – | ✅ | ✅ |
| Monthly personalised expert review, Ultra WhatsApp, monthly Zoom, end-of-season meet-up | – | – | – | ✅ |

**Free versus paid in practice.** Apart from the team rating and some editorial articles, everything is paid. On r/FantasyPL in Jul 2025, a user said FFH had *"removed all of this for free use"*: they had previously used predicted points and the forward planner for free ([1m8apu1](https://www.reddit.com/r/FantasyPL/comments/1m8apu1/what_websites_to_use/)).

---

## 3. Evidence: which features users actually use and pay for

**Method.** Following Daniel's steering, user evidence outweighs pricing-page order. I hand-coded every feature mention in the user sources I could read (Reddit threads, Trustpilot review extracts and Trustpilot's AI review summaries), then counted the **number of distinct sources** mentioning each feature. Praise and complaints both count, because both show what people engage with.

### 3.1 Sources

| # | Source | Date | What users talk about (feature mentions) |
|---|---|---|---|
| R1 | [r/FantasyPL "Fantasy Football Hub"](https://www.reddit.com/r/FantasyPL/comments/1fsxc9s/fantasy_football_hub/) | Sep–Dec 2024 | OP asks how reliable "**predicted points** and price predictions" are. "**AI Team** had a ranking of 4 million". "My team was **rated 98/100**… below average". A friend "only follows FFH's **AI's advice**". "The **expected points** metric can be used as a good baseline". "Eze had high **predicted points**". "the **AI transfers** – for 5 game weeks now it say[s]…" (no transfers) |
| R2 | [r/FantasyPL "Is Fantasy Football Hub worth it?"](https://www.reddit.com/r/FantasyPL/comments/1eksnq8/is_fantasy_football_hub_worth_it/) | Aug 2024 | **AI suggestions** "always brutal"; FPLReview's free **prediction model** recommended instead; locked tools slow |
| R3 | [r/FantasyPL "Is FPL Hub a scam…"](https://www.reddit.com/r/FantasyPL/comments/1ephg5q/is_fpl_hub_a_scam_meaning_do_they_really_help/) | Aug 2024 | "The **AI transfers** are shit imo"; data-leak reputation; money-back offer complaints |
| R4 | [r/FantasyPL "What websites to use"](https://www.reddit.com/r/FantasyPL/comments/1m8apu1/what_websites_to_use/) | Jul 2025 | "I could see some **predicted points** while also **going forward in time to see how my team would shape up in the future**" (the planner). Replies suggest free **planners** (fpl.team) |
| R5 | [r/FantasyPL "Alternative to hub and scout"](https://www.reddit.com/r/FantasyPL/comments/1mq6oq1/alternative_to_hub_and_scout/) | Aug 2025 | Wants "**underlying data**, a decent **fixture ticker** and a **planner** to check how your team looks on future gameweeks" |
| R6 | [r/FantasyPL "Fantasy football hub ad on MNF?"](https://www.reddit.com/r/FantasyPL/comments/1mtuy6m/fantasy_football_hub_ad_on_mnf/) | Aug 2025 | "unless you're just going to **let their model pick your transfers**". "Hub is one of the worst of the **models**". "spurning the Hub **AI template**" |
| R7 | [r/FantasyPL "Fantasy Football Hub Problems"](https://www.reddit.com/r/FantasyPL/comments/1mc7o2v/fantasy_football_hub_problems/) | Jul 2025 | Reliability, support, login and cancellation problems (no specific feature) |
| R8 | [r/FantasyPL "Player points projections"](https://www.reddit.com/r/FantasyPL/comments/1k702lz/player_points_projections/) | Apr 2025 | Looking for free **points projections** (multi-GW), named as the paid thing to replace |
| T1 | [Trustpilot review](https://www.trustpilot.com/review/fantasyfootballhub.co.uk?page=10) | 2025 | "The **AI transfers and predicted points** section were instrumental… I got some of it wrong by… not listening to AI. But I still won the mini league" |
| T2 | [Trustpilot review](https://uk.trustpilot.com/review/fantasyfootballhub.co.uk?page=7) | 26 May 2025 | "The **team planner, AI transfers, and player point predictions**… a huge help in strategizing week-to-week transfer plans" |
| T3 | [Trustpilot review](https://www.trustpilot.com/review/fantasyfootballhub.co.uk?page=10) | 27 May 2025 | "The AI tools, especially the **'My Team' planner and Points Predictor**" |
| T4 | [Trustpilot review (negative)](https://uk.trustpilot.com/review/fantasyfootballhub.co.uk) | 2025 | "**points predicting**… so off the mark"; "can't look at past player stats, only predictions"; but likes "the format that shows your **squads players at a glance for next 3 weeks**" (planner) |
| T5 | [Trustpilot review (negative)](https://uk.trustpilot.com/review/fantasyfootballhub.co.uk) | 2025 | "Player potential **points** not really accurate, some late **team reveals**" |
| T6 | Trustpilot AI review summaries ([main](https://uk.trustpilot.com/review/fantasyfootballhub.co.uk), [p7](https://uk.trustpilot.com/review/fantasyfootballhub.co.uk?page=7), [p8](https://www.trustpilot.com/review/fantasyfootballhub.co.uk?page=8)) | 2025–26 | "**point predictions, player comparisons**, and expert strategies". "**plan transfers**, and offer **player stats**". "**AI-driven suggestions**". "**algorithm-predicted points, team planner, and player comparison**". Bugs and app freezes. Trustpilot rating about 4.7 from about 420+ reviews (counts differ by page) |

### 3.2 How often each feature is mentioned (distinct sources out of 14)

| Feature cluster | Sources mentioning it | Count |
|---|---|---|
| **Predicted points / points model** | R1, R2, R4, R6, R8, T1, T2, T3, T4, T5, T6 | **11** |
| **AI transfers / AI team / AI rating** (the AI picks for you) | R1, R2, R3, R6, T1, T2, T3, T6 | **8** |
| **Planner** (future GWs, team & chip planning, 3-GW view) | R4, R5, T2, T3, T4, T6 | **6** |
| Player comparison / stats / OPTA | R5, T4 (absence of past stats), T6 | 3 |
| Expert team reveals / articles | T5, T6 | 2 |
| Price-change predictions | R1 | 1 |
| Live rank | (none in the sample; only FFH marketing) | 0 |
| Reliability / login / cancellation (not a feature) | R2, R3, R7, T6 | 4 |

### 3.3 FFH's own positioning agrees

- The homepage's three-step pitch is: (1) rate your team with AI, (2) AI Transfers "picks the best move for your team", (3) live points.
- The Starter card on /join promises "AI transfers tailored to your team" and "Predict your points every gameweek".
- The only money-back promise is conditional on following "the AI's recommendations".
- The Google Play listing leads with the "MY TEAM TOOL": AI Recommended Transfers "based on our proprietary prediction models", Customisable AI Suggestions, and "Long-Term Team Planning through interactive scenario modelling of future transfers" ([Play Store](https://play.google.com/store/apps/details?id=uk.co.fantasyfootballhub.app)).

## 4. The two features, and why

### 4.1 Feature 1: AI Transfers with Predicted Points

**What it is.** This is the reason people buy. FFH predicts each player's points per gameweek, then recommends the best transfers for *your* squad, budget and free transfers. It also scores your team out of 100. Users can lock players and ask for alternatives.

**Why it's #1.**
- Predictions are mentioned in 11 of 14 user sources, and AI transfers or the AI team in 8.
- It is the hook for both the free funnel (team rating) and the money-back promise.
- The criticism also centres here: "AI transfers are shit", "rated 98/100… below average", "points predicting… off the mark", "let their model pick your transfers". It is the feature users judge FFH on.

**Merging the two.** I treat "Predicted Points" and "AI Transfers" as one feature. The transfers are an optimiser run over the predictions, and users praise them together ("AI transfers and predicted points section").

→ Spec: **[`FEATURE_SPEC_AI_TRANSFERS.md`](FEATURE_SPEC_AI_TRANSFERS.md)**

### 4.2 Feature 2: Team and Chip Planner

**What it is.** A multi-gameweek view of your own squad. You can step forward through future GWs, draft transfers in later weeks, place chips, and see predicted points, bank and free transfers each week.

**Why it's #2.**
- It is mentioned in 6 of 14 user sources.
- The one user who explained *why* they used FFH named it, alongside predictions: "going forward in time to see how my team would shape up" (R4).
- Users looking to replace Hub ask for "a planner" first (R5).
- Even a negative reviewer kept "squads players at a glance for next 3 weeks" (T4).
- It is in Starter and is a headline Play Store feature.
- Chip planning matters more now that chips come in two sets per season.

→ Spec: **[`FEATURE_SPEC_TEAM_PLANNER.md`](FEATURE_SPEC_TEAM_PLANNER.md)**

### 4.3 Considered and not chosen

- **Pro stats tools** (OPTA stats, player comparison, fixture analyser, player profiler). Pro is labelled "Most Popular" on /join, and Trustpilot summaries mention player comparison. But users mention these much less (3 of 14) than predictions, AI transfers or the planner.
  - FPLBud can't licence OPTA data.
  - A comparison view and a model-based fixture ticker are folded into the two specs as supporting pieces.
- **Expert team reveals, articles and Ultra coaching.** These are human editorial content, not software features, and are mentioned only 2 of 14 times (once negatively). They're out of scope for a software spec.
- **Live rank / live mini-leagues.** Marketed heavily but not mentioned by users in this sample, and free alternatives (LiveFPL) are popular. It's a candidate for a later spec.

---

## 5. Where FFH is weak, and how FPLBud can beat it

| Users' complaint about FFH | FPLBud response (detailed in the specs) |
|---|---|
| Predictions "off the mark", feel stale ("working on last year's stats"), unknown accuracy | A backtested points model with a **public accuracy page** (MAE and calibration per GW and position, compared against FPL's own `ep_next`). Show the recency weighting. |
| AI is a black box ("let their model pick your transfers"); a rating of 98/100 meant nothing | Deterministic MILP with **per-metric reasons**, gain vs rolling, hit maths and uncertainty ranges. The rating is defined against an attainable optimum and shown with its parts. |
| AI said "no transfers" for 5 GWs with no explanation | Always show the **roll alternative and the threshold** that a transfer failed to clear. Users can force "best 1 transfer" anyway. |
| Can't see past stats, only predictions | Predictions sit next to recent actuals (the `player_gameweek_stats` window, plus season history). |
| Paywall on everything; no trial | Guests get value with no login. Free signed-in users get the 1/3/5 agent and a basic planner. Paid adds depth, not basics. |
| Reliability, logins, data leak, cancellation pain | Out of scope for the specs, but it's a positioning point: Google OAuth only, no FPL passwords ever stored (FPLBud uses the public team ID), and easy account deletion already exists. |

---

## 6. Unverified or caveated items

- **GBP list prices** come from a third party (fploracle, Sept 2026). FFH's /join page showed me **AUD** because of geo-localisation, so I couldn't read GBP directly. Yearly AUD totals are my arithmetic (monthly × 12), not a figure FFH displayed.
- **The 50% offer** was live on 31 Oct 2026 ("Last chance"). Its end date and normal prices after it may change.
- **Monthly billing.** Freshdesk article 103000113576 says plans are offered "either pay monthly or annually". Article 103000409131 and the landing page say annual only. /join showed only "billed yearly".
- **Whether `/predictions` has any free view.** The page renders client-side, and I couldn't confirm what a logged-out user sees.
- **Trustpilot pages blocked direct fetching (403).** The review quotes and AI summaries come from search-engine extracts of those pages. The review count differs between pages (423 vs other counts).
- **Reddit quotes** come from search extracts of the threads cited. Vote counts are as shown there.
- **The evidence sample is small** (14 sources, hand-coded, no social/X or YouTube comment mining). Relative order is clear for the top three. Exact counts are indicative only.
- **The data-leak and "scam" claims** are user allegations on Reddit. I didn't verify them, and they shouldn't be used in FPLBud marketing.
- **FFH's claims** ("AI Team outperformed 99% of players", "10,000 mini-leagues won") are their own marketing, not independently verified.
