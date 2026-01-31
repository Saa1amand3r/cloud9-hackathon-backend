# Algorithms (Brief, Simple)

This document explains the main algorithms in plain language.

## 1) Data Ingestion (GRID)
- We resolve the game title ID (e.g., League of Legends).
- We resolve team IDs by searching team names.
- We list tournaments for that title, then list all series in the time window.
- We keep only series where both teams appear.
- For each series, we call SeriesState to get game stats and player data.

## 2) Normalization
- We map “our team” and “opponent” by team ID, never by ordering.
- Each game becomes a simple record with:
  - team stats, opponent stats
  - player stats (kills, deaths, role, character if present)
- If a series has no games, we use the series-level team stats.

## 3) Per-Player Tendencies
- For each opponent player, we count how often they pick each character.
- Recent games count more (exponential decay by days).
- Comfort picks = top picks that cover 50% of their weighted games.
- Volatility = entropy of their pick distribution (0 = predictable, 1 = chaotic).

## 4) Team Draft Tendencies
- We count opponent picks across all games.
- “Priority picks” = most frequent (weighted) characters.
- “Flex picks” = characters used in multiple roles (if role data exists).
- Bans are empty unless the data source provides them.

## 5) Match Outcomes
- We count wins/losses, average kills, and average deaths.
- This is purely aggregated from the normalized games.

## 6) Counter Suggestions
- We build a table of matchups by role:
  - (role, our_champ, their_champ) → win/loss counts.
- We use Bayesian smoothing for winrate:
  - (wins + alpha) / (games + alpha + beta), with alpha=beta=2.
- Confidence grows with more samples (max at 20 games).
- Suggestions pick the best-scoring counters from our pool.

## 7) Scenarios (Multiple Strategies)
- Each opponent game is turned into a small feature vector:
  - role+champion hashes, kills, deaths, win/loss.
- We cluster games into 2–4 groups (KMeans if available; fallback if not).
- Each cluster becomes a “scenario card” with:
  - share of games, winrate, signature picks, volatility, and a simple punish idea.

## 8) Randomness Score
- Draft entropy: how diverse the team’s champions are.
- Player entropy: average diversity per player.
- Scenario entropy: how spread-out the clusters are.
- Drift: change in picks between older and recent games (Jensen–Shannon).
- Final score (0–100):
  - 0.35*draft + 0.25*player + 0.25*scenario + 0.15*drift.
- Interpretation:
  - <35 = predictable, 35–65 = flexible, >65 = chaotic.

## 9) Report Assembly
- Combines all outputs into one JSON report.
- Adds missing-data flags so you know what was unavailable.
