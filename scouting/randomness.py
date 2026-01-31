from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from .features import _entropy
from .normalize import GameRecord
from .scenarios import cluster_scenarios


def _distribution_from_games(games: List[GameRecord]) -> Dict[str, float]:
    counts: Counter = Counter()
    for g in games:
        for p in g.opponent.players:
            if p.character:
                counts[p.character] += 1
    return {k: float(v) for k, v in counts.items()}


def _normalize(dist: Dict[str, float]) -> Dict[str, float]:
    total = sum(dist.values())
    if total <= 0:
        return {k: 0.0 for k in dist}
    return {k: v / total for k, v in dist.items()}


def _js_divergence(p: Dict[str, float], q: Dict[str, float]) -> float:
    keys = set(p.keys()) | set(q.keys())
    p_norm = _normalize({k: p.get(k, 0.0) for k in keys})
    q_norm = _normalize({k: q.get(k, 0.0) for k in keys})
    m = {k: 0.5 * (p_norm[k] + q_norm[k]) for k in keys}

    def kl(a: Dict[str, float], b: Dict[str, float]) -> float:
        s = 0.0
        for k in keys:
            if a[k] > 0 and b[k] > 0:
                s += a[k] * math.log(a[k] / b[k], 2)
        return s

    return 0.5 * (kl(p_norm, m) + kl(q_norm, m))


def _sorted_by_time(games: List[GameRecord]) -> List[GameRecord]:
    return sorted(games, key=lambda g: g.start_time)


def compute_randomness(games: List[GameRecord]) -> Dict[str, float | str]:
    if not games:
        return {
            "draft_entropy": 0.0,
            "player_entropy": 0.0,
            "scenario_entropy": 0.0,
            "drift": 0.0,
            "score": 0.0,
            "interpretation": "no data",
            "advice": "collect more games",
        }

    team_dist = _distribution_from_games(games)
    draft_entropy = _entropy(team_dist)

    per_player: Dict[str, Counter] = defaultdict(Counter)
    for g in games:
        for p in g.opponent.players:
            if p.player_id and p.character:
                per_player[p.player_id][p.character] += 1
    player_entropies = [
        _entropy({k: float(v) for k, v in counts.items()}) for counts in per_player.values()
    ]
    player_entropy = sum(player_entropies) / len(player_entropies) if player_entropies else 0.0

    scenarios = cluster_scenarios(games)
    scenario_dist = {str(s.scenario_id): s.share for s in scenarios}
    scenario_entropy = _entropy(scenario_dist)

    ordered = _sorted_by_time(games)
    split = max(1, int(len(ordered) * 0.75))
    prev_games = ordered[:split]
    recent_games = ordered[split:]
    drift = _js_divergence(_distribution_from_games(prev_games), _distribution_from_games(recent_games))

    score = 100.0 * (
        0.35 * draft_entropy + 0.25 * player_entropy + 0.25 * scenario_entropy + 0.15 * drift
    )

    if score < 35:
        interpretation = "highly predictable"
        advice = "target-ban top comfort picks and prep 1-2 compositions"
    elif score < 65:
        interpretation = "moderately flexible"
        advice = "ban 1-2 priority picks and prepare adaptive drafts"
    else:
        interpretation = "chaotic"
        advice = "prep principles and flexible answers; prioritize comfort denial"

    return {
        "draft_entropy": draft_entropy,
        "player_entropy": player_entropy,
        "scenario_entropy": scenario_entropy,
        "drift": drift,
        "score": score,
        "interpretation": interpretation,
        "advice": advice,
    }
