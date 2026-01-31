from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .features import _entropy
from .normalize import GameRecord


@dataclass
class ScenarioCard:
    scenario_id: int
    share: float
    winrate: float
    signature_picks: Dict[str, str]
    volatility: float
    punish_plan: str


def _hash_feature(key: str, dim: int) -> int:
    return abs(hash(key)) % dim


def _game_vector(game: GameRecord, dim: int = 32) -> List[float]:
    vec = [0.0] * dim
    # role/champion hashed features
    for p in game.opponent.players:
        if p.role and p.character:
            idx = _hash_feature(f"{p.role}:{p.character}", dim)
            vec[idx] += 1.0
    # numeric features
    vec.append(float(game.opponent.kills))
    vec.append(float(game.opponent.deaths))
    vec.append(1.0 if game.opponent.won is True else 0.0)
    return vec


def _euclidean(a: List[float], b: List[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _kmeans_fallback(vectors: List[List[float]], k: int, iterations: int = 10) -> List[int]:
    if not vectors:
        return []
    centers = random.sample(vectors, k) if len(vectors) >= k else [vectors[0]] * k
    labels = [0] * len(vectors)
    for _ in range(iterations):
        for i, v in enumerate(vectors):
            labels[i] = min(range(k), key=lambda c: _euclidean(v, centers[c]))
        for c in range(k):
            cluster = [v for v, lab in zip(vectors, labels) if lab == c]
            if not cluster:
                continue
            centers[c] = [sum(vals) / len(cluster) for vals in zip(*cluster)]
    return labels


def _choose_k(vectors: List[List[float]]) -> int:
    n = len(vectors)
    if n <= 2:
        return max(1, n)
    try:
        from sklearn.cluster import KMeans  # type: ignore
        from sklearn.metrics import silhouette_score  # type: ignore

        best_k = 2
        best_score = -1.0
        for k in range(2, min(4, n) + 1):
            model = KMeans(n_clusters=k, n_init=5, random_state=42)
            labels = model.fit_predict(vectors)
            score = silhouette_score(vectors, labels)
            if score > best_score:
                best_score = score
                best_k = k
        return best_k
    except Exception:
        return min(3, n)


def cluster_scenarios_with_labels(
    games: List[GameRecord],
) -> Tuple[List[ScenarioCard], List[int], Dict[int, List[GameRecord]]]:
    if not games:
        return [], [], {}
    vectors = [_game_vector(g) for g in games]
    k = _choose_k(vectors)
    if k == 1:
        labels = [0] * len(vectors)
    else:
        try:
            from sklearn.cluster import KMeans  # type: ignore

            model = KMeans(n_clusters=k, n_init=5, random_state=42)
            labels = list(model.fit_predict(vectors))
        except Exception:
            labels = _kmeans_fallback(vectors, k)

    clusters: Dict[int, List[GameRecord]] = defaultdict(list)
    for g, label in zip(games, labels):
        clusters[int(label)].append(g)

    cards: List[ScenarioCard] = []
    total_games = len(games)
    for cid, cluster_games in clusters.items():
        if not cluster_games:
            continue
        winrate = sum(1 for g in cluster_games if g.opponent.won is True) / len(cluster_games)
        # signature picks by role
        role_counts: Dict[str, Counter] = defaultdict(Counter)
        champ_counts: Counter = Counter()
        for g in cluster_games:
            for p in g.opponent.players:
                if p.role and p.character:
                    role_counts[p.role][p.character] += 1
                if p.character:
                    champ_counts[p.character] += 1
        signature = {role: cnt.most_common(1)[0][0] for role, cnt in role_counts.items() if cnt}
        volatility = _entropy({k: float(v) for k, v in champ_counts.items()})
        punish = "ban " + ", ".join(list(champ_counts.keys())[:2]) if champ_counts else "deny comfort picks"
        cards.append(
            ScenarioCard(
                scenario_id=cid,
                share=len(cluster_games) / total_games,
                winrate=winrate,
                signature_picks=signature,
                volatility=volatility,
                punish_plan=punish,
            )
        )

    cards_sorted = sorted(cards, key=lambda c: c.share, reverse=True)
    return cards_sorted, labels, clusters


def cluster_scenarios(games: List[GameRecord]) -> List[ScenarioCard]:
    cards, _, _ = cluster_scenarios_with_labels(games)
    return cards
