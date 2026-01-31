from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from .features import (
    compute_data_coverage,
    compute_match_outcomes,
    compute_per_player_tendencies,
    compute_team_draft_tendencies,
    _entropy,
    compute_champion_winrates,
    compute_roster_stability,
    compute_style_triangle,
    compute_draft_dna_summary,
    compute_counterfactual_bans,
    compute_signature_cluster_cards,
    compute_player_similarity,
)
from .grid_ingest import FetchMeta
from .matchups import build_matchup_table, compute_our_pick_pools, suggest_counters
from .normalize import GameRecord
from .randomness import compute_randomness
from .scenarios import cluster_scenarios_with_labels


def _build_plan_template(
    per_player: Dict[str, Any],
    draft: Dict[str, Any],
    randomness: Dict[str, Any],
) -> Dict[str, Any]:
    priority = [p.get("character") for p in (draft.get("priority_picks") or []) if p.get("character")]
    ban_core = priority[:3]
    comfort_bans = []
    for p in per_player.values():
        comfort = p.get("comfort_picks") or []
        if comfort and (comfort[0].get("share") or 0) >= 0.5:
            comfort_bans.append(comfort[0].get("character"))
    ban_list = [c for c in (ban_core + comfort_bans) if c]
    ban_list = list(dict.fromkeys(ban_list))[:5]

    draft_plan = (
        "Draft for flexibility; keep answers ready for "
        + ", ".join(priority[:5])
        + ". Focus on denying engage supports and stable jungle picks if available."
    )
    if randomness.get("interpretation") == "chaotic":
        draft_plan += " Expect multiple styles; prioritize adaptable comps over single hard reads."

    return {
        "ban_plan": ban_list,
        "draft_plan": draft_plan,
    }


def _normalize_axis(values: List[float]) -> List[float]:
    if not values:
        return []
    vmin = min(values)
    vmax = max(values)
    if vmax == vmin:
        return [0.5 for _ in values]
    return [(v - vmin) / (vmax - vmin) for v in values]


