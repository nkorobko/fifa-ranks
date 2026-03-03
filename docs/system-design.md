# FIFA Tracker — System Design Document

**Authors:** Noam Korobko, Claude
**Date:** 2026-02-26
**Status:** Draft — Pending Review

---

## 1. Problem Statement

Six players (Noam, Itay, Ayal, Ari, Sharon, Dori) play FIFA 26 2v2 matches daily at the office. There is currently no system to track results, measure individual skill from team outcomes, or settle arguments about who's actually the best.

The system must: log match results, derive individual player ratings from 2v2 outcomes, present weekly power rankings with trends, and be fun to use.

---

## 2. Requirements

### Functional

- **Log matches**: Record 2v2 results (teams, score, date).
- **Player rankings**: Compute and display individual skill ratings derived from team match outcomes.
- **Weekly Power Index**: A composite ranking that goes beyond raw skill — incorporating recent form, consistency, and team impact.
- **Trends & history**: Visualize rating trajectories, win rates, streaks, and head-to-head stats over time.
- **Fair team generator**: Given available players, suggest balanced 2v2 matchups.
- **Match editing**: Ability to correct or delete mislogged matches (with recalculation).
- **Weekly awards**: Automated fun awards based on weekly performance.

### Non-Functional

- **Latency**: Sub-200ms API responses (trivial at this scale).
- **Availability**: Best-effort; this is an office fun tool, not a bank.
- **Data durability**: SQLite with WAL mode + periodic backups to the Git repo.
- **Cost**: Zero. Free hosting tier + SQLite.

### Constraints

- 6 players, ~5-15 matches per day, ~25-75 per week.
- Python backend (FastAPI), SQLite storage.
- Hosted on a free tier (Railway, Render, or a machine in the office).
- Stored in a GitHub repository.

---

## 3. Architecture

```
┌──────────────────────┐        ┌──────────────────────┐       ┌────────────┐
│      Frontend        │  HTTP  │      Backend         │       │   SQLite   │
│  (HTML/CSS/JS)       │◄──────►│      (FastAPI)        │◄─────►│   (WAL)    │
│                      │        │                      │       │  fifa.db   │
│  • Dashboard         │        │  • REST API          │       └────────────┘
│  • Log Match Form    │        │  • TrueSkill Engine  │
│  • Power Rankings    │        │  • WPI Calculator    │
│  • Trend Charts      │        │  • Team Generator    │
│  • Player Profiles   │        │  • Weekly Cron Job   │
│  • Weekly Awards     │        │                      │
└──────────────────────┘        └──────────────────────┘
```

### Tech Stack

| Layer    | Choice                      | Rationale                                              |
|----------|-----------------------------|---------------------------------------------------------|
| Backend  | FastAPI (Python 3.11+)      | Async, auto-docs (Swagger), Pydantic validation.       |
| ORM      | SQLAlchemy 2.0 + alembic    | Mature, migration support, works well with SQLite.      |
| Database | SQLite (WAL mode)           | Zero cost, single-file, sufficient for 6 users.         |
| Rating   | `openskill` library         | TrueSkill-equivalent, patent-free, supports teams.      |
| Frontend | Jinja2 templates + HTMX     | Server-rendered, minimal JS, still interactive.          |
| Charts   | Chart.js (via CDN)          | Lightweight, beautiful charts, no build step.            |
| Hosting  | Railway / Render free tier  | Git-based deploys, persistent disk for SQLite.           |

### Why not a React SPA?

For 6 users and a CRUD-heavy app, a full React build adds complexity (separate build step, state management, API client) without much payoff. Jinja2 + HTMX gives you interactive UI (partial page updates, form submissions without reload) while keeping everything in Python. If you later want a fancier dashboard, you can bolt on a React frontend without changing the API.

### SQLite Trade-offs — An Honest Assessment

