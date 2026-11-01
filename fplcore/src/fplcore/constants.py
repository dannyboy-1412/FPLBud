DEFAULT_WEIGHTS: dict[str, float] = {
    "form": 0.30,
    "fixture": 0.25,
    "home": 0.10,
    "xgi": 0.35,
    "value": 0.15,
    "minutes": 0.15,
    "trend": 0.0,
}

OPTIONAL_METRICS = ("value", "minutes", "trend")
DEFAULT_METRICS = ("form", "fixture", "home", "xgi")
ALL_METRICS = DEFAULT_METRICS + OPTIONAL_METRICS

OPTIONAL_METRIC_ON_WEIGHT = 0.15

POSITION_IDS = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
POSITION_SHORT = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

SQUAD_SELECT = {1: 2, 2: 5, 3: 5, 4: 3}
SQUAD_MIN_PLAY = {1: 1, 2: 3, 3: 2, 4: 1}
SQUAD_MAX_PLAY = {1: 1, 2: 5, 3: 5, 4: 3}

GOAL_POINTS = {1: 6, 2: 6, 3: 5, 4: 4}

PROJ_A_FALLBACK = 1.0
PROJ_B_FALLBACK = 6.0

# Squad score places an XI on 0–10 between these percentiles of players who have a fixture.
# 0 is an ordinary XI (25th percentile, captained). 10 is a premium XI (98th percentile, captained).
SQUAD_SCORE_LOW_PERCENTILE = 25.0
SQUAD_SCORE_HIGH_PERCENTILE = 98.0

FORM_EWMA_ALPHA = 0.5
XGI_MINUTES_PRIOR = 270
TREND_DEADLINE_HOURS_FLOOR = 1.0

ENTRY_CACHE_TTL_SECONDS = 300
ENTRY_CACHE_PRUNE_SECONDS = 600
MATCH_STATS_RETENTION_ROUNDS = 8
METRIC_FORWARD_GWS = 6
DAILY_SNAPSHOT_RETENTION_DAYS = 8
AGENT_RUN_KEEP_HOURS = 24
LOG_RETENTION_DAYS = 14
# Chat is on for every signed-in user unless CHAT_ALLOWED_USER_IDS narrows it.
# The model id is the OpenRouter tool-calling model. The API key stays in the environment.
CHAT_ENABLED = True
CHAT_MODEL = "openai/gpt-6-luna"
CHAT_THREAD_RETENTION_DAYS = 90
CHAT_TRACE_RETENTION_DAYS = 14
CHAT_USAGE_RETENTION_DAYS = 35
CHAT_PROPOSAL_RETENTION_DAYS = 1
PREFILTER_PER_POSITION = 40

DC_THRESHOLD = {2: 10, 3: 12, 4: 12}
TEMPLATE_OWNERSHIP = 20.0
DIFFERENTIAL_OWNERSHIP = 10.0
INSIGHTS_MIN_MINUTES = 180
STATS_TOP_N = 10
PRICE_PRESSURE_CAVEAT = (
    "Price pressure is an estimate. FPL does not publish the price-change algorithm."
)

METRIC_LABELS: dict[str, str] = {
    "form": "Form",
    "fixture": "Fixture difficulty",
    "home": "Home/away",
    "xgi": "Expected stats",
    "value": "Value for money",
    "minutes": "Minutes security",
    "trend": "Price/ownership trend",
}

METRIC_DESCRIPTIONS: dict[str, str] = {
    "form": "Recent points blended with FPL's own form rating.",
    "fixture": "How easy the next fixtures look, from the FDR.",
    "home": "Share of upcoming fixtures played at home.",
    "xgi": "Expected goals and assists, shrunk toward the position mean.",
    "value": "Points per million of price.",
    "minutes": "How securely the player starts and completes matches.",
    "trend": "Transfer momentum and recent price movement.",
}
