from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .normalize import GameRecord, PlayerPerf


def _parse_time(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _recency_weight(ts: str, half_life_days: float = 30.0) -> float:
    dt = _parse_time(ts)
    if not dt:
        return 1.0
    age_days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0
    if age_days <= 0:
        return 1.0
    return math.exp(-math.log(2) * age_days / half_life_days)


def _entropy(counts: Dict[str, float]) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    probs = [v / total for v in counts.values() if v > 0]
    if not probs:
        return 0.0
    ent = -sum(p * math.log(p, 2) for p in probs)
    max_ent = math.log(len(probs), 2) if len(probs) > 1 else 1.0
    if max_ent == 0:
        return 0.0
    return ent / max_ent


def _top_comfort_picks(weighted_counts: Dict[str, float]) -> List[Dict[str, Any]]:
    total = sum(weighted_counts.values())
    if total <= 0:
        return []
    items = sorted(weighted_counts.items(), key=lambda x: x[1], reverse=True)
    comfort: List[Dict[str, Any]] = []
    acc = 0.0
    for champ, w in items:
        acc += w
        comfort.append({"character": champ, "weight": w, "share": w / total})
        if acc / total >= 0.5:
            break
    return comfort


def _iter_side_states(games: List[GameRecord], side: str) -> List[Tuple[GameRecord, PlayerPerf, Any]]:
    out: List[Tuple[GameRecord, PlayerPerf, Any]] = []
    for g in games:
        state = g.opponent if side == "opponent" else g.team
        for p in state.players:
            out.append((g, p, state))
    return out


def compute_champion_winrates(
    games: List[GameRecord], side: str, min_games: int = 3
) -> List[Dict[str, Any]]:
    counts: Dict[str, int] = defaultdict(int)
    wins: Dict[str, int] = defaultdict(int)
    for g in games:
        state = g.opponent if side == "opponent" else g.team
        if state.won is None:
            continue
        for p in state.players:
            if not p.character:
                continue
            counts[p.character] += 1
            if state.won is True:
                wins[p.character] += 1

    rows: List[Dict[str, Any]] = []
    for champ, n in counts.items():
        winrate = (wins[champ] / n) if n else 0.0
        rows.append(
            {
                "character": champ,
                "games": n,
                "wins": wins[champ],
                "winrate": winrate,
                "stable": n >= min_games,
            }
        )
    rows.sort(key=lambda r: (r["stable"], r["games"], r["winrate"]), reverse=True)
    return rows


def compute_roster_stability(games: List[GameRecord], side: str) -> Dict[str, Any]:
    player_games: Dict[str, int] = defaultdict(int)
    total = 0
    for g in games:
        state = g.opponent if side == "opponent" else g.team
        seen = set()
        for p in state.players:
            if p.player_id:
                seen.add(p.player_id)
        for pid in seen:
            player_games[pid] += 1
        total += 1
    top5 = sum(v for _, v in sorted(player_games.items(), key=lambda x: x[1], reverse=True)[:5])
    stability = (top5 / total) if total else 0.0
    return {
        "unique_players": len(player_games),
        "games_total": total,
        "top5_share": stability,
    }


def compute_style_triangle(games: List[GameRecord]) -> Dict[str, Any]:
    def _style_for(side: str) -> Dict[str, float]:
        kills = 0
        deaths = 0
        wins = 0
        total = 0
        win_list: List[float] = []
        champ_counts: Dict[str, int] = defaultdict(int)
        for g in games:
            state = g.opponent if side == "opponent" else g.team
            kills += state.kills
            deaths += state.deaths
            total += 1
            if state.won is True:
                wins += 1
                win_list.append(1.0)
            elif state.won is False:
                win_list.append(0.0)
            for p in state.players:
                if p.character:
                    champ_counts[p.character] += 1
        aggression = (kills / (kills + deaths)) if (kills + deaths) else 0.0
        winrate = (wins / total) if total else 0.0
        winrate_std = float((sum((w - winrate) ** 2 for w in win_list) / len(win_list)) ** 0.5) if win_list else 0.0
        control = (1.0 / (1.0 + (deaths / total))) + (1.0 / (1.0 + winrate_std)) if total else 0.0
        flex = _entropy({k: float(v) for k, v in champ_counts.items()})
        roster = compute_roster_stability(games, side).get("top5_share", 0.0)
        flexibility = flex * (1.0 + roster)
        return {
            "aggression_raw": aggression,
            "control_raw": control,
            "flexibility_raw": flexibility,
        }

    team = _style_for("team")
    opp = _style_for("opponent")
    # Normalize between the two for relative comparison
    def _norm(a: float, b: float) -> Tuple[float, float]:
        lo = min(a, b)
        hi = max(a, b)
        if hi == lo:
            return (0.5, 0.5)
        return ((a - lo) / (hi - lo), (b - lo) / (hi - lo))

    team_ag, opp_ag = _norm(team["aggression_raw"], opp["aggression_raw"])
    team_ctrl, opp_ctrl = _norm(team["control_raw"], opp["control_raw"])
    team_flex, opp_flex = _norm(team["flexibility_raw"], opp["flexibility_raw"])

    return {
        "team": {
            **team,
            "aggression": team_ag,
            "control": team_ctrl,
            "flexibility": team_flex,
        },
        "opponent": {
            **opp,
            "aggression": opp_ag,
            "control": opp_ctrl,
            "flexibility": opp_flex,
        },
    }


def compute_draft_dna_summary(
    games: List[GameRecord],
    side: str,
    top_n: int = 50,
    similarity_threshold: float = 0.75,
) -> Dict[str, Any]:
    # Build feature vectors per game for a side
    champ_vocab: List[str] = []
    champ_counts: Dict[str, int] = defaultdict(int)
    for g in games:
        state = g.opponent if side == "opponent" else g.team
        for p in state.players:
            if p.character:
                champ_counts[p.character] += 1
    champ_vocab = [c for c, _ in sorted(champ_counts.items(), key=lambda x: x[1], reverse=True)[:top_n]]
    champ_index = {c: i for i, c in enumerate(champ_vocab)}

    rows: List[Dict[str, Any]] = []
    for g in games:
        state = g.opponent if side == "opponent" else g.team
        champs = {p.character for p in state.players if p.character}
        roles = Counter(p.role for p in state.players if p.role)
        rows.append(
            {
                "series_id": g.series_id,
                "game_number": g.game_number,
                "won": 1.0 if state.won is True else 0.0,
                "tempo": float(state.kills + state.deaths),
                "champs": champs,
                "roles": roles,
            }
        )

    if not rows:
        return {
            "games": 0,
            "avg_nn_similarity": 0.0,
            "similarity_coverage": 0.0,
            "nearest_neighbors": [],
        }

    role_keys = sorted({r for row in rows for r in row["roles"].keys() if r})
    role_index = {r: i for i, r in enumerate(role_keys)}

    X = []
    for row in rows:
        vec = [0.0] * (len(champ_vocab) + len(role_keys) + 2)
        for c in row["champs"]:
            idx = champ_index.get(c)
            if idx is not None:
                vec[idx] = 1.0
        offset = len(champ_vocab)
        for r, cnt in row["roles"].items():
            ridx = role_index.get(r)
            if ridx is not None:
                vec[offset + ridx] = float(cnt)
        vec[-2] = row["won"]
        vec[-1] = row["tempo"]
        X.append(vec)

    # cosine similarity
    def _cos(a: List[float], b: List[float]) -> float:
        num = sum(x * y for x, y in zip(a, b))
        da = math.sqrt(sum(x * x for x in a))
        db = math.sqrt(sum(y * y for y in b))
        if da == 0 or db == 0:
            return 0.0
        return num / (da * db)

    sims = []
    neighbors: List[Dict[str, Any]] = []
    for i in range(len(X)):
        best = (-1.0, None)
        for j in range(len(X)):
            if i == j:
                continue
            s = _cos(X[i], X[j])
            if s > best[0]:
                best = (s, j)
        sims.append(best[0])
        if best[1] is not None:
            neighbors.append(
                {
                    "game": {"series_id": rows[i]["series_id"], "game_number": rows[i]["game_number"]},
                    "nearest": {"series_id": rows[best[1]]["series_id"], "game_number": rows[best[1]]["game_number"]},
                    "similarity": best[0],
                }
            )

    avg_nn = sum(sims) / len(sims) if sims else 0.0
    coverage = sum(1 for s in sims if s >= similarity_threshold) / len(sims) if sims else 0.0

    neighbors.sort(key=lambda x: x["similarity"], reverse=True)
    return {
        "games": len(rows),
        "avg_nn_similarity": avg_nn,
        "similarity_coverage": coverage,
        "nearest_neighbors": neighbors[:10],
        "similarity_threshold": similarity_threshold,
    }


def compute_signature_cluster_cards(
    games: List[GameRecord],
    side: str,
    top_n: int = 50,
    max_clusters: int = 4,
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    champ_counts: Dict[str, int] = defaultdict(int)
    for g in games:
        state = g.opponent if side == "opponent" else g.team
        champs = {p.character for p in state.players if p.character}
        roles = Counter(p.role for p in state.players if p.role)
        for c in champs:
            champ_counts[c] += 1
        rows.append(
            {
                "series_id": g.series_id,
                "game_number": g.game_number,
                "won": 1.0 if state.won is True else 0.0,
                "tempo": float(state.kills + state.deaths),
                "champs": champs,
                "roles": roles,
            }
        )

    if not rows:
        return {"games": 0, "k": 0, "primary_cluster": None, "clusters": []}

    champ_vocab = [c for c, _ in sorted(champ_counts.items(), key=lambda x: x[1], reverse=True)[:top_n]]
    champ_index = {c: i for i, c in enumerate(champ_vocab)}
    role_keys = sorted({r for row in rows for r in row["roles"].keys() if r})
    role_index = {r: i for i, r in enumerate(role_keys)}

    X: List[List[float]] = []
    for row in rows:
        vec = [0.0] * (len(champ_vocab) + len(role_keys) + 2)
        for c in row["champs"]:
            idx = champ_index.get(c)
            if idx is not None:
                vec[idx] = 1.0
        offset = len(champ_vocab)
        for r, cnt in row["roles"].items():
            ridx = role_index.get(r)
            if ridx is not None:
                vec[offset + ridx] = float(cnt)
        vec[-2] = row["won"]
        vec[-1] = row["tempo"]
        X.append(vec)

    n = len(X)
    k = min(max_clusters, n)
    if n <= 1:
        labels = [0] * n
        k = 1
    else:
        try:
            from sklearn.cluster import KMeans  # type: ignore
            from sklearn.metrics import silhouette_score  # type: ignore

            best_k = 2
            best_score = -1.0
            for cand in range(2, min(max_clusters, n) + 1):
                model = KMeans(n_clusters=cand, n_init=5, random_state=42)
                cand_labels = model.fit_predict(X)
                score = silhouette_score(X, cand_labels) if n > cand else -1.0
                if score > best_score:
                    best_score = score
                    best_k = cand
            model = KMeans(n_clusters=best_k, n_init=5, random_state=42)
            labels = list(model.fit_predict(X))
            k = best_k
        except Exception:
            # simple fallback: split by tempo median
            median = sorted(row["tempo"] for row in rows)[len(rows) // 2]
            labels = [0 if row["tempo"] <= median else 1 for row in rows]
            k = 2

    clusters: Dict[int, List[int]] = defaultdict(list)
    for idx, lab in enumerate(labels):
        clusters[int(lab)].append(idx)

    cards: List[Dict[str, Any]] = []
    for cid, idxs in clusters.items():
        win_vals = [rows[i]["won"] for i in idxs if rows[i]["won"] in (0.0, 1.0)]
        winrate = sum(win_vals) / len(win_vals) if win_vals else None
        champ_counter: Counter = Counter()
        for i in idxs:
            champ_counter.update(rows[i]["champs"])
        cards.append(
            {
                "cluster_id": cid,
                "share": len(idxs) / n,
                "winrate": winrate,
                "top_champs": [c for c, _ in champ_counter.most_common(6)],
            }
        )

    cards.sort(key=lambda c: c["share"], reverse=True)
    primary = cards[0] if cards else None
    return {
        "games": n,
        "k": k,
        "primary_cluster": primary,
        "clusters": cards,
    }


def compute_player_similarity(
    games: List[GameRecord],
    side: str,
    min_unique_champs: int = 3,
    top_pairs: int = 30,
) -> Dict[str, Any]:
    pools: Dict[str, set] = defaultdict(set)
    names: Dict[str, Optional[str]] = {}
    for g in games:
        state = g.opponent if side == "opponent" else g.team
        for p in state.players:
            if not p.player_id or not p.character:
                continue
            pools[p.player_id].add(p.character)
            if p.name:
                names[p.player_id] = p.name

    players = [pid for pid, champs in pools.items() if len(champs) >= min_unique_champs]
    edges: List[Dict[str, Any]] = []
    for i in range(len(players)):
        for j in range(i + 1, len(players)):
            a = players[i]
            b = players[j]
            inter = pools[a] & pools[b]
            union = pools[a] | pools[b]
            if not union:
                continue
            sim = len(inter) / len(union)
            if sim <= 0:
                continue
            edges.append(
                {
                    "player_a": {"id": a, "name": names.get(a)},
                    "player_b": {"id": b, "name": names.get(b)},
                    "similarity": sim,
                    "shared_champs": sorted(inter),
                    "pool_sizes": {"a": len(pools[a]), "b": len(pools[b])},
                }
            )

    edges.sort(key=lambda e: e["similarity"], reverse=True)
    return {
        "players": [{"id": pid, "name": names.get(pid), "pool_size": len(pools[pid])} for pid in players],
        "edges": edges[:top_pairs],
        "min_unique_champs": min_unique_champs,
    }


def compute_counterfactual_bans(
    games: List[GameRecord], side: str, min_games: int = 3
) -> List[Dict[str, Any]]:
    champ_stats = compute_champion_winrates(games, side, min_games=min_games)
    out: List[Dict[str, Any]] = []
    # For each team (here: only one side), pick top champs by games
    if len(champ_stats) < 2:
        return out
    top = champ_stats[0]
    replacement = champ_stats[1]
    if top["games"] < min_games or replacement["games"] < min_games:
        return out
    drop = top["winrate"] - replacement["winrate"]
    out.append(
        {
            "ban_champ": top["character"],
            "ban_games": top["games"],
            "ban_winrate": top["winrate"],
            "replacement": replacement["character"],
            "replacement_winrate": replacement["winrate"],
            "estimated_winrate_drop": drop,
        }
    )
    return out


def compute_per_player_tendencies(games: List[GameRecord]) -> Dict[str, Any]:
    per_player_counts: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    per_player_roles: Dict[str, Counter] = defaultdict(Counter)
    per_player_names: Dict[str, Optional[str]] = {}

    games_with_chars = 0
    for g in games:
        w = _recency_weight(g.start_time)
        has_char = False
        for p in g.opponent.players:
            if not p.player_id:
                continue
            if p.character:
                per_player_counts[p.player_id][p.character] += w
                has_char = True
            if p.role:
                per_player_roles[p.player_id][p.role] += 1
            per_player_names[p.player_id] = p.name
        if has_char:
            games_with_chars += 1

    per_player: Dict[str, Any] = {}
    for pid, counts in per_player_counts.items():
        comfort = _top_comfort_picks(counts)
        volatility = _entropy(counts)
        total = sum(counts.values())
        pick_rates = [
            {"character": champ, "weight": w, "share": (w / total if total else 0.0)}
            for champ, w in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        ]
        roles = per_player_roles.get(pid)
        role = None
        if roles:
            role = roles.most_common(1)[0][0]
        per_player[pid] = {
            "player_id": pid,
            "name": per_player_names.get(pid),
            "role": role,
            "comfort_picks": comfort,
            "pick_distribution": pick_rates,
            "volatility": volatility,
        }

    return {
        "per_player": per_player,
        "games_with_player_chars": games_with_chars,
        "games_total": len(games),
    }


def compute_team_draft_tendencies(games: List[GameRecord]) -> Dict[str, Any]:
    team_counts: Dict[str, float] = defaultdict(float)
    roles_by_champ: Dict[str, set] = defaultdict(set)
    for g in games:
        w = _recency_weight(g.start_time)
        for p in g.opponent.players:
            if p.character:
                team_counts[p.character] += w
                if p.role:
                    roles_by_champ[p.character].add(p.role)

    total = sum(team_counts.values())
    priority = [
        {"character": champ, "weight": w, "share": (w / total if total else 0.0)}
        for champ, w in sorted(team_counts.items(), key=lambda x: x[1], reverse=True)
    ]
    flex = [champ for champ, roles in roles_by_champ.items() if len(roles) >= 2]

    return {
        "priority_picks": priority[:10],
        "bans": [],
        "flex_picks": flex,
        "missing_bans": True,
    }


def compute_match_outcomes(games: List[GameRecord]) -> Dict[str, Any]:
    wins = sum(1 for g in games if g.opponent.won is True)
    losses = sum(1 for g in games if g.opponent.won is False)
    kills = sum(g.opponent.kills for g in games)
    deaths = sum(g.opponent.deaths for g in games)
    total = len(games)
    return {
        "games": total,
        "wins": wins,
        "losses": losses,
        "avg_kills": (kills / total) if total else 0.0,
        "avg_deaths": (deaths / total) if total else 0.0,
    }


def compute_data_coverage(games: List[GameRecord]) -> Dict[str, Any]:
    total = len(games)
    with_char = 0
    with_role = 0
    for g in games:
        if any(p.character for p in g.opponent.players):
            with_char += 1
        if any(p.role for p in g.opponent.players):
            with_role += 1

    return {
        "games_total": total,
        "games_with_player_chars": with_char,
        "games_with_roles": with_role,
        "has_objectives": False,
    }