def _build_scenario_viz(
    clusters: Dict[int, List[GameRecord]],
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for cid, games in clusters.items():
        if not games:
            continue
        total = len(games)
        wins = sum(1 for g in games if g.opponent.won is True)
        champ_counts: Dict[str, int] = {}
        role_counts: Dict[str, int] = {}
        kills = 0
        deaths = 0
        for g in games:
            kills += g.opponent.kills
            deaths += g.opponent.deaths
            for p in g.opponent.players:
                if p.character:
                    champ_counts[p.character] = champ_counts.get(p.character, 0) + 1
                if p.role:
                    role_counts[p.role] = role_counts.get(p.role, 0) + 1

        total_picks = sum(role_counts.values()) or 1
        pick_buckets = {k: v / total_picks for k, v in role_counts.items()}
        top_picks = sorted(champ_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        items.append(
            {
                "scenario_id": cid,
                "games": total,
                "winrate": wins / total,
                "pick_buckets": pick_buckets,
                "top_picks": [c for c, _ in top_picks],
                "early_aggression_raw": kills / total,
                "teamfightiness_raw": (kills + deaths) / total,
                "draft_volatility_raw": _entropy({k: float(v) for k, v in champ_counts.items()}),
                "macro_raw": None,
            }
        )

    # normalize axes for radar charts
    early_vals = _normalize_axis([i["early_aggression_raw"] for i in items])
    fight_vals = _normalize_axis([i["teamfightiness_raw"] for i in items])
    vol_vals = _normalize_axis([i["draft_volatility_raw"] for i in items])

    for idx, item in enumerate(items):
        item["fingerprint"] = {
            "early_aggression": early_vals[idx],
            "draft_volatility": vol_vals[idx],
            "teamfightiness": fight_vals[idx],
            "macro": None,
        }

    return items


def _build_counter_matrix(
    matchup_table: Dict[tuple, Any],
    per_player: Dict[str, Any],
    our_pools: Dict[str, Dict[str, float]],
    max_rows: int = 6,
    max_cols: int = 6,
) -> Dict[str, Any]:
    # Collect opponent likely champs by role
    role_rows: Dict[str, List[str]] = {}
    for p in per_player.values():
        role = p.get("role")
        picks = p.get("comfort_picks") or []
        if not role or not picks:
            continue
        role_rows.setdefault(role, [])
        for pick in picks:
            if pick.get("character"):
                role_rows[role].append(pick["character"])

    # Collect our pool by role (fallback to global)
    global_pool: Dict[str, float] = {}
    for picks in our_pools.values():
        for champ, w in picks.items():
            global_pool[champ] = global_pool.get(champ, 0.0) + w
    cols = [c for c, _ in sorted(global_pool.items(), key=lambda x: x[1], reverse=True)[:max_cols]]

    matrix_by_role: Dict[str, Any] = {}
    for role, rows in role_rows.items():
        row_list = list(dict.fromkeys(rows))[:max_rows]
        cells = []
        for r in row_list:
            row_cells = []
            for c in cols:
                stats = matchup_table.get((role, c, r))
                if stats:
                    row_cells.append(
                        {
                            "winrate": stats.posterior_winrate(),
                            "samples": stats.games,
                            "confidence": stats.confidence(),
                        }
                    )
                else:
                    row_cells.append({"winrate": None, "samples": 0, "confidence": 0.0})
            cells.append(row_cells)
        matrix_by_role[role] = {"rows": row_list, "cols": cols, "cells": cells}
    return matrix_by_role


def _build_decision_tree(
    counter_matrix: Dict[str, Any],
    draft: Dict[str, Any],
) -> List[Dict[str, Any]]:
    priority = [p.get("character") for p in (draft.get("priority_picks") or []) if p.get("character")]
    nodes: List[Dict[str, Any]] = []
    for role, data in counter_matrix.items():
        rows = data.get("rows") or []
        cols = data.get("cols") or []
        cells = data.get("cells") or []
        for r_idx, opp_pick in enumerate(rows[:3]):
            best = None
            best_score = -1.0
            for c_idx, our_pick in enumerate(cols):
                cell = cells[r_idx][c_idx]
                if cell.get("winrate") is None:
                    continue
                score = (cell["winrate"] or 0) * (cell["confidence"] or 0)
                if score > best_score:
                    best_score = score
                    best = {
                        "our_pick": our_pick,
                        "winrate": cell["winrate"],
                        "samples": cell["samples"],
                        "confidence": cell["confidence"],
                    }
            follow_up = next((p for p in priority if p != opp_pick), None)
            nodes.append(
                {
                    "role": role,
                    "opponent_pick": opp_pick,
                    "answer": best,
                    "follow_up_ban": follow_up,
                }
            )
    return nodes


def build_report(
    games: List[GameRecord],
    meta: FetchMeta,
    our_pools: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, Any]:
    outcomes = compute_match_outcomes(games)
    per_player = compute_per_player_tendencies(games)
    draft = compute_team_draft_tendencies(games)
    coverage = compute_data_coverage(games)
    scenarios, _, clusters = cluster_scenarios_with_labels(games)
    randomness = compute_randomness(games)

    matchup_table = build_matchup_table(games)
    if our_pools is None:
        our_pools = compute_our_pick_pools(games)
    counters = suggest_counters(matchup_table, per_player["per_player"], our_pools)

    plan = _build_plan_template(per_player["per_player"], draft, randomness)
    scenario_viz = _build_scenario_viz(clusters)
    counter_matrix = _build_counter_matrix(matchup_table, per_player["per_player"], our_pools)
    decision_tree = _build_decision_tree(counter_matrix, draft)

    # Stable / comparison insights
    stable_opponent = compute_champion_winrates(games, side="opponent", min_games=3)
    stable_team = compute_champion_winrates(games, side="team", min_games=3)
    roster_opponent = compute_roster_stability(games, side="opponent")
    roster_team = compute_roster_stability(games, side="team")
    style_triangle = compute_style_triangle(games)
    draft_dna_opponent = compute_draft_dna_summary(games, side="opponent")
    counterfactual_bans = compute_counterfactual_bans(games, side="opponent", min_games=3)
    signature_opponent = compute_signature_cluster_cards(games, side="opponent")
    signature_team = compute_signature_cluster_cards(games, side="team")
    player_similarity_opponent = compute_player_similarity(games, side="opponent")
    player_similarity_team = compute_player_similarity(games, side="team")

    stable_opp_set = {c["character"] for c in stable_opponent if c.get("stable")}
    stable_team_set = {c["character"] for c in stable_team if c.get("stable")}
    stable_overlap = sorted(stable_opp_set & stable_team_set)

    missing_data = {
        "bans": draft.get("missing_bans", True),
        "objectives": not coverage.get("has_objectives"),
    }

    return {
        "meta": asdict(meta),
        "data_coverage": coverage,
        "opponent_overview": outcomes,
        "per_player": per_player["per_player"],
        "draft_tendencies": draft,
        "scenarios": [s.__dict__ for s in scenarios],
        "counters": counters,
        "randomness": randomness,
        "plan": plan,
        "insights": {
            "stable_champions": {
                "opponent": [c for c in stable_opponent if c.get("stable")],
                "team": [c for c in stable_team if c.get("stable")],
            },
            "roster_stability": {
                "opponent": roster_opponent,
                "team": roster_team,
            },
            "style_triangle": style_triangle,
            "draft_dna": {
                "opponent": draft_dna_opponent,
            },
            "counterfactual_bans": counterfactual_bans,
            "signature_clusters": {
                "opponent": signature_opponent,
                "team": signature_team,
            },
            "player_similarity": {
                "opponent": player_similarity_opponent,
                "team": player_similarity_team,
            },
            "stable_overlap": {
                "shared_champions": stable_overlap,
                "count": len(stable_overlap),
            },
        },
        "visualization": {
            "strategy_clusters": scenario_viz,
            "scenario_fingerprint_axes": ["early_aggression", "draft_volatility", "teamfightiness", "macro"],
            "objective_timeline": {
                "first_dragon": [],
                "first_herald": [],
                "first_tower": [],
                "kills_by_minute": [],
                "missing": True,
            },
            "counter_matrix": counter_matrix,
            "decision_tree": decision_tree,
        },
        "missing_data": missing_data,
    }