SQLite is the right call here, but it comes with a constraint worth understanding: **you need a persistent server**. You cannot deploy this on a pure serverless platform (Vercel Functions, AWS Lambda) because those don't have persistent filesystems. Your options are Railway (free tier with 500 hours/month), Render (free tier with spin-down), or a machine sitting in your office. If you ever outgrow this, migrating to PostgreSQL is straightforward with SQLAlchemy — the ORM abstracts the dialect.

---

## 4. Data Model

```sql
-- Core entities

CREATE TABLE players (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,         -- "Noam", "Itay", etc.
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE matches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    played_at       TIMESTAMP NOT NULL,       -- When the match was played
    team1_player1   INTEGER NOT NULL REFERENCES players(id),
    team1_player2   INTEGER NOT NULL REFERENCES players(id),
    team2_player1   INTEGER NOT NULL REFERENCES players(id),
    team2_player2   INTEGER NOT NULL REFERENCES players(id),
    team1_score     INTEGER NOT NULL CHECK(team1_score >= 0),
    team2_score     INTEGER NOT NULL CHECK(team2_score >= 0),
    logged_by       TEXT,                     -- Who entered it
    is_deleted      BOOLEAN DEFAULT FALSE,    -- Soft delete for corrections
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Rating snapshots (one row per player per match)

CREATE TABLE rating_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   INTEGER NOT NULL REFERENCES players(id),
    match_id    INTEGER NOT NULL REFERENCES matches(id),
    mu          REAL NOT NULL,                -- TrueSkill mean
    sigma       REAL NOT NULL,                -- TrueSkill uncertainty
    ordinal     REAL NOT NULL,                -- mu - 3*sigma (display rating)
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, match_id)
);

-- Weekly computed rankings

CREATE TABLE weekly_rankings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       INTEGER NOT NULL REFERENCES players(id),
    week_start      DATE NOT NULL,            -- Monday of the week
    skill_score     REAL NOT NULL,            -- Normalized TrueSkill (0-100)
    form_score      REAL NOT NULL,            -- Recent performance vs expected
    impact_score    REAL NOT NULL,            -- How much you lift your partners
    power_index     REAL NOT NULL,            -- Composite WPI
    rank            INTEGER NOT NULL,
    matches_played  INTEGER NOT NULL,
    wins            INTEGER NOT NULL,
    draws           INTEGER NOT NULL,
    losses          INTEGER NOT NULL,
    UNIQUE(player_id, week_start)
);

-- Pair chemistry tracking

CREATE TABLE pair_stats (
    player1_id      INTEGER NOT NULL REFERENCES players(id),
    player2_id      INTEGER NOT NULL REFERENCES players(id),
    matches_played  INTEGER DEFAULT 0,
    wins            INTEGER DEFAULT 0,
    goals_for       INTEGER DEFAULT 0,
    goals_against   INTEGER DEFAULT 0,
    last_played     TIMESTAMP,
    PRIMARY KEY (player1_id, player2_id),
    CHECK(player1_id < player2_id)            -- Canonical ordering
);

-- Indices for common queries

CREATE INDEX idx_matches_played_at ON matches(played_at);
CREATE INDEX idx_matches_not_deleted ON matches(is_deleted) WHERE is_deleted = FALSE;
CREATE INDEX idx_rating_history_player ON rating_history(player_id, created_at);
CREATE INDEX idx_weekly_rankings_week ON weekly_rankings(week_start, rank);
```

### Entity Relationships

```
players 1──────∞ rating_history
players 1──────∞ weekly_rankings
players ∞──────∞ players          (via pair_stats)
matches 1──────∞ rating_history
matches ∞──────4 players          (team1_p1, team1_p2, team2_p1, team2_p2)
```

### Design Decisions

**Why store rating snapshots per match?** This lets you draw a player's full rating trajectory over time — essential for trend charts. Without it, you'd need to replay every match from the start to reconstruct history.

**Why soft deletes on matches?** Hard deleting a match would require recalculating every subsequent rating for every player who participated. Soft delete + a "recalculate from scratch" function is simpler and more debuggable.

