# LoL Scouting Report API

A professional-grade scouting report generator for League of Legends teams. Analyzes historical match data and generates comprehensive insights for coaches and players.

## Quick Start

### 1. Install Dependencies

```bash
pip install -e .
# or
pip install fastapi uvicorn python-dotenv httpx scikit-learn
```

### 2. Set Up Environment

Create a `.env` file in the project root:

```bash
GRID_API_KEY=your_api_key_here
```

### 3. Run the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Test the Endpoint

```bash
# Using curl (GET request)
curl "http://localhost:8000/api/scouting/report?team=Cloud9&opponent=Team%20Liquid&window_days=180"

# Using curl (POST request)
curl -X POST "http://localhost:8000/api/scouting/report" \
  -H "Content-Type: application/json" \
  -d '{
    "team": "Cloud9",
    "opponent": "Team Liquid",
    "window_days": 180,
    "tournament_filter": "LCS"
  }'
```

### 5. View API Documentation

Open http://localhost:8000/docs for interactive Swagger documentation.

---

## API Endpoints

### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "api_key_configured": true
}
```

### `POST /api/scouting/report`
Generate a scouting report.

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `team` | string | Yes | Your team name (e.g., "Cloud9") |
| `opponent` | string | Yes | Opponent team name (e.g., "Team Liquid") |
| `window_days` | integer | No | Days back to analyze (default: 180, max: 3650) |
| `tournament_filter` | string | No | Filter by tournament name (e.g., "LCS", "Worlds") |

### `GET /api/scouting/report`
Same as POST but with query parameters for easier testing.

---

## Response Structure

The API returns a comprehensive JSON report with the following sections:

```json
{
  "success": true,
  "request": { ... },
  "report": {
    "meta": { ... },
    "executive_summary": { ... },
    "the_story": { ... },
    "enhanced_players": { ... },
    "one_thing_per_player": [ ... ],
    "enhanced_scenarios": [ ... ],
    "draft_guide": { ... },
    "pick_decision_tree": { ... },
    "side_analysis": { ... },
    "series_momentum": { ... },
    "trends": { ... },
    "cheese_picks": [ ... ],
    "kill_participation_web": { ... },
    "game_script": { ... },
    "preparation_checklist": { ... },
    ...
  }
}
```

---

## Field Documentation

### `meta`
Metadata about the report and data coverage.

| Field | Type | Description |
|-------|------|-------------|
| `team_name` | string | Your team name |
| `opponent_name` | string | Opponent team name |
| `team_id` | string | Internal team ID |
| `opponent_id` | string | Internal opponent ID |
| `title` | string | Game title (always "lol") |
| `window_gte` | string | Start date of analysis window (ISO 8601) |
| `window_lte` | string | End date of analysis window (ISO 8601) |
| `series_found` | integer | Number of series found |
| `series_analyzed` | integer | Number of series with usable data |

---

### `executive_summary`
High-level overview for quick briefings.

| Field | Type | Description |
|-------|------|-------------|
| `headline` | string | One-line assessment (e.g., "Team Liquid: Competitive matchup") |
| `profile` | string | 2-3 sentence team description |
| `key_strengths` | array | List of opponent strengths |
| `key_weaknesses` | array | List of exploitable weaknesses |
| `game_plan` | string | Recommended approach in one sentence |
| `risk_level` | string | "low" / "medium" / "high" |
| `confidence` | string | "low" / "medium" / "high" (based on sample size) |
| `games_analyzed` | integer | Total games in the dataset |
| `overall_winrate` | float | Opponent's overall winrate (0-1) |
| `recent_winrate` | float | Winrate in last 30 days (0-1) |

**How it's calculated:** Aggregates stats from all games, identifies patterns in player performance and draft tendencies, and generates human-readable summaries.

---

### `the_story`
Narrative scouting report like a sports analyst would write.

| Field | Type | Description |
|-------|------|-------------|
| `paragraphs` | array | Narrative sections with type, title, and text |
| `tldr` | string | One-line summary |
| `full_narrative` | string | All paragraphs combined |

**Paragraph types:**
- `opening` - The matchup overview
- `identity` - How they play
- `players` - Key players to watch
- `sides` - Blue/Red side preference
- `cheese` - Pocket pick warnings
- `closing` - The game plan

---

### `enhanced_players`
Detailed scouting card for each opponent player.

| Field | Type | Description |
|-------|------|-------------|
| `player_id` | string | Unique player identifier |
| `name` | string | Player name |
| `role` | string | Position (top/jg/mid/bot/sup) |
| `comfort_picks` | array | Top champions by weighted pick rate |
| `scouting_notes` | string | Human-readable player summary |
| `threat_level` | string | "low" / "medium" / "high" / "critical" |
| `champion_pool_depth` | string | "one-trick" / "shallow" / "moderate" / "deep" |
| `recent_form` | string | "cold" / "trending down" / "stable" / "trending up" / "hot" |
| `playstyle` | string | "safe/controlled" / "balanced" / "calculated aggression" / "aggressive carry" / "coinflip" / "liability" |
| `exploitable_patterns` | array | Specific weaknesses to target |
| `stats.games` | integer | Games played |
| `stats.winrate` | float | Win rate (0-1) |
| `stats.kda` | float | Kill/Death ratio |
| `stats.kills_per_game` | float | Average kills per game |

**How it's calculated:**
- `threat_level`: Based on winrate, games played, and comfort pick share
- `champion_pool_depth`: Unique champions / games ratio
- `recent_form`: Last 30 days winrate vs overall winrate
- `playstyle`: Based on kills/deaths per game patterns

---

### `one_thing_per_player`
Single most important callout per player for quick briefings.

| Field | Type | Description |
|-------|------|-------------|
| `player_name` | string | Player name |
| `role` | string | Position |
| `one_thing` | string | The key insight |
| `action` | string | What to do about it |
| `priority` | string | "low" / "medium" / "high" |

---

### `enhanced_scenarios`
Different playstyles/comps the opponent runs with win conditions.

| Field | Type | Description |
|-------|------|-------------|
| `scenario_id` | integer | Cluster identifier |
| `name` | string | Style name ("Aggressive Early", "Slow/Scaling", etc.) |
| `share` | float | Percentage of games (0-1) |
| `share_label` | string | Human-readable (e.g., "42% of their games") |
| `winrate` | float | Win rate with this style (0-1) |
| `winrate_label` | string | "dominant" / "strong" / "average" / "struggling" / "weak" |
| `signature_picks` | object | Key champions by role |
| `tempo` | string | "early-game" / "mid-game" / "late-game" / "high-tempo" |
| `flexibility` | string | "rigid" / "focused" / "moderate" / "flexible" |
| `win_conditions` | array | How they win with this style |
| `loss_patterns` | array | How they lose with this style |
| `how_to_beat` | array | Counter-strategies |

**How it's calculated:** Games are clustered using K-Means on champion picks and K/D patterns. Each cluster represents a distinct playstyle.

---

### `draft_guide`
Actionable draft recommendations.

| Field | Type | Description |
|-------|------|-------------|
| `must_ban` | array | Priority bans with reasons |
| `situational_bans` | array | Context-dependent bans |
| `respect_picks` | array | Champions to not let through |
| `draft_traps` | array | Picks to avoid against this team |
| `phase_strategy` | string | "hard_read" / "balanced" / "reactive" |
| `phase_strategy_note` | string | Detailed draft phase guidance |
| `flex_threats` | array | Their flex picks to watch |
| `summary` | string | One-line draft recommendation |

---

### `pick_decision_tree`
Visual flowchart data for draft decisions.

| Field | Type | Description |
|-------|------|-------------|
| `flowchart.nodes` | array | Graph nodes (players, picks, responses) |
| `flowchart.edges` | array | Connections between nodes |
| `quick_reference` | array | Simplified matchup recommendations per role |

**Node types:**
- `root` - Starting point
- `role` - Role category (TOP, JG, MID, BOT, SUP)
- `opponent_pick` - Their champion pick
- `response` - Our recommended response
- `avoid` - Picks to avoid

**Visualization:** Use React Flow, D3.js, or vis.js to render the flowchart.

---

### `side_analysis`
Blue side vs Red side performance comparison.

| Field | Type | Description |
|-------|------|-------------|
| `blue_side.games` | integer | Games on blue side |
| `blue_side.winrate` | float | Winrate on blue side (0-1) |
| `blue_side.priority_picks` | array | Top picks on blue side |
| `red_side.games` | integer | Games on red side |
| `red_side.winrate` | float | Winrate on red side (0-1) |
| `red_side.priority_picks` | array | Top picks on red side |
| `preference` | string | "blue" / "red" / "slight_blue" / "slight_red" / "neutral" |
| `preference_note` | string | Human-readable explanation |
| `recommendation` | string | What to do with side selection |

---

### `series_momentum`
Mental edge and adaptation analysis.

| Field | Type | Description |
|-------|------|-------------|
| `game_1.winrate` | float | Game 1 winrate |
| `later_games.winrate` | float | Games 2+ winrate |
| `after_loss.winrate` | float | Winrate after losing a game in series |
| `after_win.winrate` | float | Winrate after winning a game in series |
| `mental_profile` | string | "stable" / "resilient" / "tilter" |
| `mental_note` | string | How to exploit their mental |
| `adaptation` | string | "strong_adapters" / "consistent" / "slow_starters" |
| `adaptation_note` | string | How they adjust during series |
| `clutch_factor` | string | "clutch" / "neutral" / "chokers" |
| `series_comebacks` | integer | Times they came back from game 1 loss |
| `series_chokes` | integer | Times they lost after winning game 1 |

---

### `trends`
Performance trajectory over time.

| Field | Type | Description |
|-------|------|-------------|
| `trajectory` | string | "surging" / "improving" / "stable" / "declining" / "slumping" |
| `trajectory_note` | string | What the trajectory means |
| `form_periods` | array | Winrate breakdown by time period |
| `recent_games` | integer | Games in last 2 weeks |
| `recent_winrate` | float | Recent winrate |

**How it's calculated:** Compares winrate in last 2 weeks vs 2-6 weeks ago to detect momentum.

---

### `cheese_picks`
Pocket picks / surprise champions to watch for.

| Field | Type | Description |
|-------|------|-------------|
| `player_name` | string | Player who plays this pick |
| `role` | string | Position |
| `champion` | string | Champion name |
| `games` | integer | Times played |
| `winrate` | float | Winrate on this pick (0-1) |
| `pick_rate` | float | How often they pick it (0-1) |
| `cheese_score` | float | Danger score (higher = more dangerous) |
| `warning` | string | Human-readable warning |

**How it's calculated:** Champions with <15% pick rate but >65% winrate are flagged as pocket picks.

---

### `kill_participation_web`
Network graph showing who enables who on the team.

| Field | Type | Description |
|-------|------|-------------|
| `network.nodes` | array | Player nodes with kill stats |
| `network.edges` | array | Connections showing synergy |
| `playmaker` | object | The primary kill threat |
| `enabler` | object | The key setup player |
| `insights` | array | Actionable observations |

**Node data:**
- `kills_per_game` - Offensive involvement
- `involvement` - "primary_carry" / "secondary_carry" / "enabler"
- `size` - Visual size for graph ("large" / "medium" / "small")

**Edge data:**
- `winrate` - Winrate when both players are together
- `strength` - "strong" / "moderate" / "weak"
- `type` - "synergy" / "neutral" / "anti_synergy"

**Visualization:** Use vis.js, d3-force, or react-force-graph.

---

### `game_script`
Minute-by-minute game prediction.

| Field | Type | Description |
|-------|------|-------------|
| `timeline` | array | Predicted events by game phase |
| `critical_moments` | array | Key decision points in the game |
| `win_condition` | object | Their win condition and how to deny it |
| `tempo` | string | "slow" / "standard" / "aggressive" / "bloody" |
| `tempo_note` | string | What the tempo means |
| `summary` | string | One-paragraph game flow prediction |

**Timeline phases:**
- `champ_select` - Draft predictions
- `early_game` (0-5 min) - Level 1-3 plays
- `early_mid` (5-10 min) - First objectives
- `mid_game` (10-20 min) - Snowball or stall
- `late_game` (20+ min) - Win conditions

**Event data:**
- `event` - What might happen
- `probability` - Likelihood (0-1)
- `icon` - Emoji for visualization

---

### `preparation_checklist`
Actionable preparation items.

| Field | Type | Description |
|-------|------|-------------|
| `items` | array | Checklist items with category and priority |
| `high_priority_count` | integer | Number of high priority items |
| `series_to_review` | array | Series IDs for VOD review |

**Item categories:** Draft, Picks, Scrims, VOD Review, Focus

---

## Error Responses

| Status | Meaning |
|--------|---------|
| 404 | No matches found for the specified teams/window |
| 500 | Server error or missing API key |

```json
{
  "detail": "Error message here"
}
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GRID_API_KEY` | Yes | API key for GRID esports data |

---

## CLI Usage (Alternative)

You can also generate reports via command line:

```bash
export GRID_API_KEY="..."
python -m scouting.cli --title lol --team "Cloud9" --opponent "Team Liquid" --window-days 180 \
  --tournament-filter "LCS" \
  --output report.json --output-format json
```

**Optional CLI flags:**
- `--save-raw raw.json` - Save raw series data
- `--save-normalized games.json` - Save normalized games
- `--cache` - Enable on-disk cache
- `--from-raw raw.json` - Skip API requests, use saved data

---

## PDF Report Generation

```bash
python -m scouting.report_pdf --input report.json --output report.pdf
```

---

## Development

```bash
# Run with hot reload
uvicorn main:app --reload

# Run tests
pytest -q
```

---

## Notes

- Team mapping uses team IDs (no team0/team1 assumptions)
- AllSeries pagination is implemented to avoid missing series
- SeriesState queries fall back to basic query if extended fields aren't supported
- Role heuristics use `scouting/role_map.json` (override with `SCOUTING_ROLE_MAP` env var)