from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .features import _recency_weight
from .normalize import GameRecord, PlayerPerf


@dataclass
class MatchupStats:
    games: int = 0
    wins: int = 0

    def posterior_winrate(self, alpha: float = 2.0, beta: float = 2.0) -> float:
        return (self.wins + alpha) / (self.games + alpha + beta)

    def confidence(self) -> float:
        return min(1.0, self.games / 20.0) if self.games else 0.0


def _index_by_role(players: List[PlayerPerf]) -> Dict[str, PlayerPerf]:
    out: Dict[str, PlayerPerf] = {}
    for p in players:
        if p.role and p.character:
            if p.role not in out:
                out[p.role] = p
    return out


def build_matchup_table(games: List[GameRecord]) -> Dict[Tuple[str, str, str], MatchupStats]:
    table: Dict[Tuple[str, str, str], MatchupStats] = defaultdict(MatchupStats)

    for g in games:
        team_by_role = _index_by_role(g.team.players)
        opp_by_role = _index_by_role(g.opponent.players)
        for role, our_player in team_by_role.items():
            their_player = opp_by_role.get(role)
            if not their_player:
                continue
            key = (role, our_player.character or "", their_player.character or "")
            if not key[1] or not key[2]:
                continue
            stats = table[key]
            stats.games += 1
            if g.team.won is True:
                stats.wins += 1
    return table


def compute_our_pick_pools(games: List[GameRecord]) -> Dict[str, Dict[str, float]]:
    pools: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for g in games:
        w = _recency_weight(g.start_time)
        for p in g.team.players:
            if p.player_id and p.character:
                pools[p.player_id][p.character] += w
    return pools


def _flatten_pick_rates(pools: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    flat: Dict[str, float] = defaultdict(float)
    for picks in pools.values():
        for champ, w in picks.items():
            flat[champ] += w
    return flat


def suggest_counters(
    matchup_table: Dict[Tuple[str, str, str], MatchupStats],
    opponent_players: Dict[str, Dict[str, Any]],
    our_pools: Optional[Dict[str, Dict[str, float]]] = None,
    top_k: int = 3,
) -> Dict[str, Any]:
    personalization = "high" if our_pools else "low"

    if not our_pools:
        our_pools = {"team": _flatten_pick_rates({})}

    role_counters: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    # Build a global pool if per-player pools are absent
    global_pool = _flatten_pick_rates(our_pools)

    for opp in opponent_players.values():
        role = opp.get("role")
        picks = opp.get("comfort_picks") or []
        if not role or not picks:
            continue
        for pick in picks:
            their_champ = pick.get("character")
            if not their_champ:
                continue
            candidates = []
            for our_champ, weight in global_pool.items():
                key = (role, our_champ, their_champ)
                stats = matchup_table.get(key)
                if not stats:
                    continue
                winrate = stats.posterior_winrate()
                confidence = stats.confidence()
                score = winrate * confidence * (weight or 0.0)
                candidates.append(
                    {
                        "our_champ": our_champ,
                        "their_champ": their_champ,
                        "expected_winrate": winrate,
                        "samples": stats.games,
                        "confidence": confidence,
                        "score": score,
                    }
                )

            candidates.sort(key=lambda x: x["score"], reverse=True)
            for c in candidates[:top_k]:
                role_counters[role].append(c)

    return {
        "personalization_level": personalization,
        "by_role": role_counters,
    }