**Why `player1_id < player2_id` on pair_stats?** Without canonical ordering, (Noam, Itay) and (Itay, Noam) become separate rows. The CHECK constraint ensures each pair is stored exactly once.

---

## 5. Ranking System

This is the core intellectual challenge. You're asking: **"How do I measure individual skill from team outcomes?"** There are two layers here.

### Layer 1: TrueSkill Rating (The Real Signal)

TrueSkill (or its patent-free equivalent, OpenSkill's Plackett-Luce model) was literally designed by Microsoft Research for exactly this problem — rating individuals in team-based multiplayer games on Xbox Live.

Each player has two numbers: **μ (mu)** — their estimated skill, and **σ (sigma)** — the uncertainty around that estimate. A new player starts at μ=25, σ=8.33. After each match, winners' μ goes up (and losers' down), while σ shrinks for everyone as the system becomes more confident.

The **display rating** (ordinal) is `μ - 3σ`, which represents a conservative lower bound of skill. This means new players start low (~0) and climb as they play, which feels right.

Why TrueSkill over Elo? Elo is designed for 1v1. It doesn't handle the attribution problem: if Noam and Itay beat Ayal and Ari 3-0, was it Noam or Itay who carried? TrueSkill uses Bayesian inference to update each player independently based on the team composition and result.

**A skeptic's objection I'll raise myself**: TrueSkill assumes players perform independently. In reality, some pairs have chemistry — Noam and Itay might play differently together than their individual ratings predict. TrueSkill can't capture this. The pair_stats table partially addresses this, and the Impact Score (below) tries to measure it, but it's an inherent limitation. No rating system perfectly solves this for 2v2.

### Layer 2: Weekly Power Index (WPI) — The Fun Layer

The WPI is computed every Monday for the prior week. It's a composite score designed to capture more than just raw skill.

```
WPI = (0.50 × Skill Score) + (0.25 × Form Score) + (0.25 × Impact Score)
```

**Skill Score (50% weight)**: The player's current TrueSkill ordinal, normalized to a 0-100 scale across all players. This is the stable, long-term backbone of the ranking.

**Form Score (25% weight)**: How you performed THIS WEEK relative to what your rating predicted.

```
form = (actual_wins - expected_wins) / matches_played_this_week
```

Where `expected_wins` is calculated from the TrueSkill win probability for each match you played. If you won 4 matches this week but TrueSkill predicted you'd win 6, your form is negative — you underperformed. This rewards players who punch above their weight and penalizes those coasting on an inflated rating. Normalized to 0-100.

**Impact Score (25% weight)**: How much you elevate your partners. Uses **all-time** pair data (not just the current week) for stability.

```
impact = avg(partner_win_rate_with_you) - avg(partner_win_rate_without_you)
```

This is the most unique component. It measures whether your partners win more often when they play WITH you versus when they play without you. A player who makes everyone around them better gets a high impact score — like a midfielder who doesn't score but creates chances. Normalized to 0-100. **Requires 10+ matches per pair before the pair's data contributes to the score** — otherwise defaults to neutral (50). In the first few weeks of the system, Impact Score will default to 50 for most players until enough data accumulates.

**Why this split?** Skill Score provides stability (you don't swing wildly week to week). Form Score rewards hot streaks and punishes cold ones. Impact Score captures the "invisible" contribution that pure win/loss doesn't show. The 50/25/25 weighting means skill dominates, but a player on great form with high impact can overtake a slightly higher-rated player who's been coasting.

**My honest caveat**: The Form and Impact scores will be noisy in weeks with few matches. With only 3-4 matches, the scores will jump around. I'd recommend a minimum of 5 matches in a week to be ranked in the WPI — otherwise, show TrueSkill only. You can tune these weights once you have a few weeks of data.

### Weekly Awards

Computed alongside the WPI each Monday:

| Award | Criteria |
|-------|----------|
| **El Jefe** 👑 | Highest WPI for the week |
| **On Fire** 🔥 | Longest active win streak |
| **Rising Star** 📈 | Biggest WPI improvement vs. previous week |
| **The Wall** 🧱 | Fewest goals conceded per match (min 5 matches) |
| **Chemistry Kings** 🤝 | Best-performing pair of the week (by win rate, min 3 matches together) |
| **The Carry** 💪 | Highest Impact Score |

---

## 6. API Design

Base URL: `/api/v1`

### Matches

```
POST   /matches                  Log a new match
GET    /matches                  List matches (query: ?date=2026-02-26&player_id=1&limit=20&offset=0)
GET    /matches/{id}             Get match detail
DELETE /matches/{id}             Soft-delete a match (triggers rating recalc)
```

**POST /matches — Request Body:**
```json
{
  "played_at": "2026-02-26T14:30:00",
  "team1": ["Noam", "Itay"],
  "team2": ["Ayal", "Ari"],
  "team1_score": 3,
  "team2_score": 1,
  "logged_by": "Noam"
}
```

**Response (201):**
```json
{
  "id": 42,
  "played_at": "2026-02-26T14:30:00",
  "team1": {"players": ["Noam", "Itay"], "score": 3},
  "team2": {"players": ["Ayal", "Ari"], "score": 1},
  "rating_changes": [
    {"player": "Noam",  "old_ordinal": 28.3, "new_ordinal": 29.1, "delta": "+0.8"},
    {"player": "Itay",  "old_ordinal": 26.7, "new_ordinal": 27.4, "delta": "+0.7"},
    {"player": "Ayal",  "old_ordinal": 25.1, "new_ordinal": 24.5, "delta": "-0.6"},
    {"player": "Ari",   "old_ordinal": 22.9, "new_ordinal": 22.4, "delta": "-0.5"}
  ]
}
```

Note: Rating deltas are returned immediately so the UI can show "Noam ▲ +0.8" right after logging. This is the dopamine hit that keeps people using the app.

### Players

```
GET    /players                  List all players with current ratings
GET    /players/{id}             Detailed player profile
GET    /players/{id}/history     Rating history for trend charts
GET    /players/{id}/partners    Win rate with each partner
GET    /players/{id}/opponents   Win rate vs. each opponent
```

**GET /players/{id} — Response:**
```json
{
  "id": 1,
  "name": "Noam",
  "current_rating": {"mu": 31.2, "sigma": 3.1, "ordinal": 21.9},
  "stats": {
    "total_matches": 87,
    "wins": 52, "draws": 8, "losses": 27,
    "win_rate": 0.598,
    "goals_for": 186, "goals_against": 121,
    "current_streak": {"type": "W", "count": 3},
    "best_streak": {"type": "W", "count": 7}
  },
  "weekly_power_index": {
    "rank": 2,
    "wpi": 74.3,
    "skill_score": 78.0,
    "form_score": 65.2,
    "impact_score": 71.8
  }
}
```

### Rankings

```
GET    /rankings                 Current power rankings (all players)
GET    /rankings/history         Weekly ranking snapshots for trend chart
GET    /rankings/awards          Current week's awards
```

### Pairs

```
GET    /pairs                    All pair stats, sorted by matches played
GET    /pairs/best               Best-performing pair (highest win rate, min games)
GET    /pairs/worst              Worst-performing pair
```

### Team Generator

```
POST   /generate-teams           Generate balanced 2v2 matchups
```

**Request:**
```json
{
  "players": ["Noam", "Itay", "Ayal", "Ari"]
}
```

**Response:**
```json
{
  "matchups": [
    {
      "team1": ["Noam", "Ari"],
      "team2": ["Itay", "Ayal"],
      "balance_score": 0.97,
      "team1_win_prob": 0.48,
      "team2_win_prob": 0.52
    },
    {
      "team1": ["Noam", "Ayal"],
      "team2": ["Itay", "Ari"],
      "balance_score": 0.89,
      "team1_win_prob": 0.55,
      "team2_win_prob": 0.45
    }
  ]
}
```

The generator enumerates all possible 2v2 splits (with 4 players: 3 possible matchups; with 6 players: C(6,3)/2 = 10 possible matchups), computes the TrueSkill win probability for each, and returns them sorted by balance (how close to 50/50 the predicted outcome is).

---

## 7. Project Structure

```
fifa-tracker/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app, CORS, lifespan
│   │   ├── config.py            # Settings (DB path, TrueSkill params)
│   │   ├── database.py          # SQLAlchemy engine, session factory
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── ranking.py           # TrueSkill + WPI calculation engine
│   │   ├── team_generator.py    # Balanced matchup generator
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── matches.py       # Match CRUD endpoints
│   │       ├── players.py       # Player profile endpoints
│   │       ├── rankings.py      # Ranking + award endpoints
│   │       └── teams.py         # Team generator endpoint
│   ├── templates/               # Jinja2 HTML templates
│   │   ├── base.html            # Layout with nav, Chart.js CDN
│   │   ├── dashboard.html       # Main dashboard
│   │   ├── log_match.html       # Match entry form
│   │   ├── rankings.html        # Power ranking table + charts
│   │   ├── player.html          # Player profile page
│   │   └── awards.html          # Weekly awards showcase
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/charts.js         # Chart.js rendering helpers
│   ├── alembic/                 # Database migrations
│   ├── tests/
│   │   ├── test_ranking.py      # Unit tests for TrueSkill + WPI
│   │   ├── test_matches.py      # API endpoint tests
│   │   └── test_generator.py    # Team generator tests
│   ├── seed.py                  # Seed the 6 players
│   ├── weekly_job.py            # Script to compute WPI (run via cron)
│   ├── requirements.txt
│   └── Dockerfile
├── fifa.db                      # SQLite database (gitignored)
├── backups/                     # Periodic DB snapshots (optional)
├── .github/
│   └── workflows/
│       └── ci.yml               # Run tests on push
├── .gitignore
├── README.md
└── docker-compose.yml           # Optional: for easy local setup
```

---

## 8. Key Algorithms

### TrueSkill Update (per match)

```python
from openskill.models import PlackettLuce

model = PlackettLuce()

# After a match: team1 (Noam, Itay) beat team2 (Ayal, Ari) 3-1
team1 = [noam_rating, itay_rating]
team2 = [ayal_rating, ari_rating]

# Result: team1 won → listed first; ranks = [1, 2]
[new_team1, new_team2] = model.rate([team1, team2], ranks=[1, 2])
```

Draws are handled by passing `ranks=[1, 1]`.

### Weekly Power Index Calculation

```python
def compute_wpi(player_id: int, week_start: date, db: Session) -> dict:
    # 1. Skill Score: current ordinal, normalized to 0-100
    all_ordinals = get_all_current_ordinals(db)
    player_ordinal = get_player_ordinal(player_id, db)
    skill_score = normalize(player_ordinal, min(all_ordinals), max(all_ordinals))

    # 2. Form Score: actual wins vs expected wins this week
    week_matches = get_player_matches_in_week(player_id, week_start, db)
    if len(week_matches) < 5:
        return None  # Not enough data for meaningful WPI

    actual_wins = sum(1 for m in week_matches if player_won(player_id, m))
    expected_wins = sum(win_probability(player_id, m) for m in week_matches)
    form_raw = (actual_wins - expected_wins) / len(week_matches)
    form_score = normalize(form_raw, -1.0, 1.0)  # Map to 0-100

    # 3. Impact Score: partner uplift
    partner_rates = []
    for partner_id in get_partners_this_week(player_id, week_start, db):
        wr_with = win_rate_together(player_id, partner_id, db)
        wr_without = win_rate_without(partner_id, player_id, db)
        partner_rates.append(wr_with - wr_without)

    impact_raw = mean(partner_rates) if partner_rates else 0
    impact_score = normalize(impact_raw, -0.5, 0.5)

    # Note: All pair_stats queries MUST canonicalize player IDs (smaller ID first)
    # to match the CHECK(player1_id < player2_id) constraint on the pair_stats table.
    # e.g.: p1, p2 = min(a, b), max(a, b)

    # Edge case: In the first few weeks, Impact Score will be noisy because
    # win_rate_without() has little data. Use all-time pair data (not weekly)
    # and require each pair to have 10+ matches before trusting the score.
    # If insufficient data, default impact_score to 50 (neutral).

    # Composite
    wpi = (0.50 * skill_score) + (0.25 * form_score) + (0.25 * impact_score)

    return {
        "skill_score": round(skill_score, 1),
        "form_score": round(form_score, 1),
        "impact_score": round(impact_score, 1),
        "power_index": round(wpi, 1),
    }
```

### Balanced Team Generator

```python
from itertools import combinations

def generate_balanced_matchups(player_ids: list[int], db: Session) -> list[dict]:
    ratings = {pid: get_current_rating(pid, db) for pid in player_ids}
    n = len(player_ids)

    matchups = []
    # Generate all ways to split N players into two teams of N/2
    for team1 in combinations(player_ids, n // 2):
        team2 = tuple(p for p in player_ids if p not in team1)

        # Avoid counting (A,B) vs (C,D) and (C,D) vs (A,B) as different
        if team1 > team2:
            continue

        # Compute win probability using TrueSkill
        win_prob = predict_win(
            [ratings[p] for p in team1],
            [ratings[p] for p in team2]
        )
        balance = 1.0 - abs(win_prob - 0.5) * 2  # 1.0 = perfectly balanced

        matchups.append({
            "team1": team1,
            "team2": team2,
            "balance_score": round(balance, 3),
            "team1_win_prob": round(win_prob, 2),
            "team2_win_prob": round(1 - win_prob, 2),
        })

    return sorted(matchups, key=lambda m: m["balance_score"], reverse=True)
```

---


---

## 8b. Telegram Bot (Primary Input Interface)

The Telegram bot is the primary way to log matches. It's a thin client that calls the same REST API — the backend doesn't know or care whether input comes from the web form or the bot.

### Architecture

```
Telegram Group Chat                Web Dashboard (read-only)
       │                                │
       ▼                                ▼
  Telegram Bot ──── HTTP ────►  FastAPI Backend  ◄──── SQLite
  (python-telegram-bot v20+)     (same REST API)
```

### Commands

| Command | Example | Description |
|---------|---------|-------------|
| `/match` | `/match Noam Itay vs Ayal Ari 3-1` | Log a match, show rating deltas |
| `/rank` | `/rank` | Current power rankings |
| `/stats` | `/stats Noam` | Player profile and stats |
| `/teams` | `/teams Noam Itay Ayal Ari` | Suggest balanced matchups |
| `/undo` | `/undo` | Delete last match (with confirmation) |
| `/awards` | `/awards` | This week's awards |
| `/today` | `/today` | Today's matches |

### Key Design Decisions

**Fuzzy name matching**: The bot uses Levenshtein distance to catch typos. "/match Noan Itay vs Ayal Ari 3-1" → "Did you mean Noam?" This is critical because phone keyboards make typos inevitable.

**Confirmation for destructive actions**: `/undo` shows the match details and asks for confirmation via inline keyboard (✅/❌) before deleting.

**Automated posting**: The bot auto-posts weekly rankings and awards every Monday morning when the WPI cron job completes.

**Separate process**: The bot runs as its own process (not inside the FastAPI app). This means the web dashboard stays up even if the bot crashes, and vice versa. In Docker, they're two separate services.

## 9. Frontend Pages

### Dashboard (Home)
- Today's matches (live-updating list)
- Current top 3 in WPI with mini trend sparklines
- Quick "Log Match" button
- Current weekly awards

### Log Match
- Player selector (dropdowns or click-to-assign to teams)
- Score inputs
- "Randomize Teams" button (calls team generator)
- Shows rating changes immediately on submit

### Power Rankings
- Full ranking table: Rank, Player, WPI, Skill/Form/Impact breakdown, W/L, Streak
- Toggle between WPI and raw TrueSkill
- Line chart: all players' ratings over time (last 30 days)

### Player Profile
- Personal stats: matches, win rate, goals, best/worst day
- Rating history chart
- Best/worst partners table
- Opponent record (who do they beat, who beats them)
- Weekly WPI history

### Awards
- Current week's awards with player avatars
- Historical awards archive

---

## 10. Deployment

### Recommended: Railway (Free Tier)

Railway offers a free tier with persistent disk storage (needed for SQLite) and Git-based deploys.

```yaml
# docker-compose.yml (local dev)
version: "3.8"
services:
  app:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./fifa.db:/app/fifa.db
    environment:
      - DATABASE_URL=sqlite:///fifa.db
```

### Weekly Cron Job

The WPI calculation runs as a scheduled job. On Railway/Render, use their built-in cron support. Alternatively, run `python weekly_job.py` via a GitHub Action every Monday at 00:00.

```yaml
# .github/workflows/weekly-rankings.yml
name: Compute Weekly Rankings
on:
  schedule:
    - cron: '0 0 * * 1'  # Every Monday at midnight UTC
```

### Backup Strategy

SQLite is a single file. Add a GitHub Action that backs up `fifa.db` to a private repo or cloud storage weekly. Alternatively, the app can dump SQL on each match log (cheap insurance).

---

## 11. Trade-offs and Things I'd Push Back On

### What I'd Revisit First

1. **The WPI weights (50/25/25) are arbitrary.** They feel reasonable, but you'll want to tune them after 3-4 weeks of real data. If Impact Score feels meaningless, drop its weight. If Form Score swings too much, dampen it. The architecture supports easy retuning.

2. **Impact Score needs volume.** With 6 players rotating partners, each pair might play only 2-3 times per week. The "partner uplift" calculation will be noisy until you have ~50+ matches per pair. Consider using all-time pair data (not just weekly) for this component.

3. **SQLite won't scale past ~10 concurrent writers.** This is fine for 6 people, but if you ever want to open this up to multiple office leagues, migrate to PostgreSQL. The SQLAlchemy ORM makes this a <1 hour change.

4. **No authentication in v1.** Anyone with the URL can log matches. For an office tool among friends, this is fine. If someone starts trolling, add basic auth (even just a shared PIN).

### What I'd Add in v2

- **Seasons**: Reset rankings quarterly. Keep all-time stats separate from season stats.
- **Match replay dispute**: Let any of the 4 players in a match flag it as "incorrect" — requires consensus to modify.
- **Push notifications**: Slack/Telegram webhook when weekly awards drop.
- **Score margin weighting**: A 5-0 blowout should update ratings more aggressively than a 1-0 squeeze. TrueSkill doesn't natively support this — you'd need a custom modification.
- **ELO vs. TrueSkill toggle**: Some people trust what they understand. Let users view both.

---

## 12. Open Questions for the Team

1. **What counts as a draw?** FIFA can end in draws. Should draws update ratings? (My recommendation: yes, with `ranks=[1,1]` in TrueSkill — both teams "tie" for first.)

2. **Minimum matches per week for WPI?** I suggested 5, but with 6 players and daily play, is that too high? Could drop to 3.

3. **Should the team generator enforce variety?** E.g., avoid pairing the same two players in back-to-back matches. Adds complexity but prevents staleness.

4. **Hosting preference?** Railway (easiest), Render (also easy), or a machine in the office (most control, zero cost, but needs maintenance)?

---

*This document is a starting point. The architecture is deliberately simple — you can build v1 in a weekend. Start logging matches immediately and add the fancy ranking stuff once you have a few weeks of data to validate against.*
