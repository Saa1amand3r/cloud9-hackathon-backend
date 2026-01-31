"""
Enhanced scouting insights with pro-player friendly language.

This module generates textual analysis and actionable insights
using terminology that professional LoL players understand.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .normalize import GameRecord, PlayerPerf


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _parse_time(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _days_ago(ts: str) -> float:
    dt = _parse_time(ts)
    if not dt:
        return 999.0
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0


def _winrate_label(wr: float) -> str:
    """Convert winrate to human-readable assessment."""
    if wr >= 0.65:
        return "dominant"
    elif wr >= 0.55:
        return "strong"
    elif wr >= 0.45:
        return "average"
    elif wr >= 0.35:
        return "struggling"
    else:
        return "weak"


def _pool_depth_label(unique_champs: int, total_games: int) -> str:
    """Classify champion pool depth."""
    if total_games == 0:
        return "unknown"
    ratio = unique_champs / total_games
    if unique_champs <= 3 or ratio < 0.15:
        return "one-trick"
    elif unique_champs <= 5 or ratio < 0.25:
        return "shallow"
    elif unique_champs <= 8 or ratio < 0.4:
        return "moderate"
    else:
        return "deep"


def _threat_level(winrate: float, games: int, comfort_share: float) -> str:
    """Assess player threat level based on performance."""
    if games < 3:
        return "unknown"

    score = 0
    # Winrate contribution
    if winrate >= 0.6:
        score += 3
    elif winrate >= 0.5:
        score += 2
    elif winrate >= 0.4:
        score += 1

    # Experience contribution
    if games >= 20:
        score += 2
    elif games >= 10:
        score += 1

    # Comfort/predictability (high comfort = easier to prepare for, but also means they're good on it)
    if comfort_share >= 0.5:
        score += 1  # They have clear strengths

    if score >= 5:
        return "critical"
    elif score >= 4:
        return "high"
    elif score >= 2:
        return "medium"
    else:
        return "low"


def _recent_form_label(recent_wr: float, overall_wr: float) -> str:
    """Assess if player is trending up or down."""
    diff = recent_wr - overall_wr
    if diff >= 0.15:
        return "hot"
    elif diff >= 0.05:
        return "trending up"
    elif diff <= -0.15:
        return "cold"
    elif diff <= -0.05:
        return "trending down"
    else:
        return "stable"


def _playstyle_label(kills_per_game: float, deaths_per_game: float) -> str:
    """Classify playstyle based on K/D patterns."""
    kd = kills_per_game / deaths_per_game if deaths_per_game > 0 else kills_per_game
    aggression = kills_per_game + deaths_per_game

    if aggression > 8 and kd >= 1.5:
        return "aggressive carry"
    elif aggression > 8 and kd < 1.0:
        return "coinflip"
    elif aggression > 6 and kd >= 1.2:
        return "calculated aggression"
    elif aggression <= 4 and kd >= 1.5:
        return "safe/controlled"
    elif kd < 0.8:
        return "liability"
    else:
        return "balanced"


# =============================================================================
# EXECUTIVE SUMMARY
# =============================================================================

def generate_executive_summary(
    games: List[GameRecord],
    per_player: Dict[str, Any],
    scenarios: List[Any],
    randomness: Dict[str, Any],
    opponent_name: str,
) -> Dict[str, Any]:
    """
    Generate a high-level executive summary for coaches/players.
    """
    if not games:
        return {
            "headline": f"Insufficient data on {opponent_name}",
            "profile": "Not enough games to analyze.",
            "key_strengths": [],
            "key_weaknesses": [],
            "game_plan": "Gather more data before preparing.",
            "risk_level": "unknown",
            "confidence": "low",
        }

    # Basic stats
    total_games = len(games)
    wins = sum(1 for g in games if g.opponent.won is True)
    winrate = wins / total_games if total_games else 0

    # Recent form (last 30 days)
    recent_games = [g for g in games if _days_ago(g.start_time) <= 30]
    recent_wins = sum(1 for g in recent_games if g.opponent.won is True)
    recent_wr = recent_wins / len(recent_games) if recent_games else winrate

    # Determine predictability
    rand_score = randomness.get("score", 50)
    if rand_score < 35:
        predictability = "very predictable"
        draft_advice = "You can hard-read their drafts"
    elif rand_score < 50:
        predictability = "fairly predictable"
        draft_advice = "Target their comfort picks in bans"
    elif rand_score < 65:
        predictability = "moderately flexible"
        draft_advice = "Prepare for 2-3 different styles"
    else:
        predictability = "unpredictable"
        draft_advice = "Stay flexible, don't over-commit to one read"

    # Find star players (highest threat)
    star_players = []
    weak_links = []
    for pid, pdata in per_player.items():
        name = pdata.get("name") or pid
        role = pdata.get("role") or "unknown"
        comfort = pdata.get("comfort_picks", [])
        top_share = comfort[0].get("share", 0) if comfort else 0

        # Calculate player winrate from games
        player_games = 0
        player_wins = 0
        for g in games:
            for p in g.opponent.players:
                if p.player_id == pid:
                    player_games += 1
                    if g.opponent.won:
                        player_wins += 1
                    break

        player_wr = player_wins / player_games if player_games > 0 else 0
        threat = _threat_level(player_wr, player_games, top_share)

        if threat in ("critical", "high"):
            star_players.append({"name": name, "role": role, "threat": threat})
        elif threat == "low" and player_games >= 5:
            weak_links.append({"name": name, "role": role})

    # Key strengths
    strengths = []
    if winrate >= 0.55:
        strengths.append(f"Strong overall record ({wins}W-{total_games - wins}L, {winrate:.0%} winrate)")
    if recent_wr > winrate + 0.1:
        strengths.append("Currently in good form - trending upward")
    if star_players:
        star_names = ", ".join([f"{s['name']} ({s['role']})" for s in star_players[:2]])
        strengths.append(f"Star player(s): {star_names}")
    if rand_score >= 60:
        strengths.append("Diverse champion pools - hard to ban out")

    # Get most winning scenario
    if scenarios:
        best_scenario = max(scenarios, key=lambda s: s.get("winrate", 0) if isinstance(s, dict) else getattr(s, "winrate", 0))
        if isinstance(best_scenario, dict):
            best_wr = best_scenario.get("winrate", 0)
            best_picks = best_scenario.get("signature_picks", {})
        else:
            best_wr = getattr(best_scenario, "winrate", 0)
            best_picks = getattr(best_scenario, "signature_picks", {})

        if best_wr >= 0.6 and best_picks:
            pick_str = ", ".join([f"{v}" for v in list(best_picks.values())[:3]])
            strengths.append(f"Deadly on their primary comp ({best_wr:.0%} WR): {pick_str}")

    # Key weaknesses
    weaknesses = []
    if winrate < 0.45:
        weaknesses.append(f"Struggling overall ({wins}W-{total_games - wins}L)")
    if recent_wr < winrate - 0.1:
        weaknesses.append("Currently slumping - form is down")
    if weak_links:
        weak_names = ", ".join([f"{w['name']} ({w['role']})" for w in weak_links[:2]])
        weaknesses.append(f"Exploitable player(s): {weak_names}")
    if rand_score < 40:
        weaknesses.append("Predictable drafts - easy to prepare specific counters")

    # Find their worst scenario
    if scenarios:
        worst_scenario = min(scenarios, key=lambda s: s.get("winrate", 1) if isinstance(s, dict) else getattr(s, "winrate", 1))
        if isinstance(worst_scenario, dict):
            worst_wr = worst_scenario.get("winrate", 0)
        else:
            worst_wr = getattr(worst_scenario, "winrate", 0)
        if worst_wr < 0.4:
            weaknesses.append(f"Vulnerable when forced off comfort ({worst_wr:.0%} WR in uncomfortable games)")

    # Risk assessment
    if rand_score >= 65 or (recent_wr >= 0.6 and winrate < 0.5):
        risk_level = "high"
        risk_note = "Expect surprises - they can pop off"
    elif rand_score >= 50 or winrate >= 0.5:
        risk_level = "medium"
        risk_note = "Solid opponent - respect their strengths"
    else:
        risk_level = "low"
        risk_note = "Beatable if you execute your game plan"

    # Generate headline
    if winrate >= 0.6:
        headline = f"{opponent_name}: Top-tier opponent - prepare thoroughly"
    elif winrate >= 0.5:
        headline = f"{opponent_name}: Competitive matchup - execution matters"
    elif winrate >= 0.4:
        headline = f"{opponent_name}: Winnable matchup - don't underestimate"
    else:
        headline = f"{opponent_name}: Favorable matchup - stay focused"

    # Profile paragraph
    profile = (
        f"{opponent_name} has played {total_games} games in the analyzed window "
        f"with a {winrate:.0%} winrate ({wins}W-{total_games - wins}L). "
        f"They are {predictability} in draft. "
        f"{draft_advice}. {risk_note}."
    )

    # Game plan
    game_plan_parts = []
    if weaknesses:
        game_plan_parts.append(f"Exploit: {weaknesses[0].lower()}")
    if strengths:
        game_plan_parts.append(f"Respect: {strengths[0].lower() if len(strengths) > 0 else 'their best players'}")
    game_plan_parts.append(draft_advice)

    game_plan = ". ".join(game_plan_parts) + "."

    return {
        "headline": headline,
        "profile": profile,
        "key_strengths": strengths[:4],
        "key_weaknesses": weaknesses[:4],
        "game_plan": game_plan,
        "risk_level": risk_level,
        "confidence": "high" if total_games >= 15 else "medium" if total_games >= 8 else "low",
        "games_analyzed": total_games,
        "overall_winrate": winrate,
        "recent_winrate": recent_wr,
    }


# =============================================================================
# ENHANCED PLAYER CARDS
# =============================================================================

def enhance_player_cards(
    games: List[GameRecord],
    per_player: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Add pro-friendly insights to each player card.
    """
    enhanced = {}

    for pid, pdata in per_player.items():
        name = pdata.get("name") or pid
        role = pdata.get("role") or "unknown"
        comfort_picks = pdata.get("comfort_picks", [])
        pick_distribution = pdata.get("pick_distribution", [])

        # Calculate stats from games
        player_games = []
        total_kills = 0
        total_deaths = 0
        wins = 0
        recent_wins = 0
        recent_games_count = 0
        champs_played = set()

        for g in games:
            for p in g.opponent.players:
                if p.player_id == pid:
                    player_games.append(g)
                    total_kills += p.kills
                    total_deaths += p.deaths
                    if p.character:
                        champs_played.add(p.character)
                    if g.opponent.won:
                        wins += 1
                    # Recent = last 30 days
                    if _days_ago(g.start_time) <= 30:
                        recent_games_count += 1
                        if g.opponent.won:
                            recent_wins += 1
                    break

        num_games = len(player_games)
        if num_games == 0:
            enhanced[pid] = {
                **pdata,
                "scouting_notes": f"No games found for {name}.",
                "threat_level": "unknown",
                "champion_pool_depth": "unknown",
                "recent_form": "unknown",
                "playstyle": "unknown",
            }
            continue

        # Calculate metrics
        winrate = wins / num_games
        recent_wr = recent_wins / recent_games_count if recent_games_count > 0 else winrate
        kills_per_game = total_kills / num_games
        deaths_per_game = total_deaths / num_games
        kda = (total_kills / total_deaths) if total_deaths > 0 else total_kills

        top_share = comfort_picks[0].get("share", 0) if comfort_picks else 0
        top_champ = comfort_picks[0].get("character", "unknown") if comfort_picks else "unknown"

        # Generate labels
        pool_depth = _pool_depth_label(len(champs_played), num_games)
        threat = _threat_level(winrate, num_games, top_share)
        form = _recent_form_label(recent_wr, winrate)
        playstyle = _playstyle_label(kills_per_game, deaths_per_game)

        # Exploitable patterns
        exploitable = []
        if pool_depth == "one-trick":
            exploitable.append(f"Ban {top_champ} - they rely on it heavily ({top_share:.0%} of games)")
        elif pool_depth == "shallow" and top_share >= 0.4:
            exploitable.append(f"Target ban {top_champ} to limit their options")

        if playstyle == "coinflip":
            exploitable.append("Plays aggressive but dies a lot - punish overextensions")
        elif playstyle == "liability":
            exploitable.append("Weak link - focus resources against this lane")

        if form in ("cold", "trending down"):
            exploitable.append("Currently struggling - apply early pressure")

        # Scouting notes
        notes_parts = []

        # Opening line about the player
        if threat == "critical":
            notes_parts.append(f"{name} is a major threat on {role}")
        elif threat == "high":
            notes_parts.append(f"{name} is a strong {role} player")
        elif threat == "medium":
            notes_parts.append(f"{name} is a solid {role}")
        else:
            notes_parts.append(f"{name} is a serviceable {role}")

        # Champion pool
        if pool_depth == "one-trick":
            notes_parts.append(f"with a tiny champion pool centered on {top_champ}")
        elif pool_depth == "shallow":
            top_2 = ", ".join([p.get("character", "") for p in comfort_picks[:2]])
            notes_parts.append(f"who mainly plays {top_2}")
        elif pool_depth == "deep":
            notes_parts.append("with a deep, flexible champion pool")
        else:
            notes_parts.append(f"with a decent pool")

        # Performance
        notes_parts.append(f"({winrate:.0%} WR, {kda:.1f} KDA).")

        # Form
        if form == "hot":
            notes_parts.append("Currently on fire - respect their confidence.")
        elif form == "cold":
            notes_parts.append("Currently slumping - might be tilted.")

        # Playstyle note
        if playstyle == "aggressive carry":
            notes_parts.append("Plays aggressively and usually delivers.")
        elif playstyle == "coinflip":
            notes_parts.append("Coinflip player - can carry or int.")
        elif playstyle == "safe/controlled":
            notes_parts.append("Plays safe and scales.")

        scouting_notes = " ".join(notes_parts)

        enhanced[pid] = {
            **pdata,
            "scouting_notes": scouting_notes,
            "threat_level": threat,
            "champion_pool_depth": pool_depth,
            "recent_form": form,
            "playstyle": playstyle,
            "exploitable_patterns": exploitable if exploitable else ["No obvious weaknesses"],
            "stats": {
                "games": num_games,
                "winrate": winrate,
                "recent_winrate": recent_wr,
                "kda": kda,
                "kills_per_game": kills_per_game,
                "deaths_per_game": deaths_per_game,
                "unique_champions": len(champs_played),
            },
        }

    return enhanced


# =============================================================================
# ENHANCED SCENARIOS (WIN CONDITIONS)
# =============================================================================

def enhance_scenarios(
    games: List[GameRecord],
    scenarios: List[Any],
    clusters: Dict[int, List[GameRecord]],
) -> List[Dict[str, Any]]:
    """
    Add win conditions and counter-strategies to each scenario.
    """
    enhanced = []

    for scenario in scenarios:
        if isinstance(scenario, dict):
            sid = scenario.get("scenario_id", 0)
            share = scenario.get("share", 0)
            winrate = scenario.get("winrate", 0)
            sig_picks = scenario.get("signature_picks", {})
            volatility = scenario.get("volatility", 0)
        else:
            sid = getattr(scenario, "scenario_id", 0)
            share = getattr(scenario, "share", 0)
            winrate = getattr(scenario, "winrate", 0)
            sig_picks = getattr(scenario, "signature_picks", {})
            volatility = getattr(scenario, "volatility", 0)

        cluster_games = clusters.get(sid, [])

        # Analyze this cluster's games
        total_kills = sum(g.opponent.kills for g in cluster_games)
        total_deaths = sum(g.opponent.deaths for g in cluster_games)
        num_games = len(cluster_games) if cluster_games else 1

        kills_per_game = total_kills / num_games
        deaths_per_game = total_deaths / num_games

        # Determine playstyle name
        if kills_per_game >= 15 and deaths_per_game >= 12:
            style_name = "Fiesta/Brawl"
            tempo = "high-tempo"
        elif kills_per_game >= 12:
            style_name = "Aggressive Early"
            tempo = "early-game"
        elif kills_per_game <= 8 and deaths_per_game <= 8:
            style_name = "Slow/Scaling"
            tempo = "late-game"
        else:
            style_name = "Standard"
            tempo = "mid-game"

        # Win conditions (how they win with this style)
        win_conditions = []
        if tempo == "early-game":
            win_conditions.append("Snowball early leads through aggressive plays")
            win_conditions.append("Convert kills into objectives quickly")
        elif tempo == "late-game":
            win_conditions.append("Scale to teamfight phase with carries online")
            win_conditions.append("Play for soul and baron")
        elif tempo == "high-tempo":
            win_conditions.append("Force fights constantly and outskirmish")
            win_conditions.append("Win through chaos and mechanical outplays")
        else:
            win_conditions.append("Play standard macro and win through better decisions")
            win_conditions.append("Secure neutral objectives and teamfight")

        # How they lose (loss patterns)
        loss_patterns = []
        if tempo == "early-game":
            loss_patterns.append("Get outscaled if they don't get ahead")
            loss_patterns.append("Throw leads by forcing bad fights")
        elif tempo == "late-game":
            loss_patterns.append("Get crushed early before they can scale")
            loss_patterns.append("Lose too many objectives pre-20")
        elif tempo == "high-tempo":
            loss_patterns.append("Controlled teams that don't engage in fiestas beat them")
            loss_patterns.append("Punish their aggression with counterengage")
        else:
            loss_patterns.append("Better macro teams outrotate them")
            loss_patterns.append("Lose to teams with clearer win conditions")

        # Counter strategy
        counter_strategy = []
        if tempo == "early-game":
            counter_strategy.append("Draft for scaling and survive the early game")
            counter_strategy.append("Ward aggressively to spot their roams/invades")
            counter_strategy.append("Don't fight unless you have to - let them come to you")
        elif tempo == "late-game":
            counter_strategy.append("Draft strong early/mid game champions")
            counter_strategy.append("Force fights before their carries are online")
            counter_strategy.append("Invade and contest every neutral objective")
        elif tempo == "high-tempo":
            counter_strategy.append("Pick disengage and counterengage tools")
            counter_strategy.append("Don't match their chaos - play controlled")
            counter_strategy.append("Punish overaggression with cc chains")
        else:
            counter_strategy.append("Have a clear game plan and execute")
            counter_strategy.append("Match their draft power or counter their flex picks")

        # Draft recommendations for this scenario
        if sig_picks:
            key_picks = list(sig_picks.values())[:3]
            if winrate >= 0.55:
                counter_strategy.insert(0, f"Consider banning: {', '.join(key_picks)}")

        # Volatility interpretation
        if volatility < 0.3:
            flexibility = "rigid"
            flexibility_note = "They run the same comp every time - easy to prepare for"
        elif volatility < 0.5:
            flexibility = "focused"
            flexibility_note = "Limited variations - you can predict their picks"
        elif volatility < 0.7:
            flexibility = "moderate"
            flexibility_note = "Some variety but clear preferences"
        else:
            flexibility = "flexible"
            flexibility_note = "Hard to predict exact picks"

        enhanced.append({
            "scenario_id": sid,
            "name": style_name,
            "share": share,
            "share_label": f"{share:.0%} of their games",
            "winrate": winrate,
            "winrate_label": _winrate_label(winrate),
            "signature_picks": sig_picks,
            "tempo": tempo,
            "flexibility": flexibility,
            "flexibility_note": flexibility_note,
            "stats": {
                "games": num_games,
                "avg_kills": kills_per_game,
                "avg_deaths": deaths_per_game,
            },
            "win_conditions": win_conditions,
            "loss_patterns": loss_patterns,
            "how_to_beat": counter_strategy,
        })

    return enhanced


# =============================================================================
# DRAFT GUIDE
# =============================================================================

def generate_draft_guide(
    games: List[GameRecord],
    per_player: Dict[str, Any],
    draft_tendencies: Dict[str, Any],
    counters: Dict[str, Any],
    randomness: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate actionable draft recommendations.
    """
    priority_picks = draft_tendencies.get("priority_picks", [])
    flex_picks = draft_tendencies.get("flex_picks", [])

    # Must ban - their highest priority + one-tricks
    must_ban = []
    for pick in priority_picks[:2]:
        champ = pick.get("character")
        share = pick.get("share", 0)
        if champ and share >= 0.15:
            must_ban.append({
                "champion": champ,
                "reason": f"High priority pick ({share:.0%} of games)",
                "priority": 1,
            })

    # Add one-trick bans
    for pid, pdata in per_player.items():
        comfort = pdata.get("comfort_picks", [])
        if comfort and comfort[0].get("share", 0) >= 0.5:
            champ = comfort[0].get("character")
            name = pdata.get("name", "unknown")
            if champ and champ not in [b["champion"] for b in must_ban]:
                must_ban.append({
                    "champion": champ,
                    "reason": f"{name}'s main ({comfort[0]['share']:.0%} of their games)",
                    "priority": 2,
                })

    # Situational bans - flex picks and high winrate champs
    situational_bans = []
    for champ in flex_picks[:3]:
        if champ not in [b["champion"] for b in must_ban]:
            situational_bans.append({
                "champion": champ,
                "reason": "Flex pick - limits their draft options",
            })

    # Respect picks - things to not let through
    respect_picks = []
    for pick in priority_picks[:5]:
        champ = pick.get("character")
        if champ:
            respect_picks.append(champ)

    # Draft traps - picks to avoid
    draft_traps = []
    by_role = counters.get("by_role", {})
    for role, role_counters in by_role.items():
        for c in role_counters:
            if c.get("expected_winrate", 0.5) <= 0.4 and c.get("samples", 0) >= 3:
                draft_traps.append({
                    "our_pick": c.get("our_champ"),
                    "their_answer": c.get("their_champ"),
                    "role": role,
                    "note": f"They have a strong answer - {c.get('expected_winrate', 0):.0%} expected WR",
                })

    # Phase recommendations based on predictability
    rand_score = randomness.get("score", 50)

    if rand_score < 40:
        phase_strategy = "hard_read"
        phase_note = (
            "They're predictable. You can save counterpicks for later phases "
            "since you know what's coming. Use early picks on flex champions."
        )
    elif rand_score < 60:
        phase_strategy = "balanced"
        phase_note = (
            "Moderate predictability. Secure one comfort pick early, "
            "save one counterpick for R4/R5 or B4/B5."
        )
    else:
        phase_strategy = "reactive"
        phase_note = (
            "They're unpredictable. Don't over-commit to specific counters. "
            "Prioritize your own comfort and flexibility over hard reads."
        )

    return {
        "must_ban": must_ban[:5],
        "situational_bans": situational_bans[:3],
        "respect_picks": respect_picks,
        "draft_traps": draft_traps[:5],
        "phase_strategy": phase_strategy,
        "phase_strategy_note": phase_note,
        "flex_threats": flex_picks[:5],
        "summary": (
            f"Ban {len(must_ban)} priority targets. "
            f"{'Hard-read their draft.' if phase_strategy == 'hard_read' else 'Stay flexible in draft.'}"
        ),
    }


# =============================================================================
# TREND ANALYSIS
# =============================================================================

def analyze_trends(
    games: List[GameRecord],
) -> Dict[str, Any]:
    """
    Analyze performance trends over time.
    """
    if not games:
        return {
            "trajectory": "unknown",
            "trajectory_note": "Not enough data",
            "form_periods": [],
        }

    # Sort by time
    sorted_games = sorted(games, key=lambda g: g.start_time)

    # Split into periods
    recent_cutoff = 14  # days
    mid_cutoff = 45  # days

    recent = [g for g in sorted_games if _days_ago(g.start_time) <= recent_cutoff]
    mid = [g for g in sorted_games if recent_cutoff < _days_ago(g.start_time) <= mid_cutoff]
    old = [g for g in sorted_games if _days_ago(g.start_time) > mid_cutoff]

    def period_stats(period_games: List[GameRecord]) -> Dict[str, Any]:
        if not period_games:
            return {"games": 0, "winrate": None}
        wins = sum(1 for g in period_games if g.opponent.won is True)
        return {
            "games": len(period_games),
            "winrate": wins / len(period_games),
        }

    recent_stats = period_stats(recent)
    mid_stats = period_stats(mid)
    old_stats = period_stats(old)

    # Determine trajectory
    if recent_stats["winrate"] is not None and mid_stats["winrate"] is not None:
        diff = recent_stats["winrate"] - mid_stats["winrate"]
        if diff >= 0.15:
            trajectory = "surging"
            trajectory_note = "They're on a hot streak - expect their best"
        elif diff >= 0.05:
            trajectory = "improving"
            trajectory_note = "Trending upward - don't take them lightly"
        elif diff <= -0.15:
            trajectory = "slumping"
            trajectory_note = "They're struggling lately - exploit their poor form"
        elif diff <= -0.05:
            trajectory = "declining"
            trajectory_note = "Slight downward trend - could be vulnerable"
        else:
            trajectory = "stable"
            trajectory_note = "Consistent performance - expect their standard level"
    elif recent_stats["winrate"] is not None:
        if recent_stats["winrate"] >= 0.6:
            trajectory = "strong"
            trajectory_note = "Playing well recently"
        elif recent_stats["winrate"] <= 0.4:
            trajectory = "weak"
            trajectory_note = "Struggling in recent games"
        else:
            trajectory = "stable"
            trajectory_note = "Average recent performance"
    else:
        trajectory = "unknown"
        trajectory_note = "Not enough recent data"

    form_periods = []
    if recent_stats["games"] > 0:
        form_periods.append({
            "period": "Last 2 weeks",
            "games": recent_stats["games"],
            "winrate": recent_stats["winrate"],
        })
    if mid_stats["games"] > 0:
        form_periods.append({
            "period": "2-6 weeks ago",
            "games": mid_stats["games"],
            "winrate": mid_stats["winrate"],
        })
    if old_stats["games"] > 0:
        form_periods.append({
            "period": "Older",
            "games": old_stats["games"],
            "winrate": old_stats["winrate"],
        })

    return {
        "trajectory": trajectory,
        "trajectory_note": trajectory_note,
        "form_periods": form_periods,
        "recent_games": recent_stats["games"],
        "recent_winrate": recent_stats["winrate"],
    }


# =============================================================================
# PREPARATION CHECKLIST
# =============================================================================

def generate_preparation_checklist(
    games: List[GameRecord],
    per_player: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
    draft_guide: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate actionable preparation items for the team.
    """
    checklist = []

    # Ban preparation
    must_bans = draft_guide.get("must_ban", [])
    if must_bans:
        ban_champs = [b["champion"] for b in must_bans[:3]]
        checklist.append({
            "category": "Draft",
            "item": f"Finalize ban priorities: {', '.join(ban_champs)}",
            "priority": "high",
        })

    # Counter-pick preparation
    for role in ["top", "mid", "bot", "jg", "sup"]:
        for pid, pdata in per_player.items():
            if pdata.get("role") == role:
                comfort = pdata.get("comfort_picks", [])
                if comfort:
                    top_champ = comfort[0].get("character")
                    if top_champ:
                        checklist.append({
                            "category": "Picks",
                            "item": f"Prepare {role} answer to {top_champ}",
                            "priority": "medium",
                        })
                break

    # Scenario practice
    for scenario in scenarios[:2]:
        style = scenario.get("name", "Unknown")
        winrate = scenario.get("winrate", 0)
        if winrate >= 0.5:
            how_to_beat = scenario.get("how_to_beat", [])
            if how_to_beat:
                checklist.append({
                    "category": "Scrims",
                    "item": f"Practice against {style} comps: {how_to_beat[0]}",
                    "priority": "high" if winrate >= 0.6 else "medium",
                })

    # VOD review - find most relevant series
    recent_games = sorted(games, key=lambda g: g.start_time, reverse=True)[:10]
    series_ids = list(set(g.series_id for g in recent_games))[:3]
    if series_ids:
        checklist.append({
            "category": "VOD Review",
            "item": f"Review recent series: {', '.join(series_ids)}",
            "priority": "medium",
        })

    # Player-specific notes
    for pid, pdata in per_player.items():
        threat = pdata.get("threat_level", "medium")
        if threat == "critical":
            name = pdata.get("name", "Unknown")
            role = pdata.get("role", "")
            checklist.append({
                "category": "Focus",
                "item": f"Game plan to neutralize {name} ({role})",
                "priority": "high",
            })

    return {
        "items": checklist,
        "high_priority_count": sum(1 for c in checklist if c.get("priority") == "high"),
        "series_to_review": series_ids,
    }


# =============================================================================
# THE STORY - NARRATIVE SCOUTING REPORT
# =============================================================================

def generate_the_story(
    games: List[GameRecord],
    per_player: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
    trends: Dict[str, Any],
    side_analysis: Dict[str, Any],
    cheese_picks: List[Dict[str, Any]],
    opponent_name: str,
) -> Dict[str, Any]:
    """
    Generate a narrative scouting report like a sports analyst would write.
    Multiple paragraphs telling the story of this opponent.
    """
    if not games:
        return {
            "paragraphs": [],
            "tldr": "Insufficient data to analyze.",
        }

    total_games = len(games)
    wins = sum(1 for g in games if g.opponent.won is True)
    winrate = wins / total_games

    # Opening paragraph - who are they?
    trajectory = trends.get("trajectory", "stable")
    trajectory_note = trends.get("trajectory_note", "")

    if trajectory in ("surging", "improving"):
        momentum_text = f"They're coming in hot - {trajectory_note.lower()}"
    elif trajectory in ("slumping", "declining"):
        momentum_text = f"But don't get too confident - {trajectory_note.lower()}"
    else:
        momentum_text = "They've been consistent lately, so expect their standard level."

    opening = (
        f"{opponent_name} enters this match with a {winrate:.0%} winrate "
        f"across {total_games} games. {momentum_text}"
    )

    # Identity paragraph - how do they play?
    identity_parts = []

    if scenarios:
        main_scenario = scenarios[0]
        style_name = main_scenario.get("name", "Standard")
        share = main_scenario.get("share", 0)
        tempo = main_scenario.get("tempo", "mid-game")

        if share >= 0.5:
            identity_parts.append(
                f"Their identity is clear: they're a {style_name.lower()} team "
                f"({share:.0%} of their games follow this pattern)."
            )
        else:
            identity_parts.append(
                f"They don't have one dominant style, but lean toward {style_name.lower()} gameplay."
            )

        if tempo == "early-game":
            identity_parts.append(
                "They want to fight early and snowball. If you survive their early aggression, they struggle."
            )
        elif tempo == "late-game":
            identity_parts.append(
                "They're patient and scale-focused. Don't let them reach their power spikes for free."
            )
        elif tempo == "high-tempo":
            identity_parts.append(
                "Expect chaos. They thrive in skirmishes and fiestas - play controlled if you want to beat them."
            )

    identity = " ".join(identity_parts) if identity_parts else "They play a balanced style without clear tendencies."

    # Star players paragraph
    stars = []
    weak_links = []
    for pid, pdata in per_player.items():
        threat = pdata.get("threat_level", "medium")
        name = pdata.get("name", "Unknown")
        role = pdata.get("role", "")
        if threat in ("critical", "high"):
            stars.append({"name": name, "role": role, "data": pdata})
        elif threat == "low":
            weak_links.append({"name": name, "role": role, "data": pdata})

    players_paragraph_parts = []
    if stars:
        star = stars[0]
        star_data = star["data"]
        comfort = star_data.get("comfort_picks", [])
        top_champ = comfort[0].get("character", "") if comfort else ""

        players_paragraph_parts.append(
            f"Watch out for {star['name']} in the {star['role']} position - "
            f"they're the player who can take over games."
        )
        if top_champ:
            players_paragraph_parts.append(
                f"Their {top_champ} is especially dangerous and should be respect-banned or countered."
            )

    if weak_links:
        weak = weak_links[0]
        players_paragraph_parts.append(
            f"On the flip side, {weak['name']} ({weak['role']}) has been their weak link. "
            f"Consider focusing resources on punishing this lane."
        )

    players_paragraph = " ".join(players_paragraph_parts) if players_paragraph_parts else ""

    # Side preference paragraph
    blue_wr = side_analysis.get("blue_side", {}).get("winrate", 0.5)
    red_wr = side_analysis.get("red_side", {}).get("winrate", 0.5)
    blue_games = side_analysis.get("blue_side", {}).get("games", 0)
    red_games = side_analysis.get("red_side", {}).get("games", 0)

    if blue_games >= 3 and red_games >= 3:
        diff = abs(blue_wr - red_wr)
        if diff >= 0.15:
            if blue_wr > red_wr:
                side_text = (
                    f"Interestingly, they're significantly stronger on blue side "
                    f"({blue_wr:.0%} WR) compared to red side ({red_wr:.0%} WR). "
                    f"If you have side selection, put them on red."
                )
            else:
                side_text = (
                    f"They actually prefer red side ({red_wr:.0%} WR) over blue ({blue_wr:.0%} WR). "
                    f"Their counterpicking is strong - don't give them last pick on key roles."
                )
        else:
            side_text = f"They perform similarly on both sides (Blue: {blue_wr:.0%}, Red: {red_wr:.0%})."
    else:
        side_text = ""

    # Cheese warning paragraph
    cheese_paragraph = ""
    if cheese_picks:
        cheese = cheese_picks[0]
        champ = cheese.get("champion", "")
        player = cheese.get("player_name", "")
        wr = cheese.get("winrate", 0)
        games_count = cheese.get("games", 0)

        cheese_paragraph = (
            f"One more thing: watch for the {champ} pocket pick. "
            f"{player} has pulled it out {games_count} times with a {wr:.0%} winrate. "
            f"It's rare but deadly - have an answer ready if you see it."
        )

    # Closing - the game plan
    closing_parts = []
    if scenarios:
        how_to_beat = scenarios[0].get("how_to_beat", [])
        if how_to_beat:
            closing_parts.append(f"To beat them: {how_to_beat[0].lower()}.")

    if stars:
        star = stars[0]
        closing_parts.append(f"Neutralize {star['name']} and you neutralize their win condition.")

    if trajectory in ("slumping", "declining"):
        closing_parts.append("Their mental might be fragile - get ahead early and they could crumble.")

    closing = " ".join(closing_parts) if closing_parts else "Execute your game plan and you'll be fine."

    # Build paragraph list
    paragraphs = [
        {"type": "opening", "title": "The Matchup", "text": opening},
        {"type": "identity", "title": "How They Play", "text": identity},
    ]

    if players_paragraph:
        paragraphs.append({"type": "players", "title": "Key Players", "text": players_paragraph})

    if side_text:
        paragraphs.append({"type": "sides", "title": "Side Preference", "text": side_text})

    if cheese_paragraph:
        paragraphs.append({"type": "cheese", "title": "Cheese Alert", "text": cheese_paragraph})

    paragraphs.append({"type": "closing", "title": "The Game Plan", "text": closing})

    # TL;DR
    tldr_parts = []
    tldr_parts.append(f"{winrate:.0%} WR team")
    if stars:
        tldr_parts.append(f"star player: {stars[0]['name']}")
    if scenarios:
        tldr_parts.append(f"plays {scenarios[0].get('name', 'standard').lower()}")
    if trajectory in ("surging", "slumping"):
        tldr_parts.append(trajectory)

    tldr = f"{opponent_name}: " + ", ".join(tldr_parts) + "."

    return {
        "paragraphs": paragraphs,
        "tldr": tldr,
        "full_narrative": "\n\n".join([p["text"] for p in paragraphs]),
    }


# =============================================================================
# BLUE SIDE VS RED SIDE ANALYSIS
# =============================================================================

def analyze_side_preference(
    games: List[GameRecord],
    per_player: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Analyze performance differences on blue vs red side.
    """
    # We need to determine which side the opponent was on for each game
    # Since we don't have explicit side data, we'll infer from team order if available
    # For now, we'll use series_id patterns or assume alternating if no data

    blue_games: List[GameRecord] = []
    red_games: List[GameRecord] = []

    # Try to infer side from game data
    # In many APIs, team order indicates side (first = blue)
    for g in games:
        # Check if opponent team_id comes before or after in any ordering
        # This is a heuristic - real data might have explicit side info
        game_num = g.game_number
        # Odd games often blue side for one team, even for other
        # This is imperfect but better than nothing
        if game_num % 2 == 1:
            blue_games.append(g)
        else:
            red_games.append(g)

    def side_stats(side_games: List[GameRecord], side_name: str) -> Dict[str, Any]:
        if not side_games:
            return {
                "side": side_name,
                "games": 0,
                "wins": 0,
                "winrate": None,
                "avg_kills": 0,
                "avg_deaths": 0,
                "priority_picks": [],
                "first_pick_champions": [],
            }

        wins = sum(1 for g in side_games if g.opponent.won is True)
        total_kills = sum(g.opponent.kills for g in side_games)
        total_deaths = sum(g.opponent.deaths for g in side_games)

        # Champion frequency on this side
        champ_counts: Counter = Counter()
        for g in side_games:
            for p in g.opponent.players:
                if p.character:
                    champ_counts[p.character] += 1

        top_champs = [{"champion": c, "games": n} for c, n in champ_counts.most_common(5)]

        return {
            "side": side_name,
            "games": len(side_games),
            "wins": wins,
            "winrate": wins / len(side_games),
            "avg_kills": total_kills / len(side_games),
            "avg_deaths": total_deaths / len(side_games),
            "priority_picks": top_champs,
        }

    blue_stats = side_stats(blue_games, "blue")
    red_stats = side_stats(red_games, "red")

    # Determine preference
    if blue_stats["winrate"] is not None and red_stats["winrate"] is not None:
        diff = blue_stats["winrate"] - red_stats["winrate"]
        if diff >= 0.15:
            preference = "blue"
            preference_note = f"Significantly stronger on blue side (+{diff:.0%} WR)"
            recommendation = "If you have side selection, put them on red side"
        elif diff <= -0.15:
            preference = "red"
            preference_note = f"Significantly stronger on red side (+{-diff:.0%} WR)"
            recommendation = "If you have side selection, put them on blue side - they prefer counterpicking"
        elif diff >= 0.05:
            preference = "slight_blue"
            preference_note = "Slightly favor blue side"
            recommendation = "Minor blue side preference - factor into draft planning"
        elif diff <= -0.05:
            preference = "slight_red"
            preference_note = "Slightly favor red side"
            recommendation = "Minor red side preference - they like to counterpick"
        else:
            preference = "neutral"
            preference_note = "Perform equally on both sides"
            recommendation = "Side selection won't give you an edge"
    else:
        preference = "unknown"
        preference_note = "Not enough data to determine"
        recommendation = "Need more games to analyze"

    # Find champions that differ significantly by side
    blue_champs = {c["champion"]: c["games"] for c in blue_stats.get("priority_picks", [])}
    red_champs = {c["champion"]: c["games"] for c in red_stats.get("priority_picks", [])}

    blue_only = [c for c in blue_champs if c not in red_champs or red_champs[c] < blue_champs[c] * 0.5]
    red_only = [c for c in red_champs if c not in blue_champs or blue_champs[c] < red_champs[c] * 0.5]

    return {
        "blue_side": blue_stats,
        "red_side": red_stats,
        "preference": preference,
        "preference_note": preference_note,
        "recommendation": recommendation,
        "blue_side_picks": blue_only[:3],
        "red_side_picks": red_only[:3],
    }


# =============================================================================
# SERIES MOMENTUM / MENTAL EDGE
# =============================================================================

def analyze_series_momentum(
    games: List[GameRecord],
) -> Dict[str, Any]:
    """
    Analyze how the team performs across a series (game 1 vs game 2-5).
    Do they adapt? Do they tilt after losses?
    """
    # Group games by series
    series_map: Dict[str, List[GameRecord]] = defaultdict(list)
    for g in games:
        series_map[g.series_id].append(g)

    # Sort each series by game number
    for sid in series_map:
        series_map[sid].sort(key=lambda g: g.game_number)

    # Game 1 performance
    game1_results = []
    later_games_results = []

    # After-loss performance (within series)
    after_loss_wins = 0
    after_loss_games = 0

    # After-win performance
    after_win_wins = 0
    after_win_games = 0

    # Adaptation: do they improve within series?
    series_comebacks = 0  # Lost game 1, won series
    series_chokes = 0     # Won game 1, lost series
    total_multi_game_series = 0

    for sid, series_games in series_map.items():
        if len(series_games) < 1:
            continue

        # Game 1 stats
        g1 = series_games[0]
        game1_results.append(g1.opponent.won is True)

        # Later games
        for g in series_games[1:]:
            later_games_results.append(g.opponent.won is True)

        # Track momentum within series
        prev_won = None
        for g in series_games:
            if prev_won is not None:
                if prev_won is False:  # Previous game was a loss
                    after_loss_games += 1
                    if g.opponent.won is True:
                        after_loss_wins += 1
                elif prev_won is True:  # Previous game was a win
                    after_win_games += 1
                    if g.opponent.won is True:
                        after_win_wins += 1
            prev_won = g.opponent.won

        # Comebacks / chokes (need 2+ game series with outcome info)
        if len(series_games) >= 2:
            first_game_won = series_games[0].opponent.won
            # Determine series winner (simplified: who won more games)
            wins_in_series = sum(1 for g in series_games if g.opponent.won is True)
            losses_in_series = sum(1 for g in series_games if g.opponent.won is False)

            if wins_in_series > 0 or losses_in_series > 0:
                total_multi_game_series += 1
                series_won = wins_in_series > losses_in_series

                if first_game_won is False and series_won:
                    series_comebacks += 1
                elif first_game_won is True and not series_won:
                    series_chokes += 1

    # Calculate stats
    game1_wr = sum(game1_results) / len(game1_results) if game1_results else None
    later_wr = sum(later_games_results) / len(later_games_results) if later_games_results else None
    after_loss_wr = after_loss_wins / after_loss_games if after_loss_games > 0 else None
    after_win_wr = after_win_wins / after_win_games if after_win_games > 0 else None

    # Determine mental profile
    mental_profile = "stable"
    mental_note = "They maintain consistent performance regardless of game state."

    if after_loss_wr is not None and after_loss_games >= 3:
        if after_loss_wr >= 0.6:
            mental_profile = "resilient"
            mental_note = "They bounce back strong after losses - don't expect them to tilt."
        elif after_loss_wr <= 0.3:
            mental_profile = "tilter"
            mental_note = "They struggle after losing - get ahead early and they might crumble."

    # Adaptation assessment
    adaptation = "unknown"
    adaptation_note = "Not enough multi-game series to assess."

    if game1_wr is not None and later_wr is not None:
        diff = later_wr - game1_wr
        if diff >= 0.15:
            adaptation = "strong_adapters"
            adaptation_note = f"They get better as series progress (+{diff:.0%} WR in later games). Expect adjustments."
        elif diff <= -0.15:
            adaptation = "slow_starters"
            adaptation_note = f"They're actually weaker in later games ({diff:.0%} WR drop). Their game 1 prep is their peak."
        else:
            adaptation = "consistent"
            adaptation_note = "Consistent across series - they don't notably adapt or decline."

    # Comeback/choke assessment
    clutch = "neutral"
    if total_multi_game_series >= 3:
        comeback_rate = series_comebacks / total_multi_game_series
        choke_rate = series_chokes / total_multi_game_series

        if comeback_rate >= 0.3:
            clutch = "clutch"
        elif choke_rate >= 0.3:
            clutch = "chokers"

    return {
        "game_1": {
            "games": len(game1_results),
            "winrate": game1_wr,
            "note": f"Game 1 winrate: {game1_wr:.0%}" if game1_wr else "No data",
        },
        "later_games": {
            "games": len(later_games_results),
            "winrate": later_wr,
            "note": f"Games 2+ winrate: {later_wr:.0%}" if later_wr else "No data",
        },
        "after_loss": {
            "games": after_loss_games,
            "winrate": after_loss_wr,
            "note": f"After a loss: {after_loss_wr:.0%} WR" if after_loss_wr else "No data",
        },
        "after_win": {
            "games": after_win_games,
            "winrate": after_win_wr,
            "note": f"After a win: {after_win_wr:.0%} WR" if after_win_wr else "No data",
        },
        "mental_profile": mental_profile,
        "mental_note": mental_note,
        "adaptation": adaptation,
        "adaptation_note": adaptation_note,
        "clutch_factor": clutch,
        "series_comebacks": series_comebacks,
        "series_chokes": series_chokes,
        "total_series": total_multi_game_series,
    }


# =============================================================================
# CHEESE DETECTOR - POCKET PICKS
# =============================================================================

def detect_cheese_picks(
    games: List[GameRecord],
    min_winrate: float = 0.65,
    max_pick_rate: float = 0.15,
    min_games: int = 2,
) -> List[Dict[str, Any]]:
    """
    Find pocket picks: rarely played champions with unusually high winrates.
    These are surprise picks the opponent might pull out.
    """
    # Track champion stats per player
    player_champ_stats: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"games": 0, "wins": 0})
    )
    player_total_games: Dict[str, int] = defaultdict(int)
    player_names: Dict[str, str] = {}
    player_roles: Dict[str, str] = {}

    for g in games:
        for p in g.opponent.players:
            if not p.player_id or not p.character:
                continue

            player_total_games[p.player_id] += 1
            player_champ_stats[p.player_id][p.character]["games"] += 1
            if g.opponent.won is True:
                player_champ_stats[p.player_id][p.character]["wins"] += 1

            if p.name:
                player_names[p.player_id] = p.name
            if p.role:
                player_roles[p.player_id] = p.role

    cheese_picks = []

    for pid, champ_data in player_champ_stats.items():
        total_games = player_total_games[pid]
        if total_games < 5:  # Need enough games to identify patterns
            continue

        for champ, stats in champ_data.items():
            games_count = stats["games"]
            wins = stats["wins"]
            pick_rate = games_count / total_games
            winrate = wins / games_count if games_count > 0 else 0

            # Cheese criteria: low pick rate, high winrate, minimum sample
            if (
                pick_rate <= max_pick_rate
                and winrate >= min_winrate
                and games_count >= min_games
            ):
                cheese_picks.append({
                    "player_id": pid,
                    "player_name": player_names.get(pid, "Unknown"),
                    "role": player_roles.get(pid, ""),
                    "champion": champ,
                    "games": games_count,
                    "wins": wins,
                    "winrate": winrate,
                    "pick_rate": pick_rate,
                    "cheese_score": winrate * (1 - pick_rate),  # Higher = more cheesy
                    "warning": (
                        f"{player_names.get(pid, 'Unknown')}'s {champ}: "
                        f"Rare pick ({pick_rate:.0%} of games) but {winrate:.0%} winrate. "
                        f"Have an answer ready!"
                    ),
                })

    # Sort by cheese score (most dangerous pocket picks first)
    cheese_picks.sort(key=lambda x: x["cheese_score"], reverse=True)

    return cheese_picks


# =============================================================================
# ONE THING TO REMEMBER - PER PLAYER
# =============================================================================

def generate_one_thing_to_remember(
    games: List[GameRecord],
    per_player: Dict[str, Any],
    cheese_picks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Generate the single most important thing to remember about each player.
    Perfect for quick pre-game briefings.
    """
    one_things = []

    # Index cheese picks by player
    cheese_by_player = {}
    for cheese in cheese_picks:
        pid = cheese.get("player_id")
        if pid and pid not in cheese_by_player:
            cheese_by_player[pid] = cheese

    for pid, pdata in per_player.items():
        name = pdata.get("name") or "Unknown"
        role = pdata.get("role") or ""
        threat = pdata.get("threat_level", "medium")
        pool_depth = pdata.get("champion_pool_depth", "moderate")
        playstyle = pdata.get("playstyle", "balanced")
        recent_form = pdata.get("recent_form", "stable")
        comfort_picks = pdata.get("comfort_picks", [])

        top_champ = comfort_picks[0].get("character") if comfort_picks else None
        top_share = comfort_picks[0].get("share", 0) if comfort_picks else 0

        # Determine the one thing
        one_thing = ""
        priority = "medium"
        action = ""

        # Check for cheese pick first
        if pid in cheese_by_player:
            cheese = cheese_by_player[pid]
            one_thing = f"Watch for {cheese['champion']} pocket pick ({cheese['winrate']:.0%} WR)"
            action = f"Have a counter ready for {cheese['champion']}"
            priority = "high"

        # One-trick detection
        elif pool_depth == "one-trick" and top_champ:
            one_thing = f"One-trick on {top_champ} ({top_share:.0%} pick rate)"
            action = f"Ban {top_champ} or have a hard counter"
            priority = "high"

        # Major threat
        elif threat == "critical":
            if top_champ:
                one_thing = f"Primary carry threat on {top_champ}"
                action = f"Neutralize with bans or jungle focus"
            else:
                one_thing = "Primary carry threat for the team"
                action = "Don't let them get ahead"
            priority = "high"

        # Tilter
        elif playstyle == "coinflip":
            one_thing = "Coinflip player - will either carry or int"
            action = "Punish aggressive overextensions"
            priority = "medium"

        # Weak link
        elif threat == "low":
            one_thing = "Weak link - exploitable in lane"
            action = "Consider camping this lane"
            priority = "medium"

        # Form-based
        elif recent_form == "hot":
            one_thing = "Currently on fire - playing their best"
            action = "Respect their confidence, don't underestimate"
            priority = "medium"
        elif recent_form == "cold":
            one_thing = "Currently slumping - might tilt easily"
            action = "Apply early pressure to break their mental"
            priority = "medium"

        # Safe player
        elif playstyle == "safe/controlled":
            one_thing = "Plays very safe - hard to punish"
            action = "Don't waste resources ganking, focus elsewhere"
            priority = "low"

        # Default
        else:
            if top_champ:
                one_thing = f"Comfort pick: {top_champ}"
                action = f"Consider banning or countering {top_champ}"
            else:
                one_thing = "Solid player without obvious weaknesses"
                action = "Play your game"
            priority = "low"

        one_things.append({
            "player_id": pid,
            "player_name": name,
            "role": role,
            "one_thing": one_thing,
            "action": action,
            "priority": priority,
            "threat_level": threat,
        })

    # Sort by priority and threat level
    priority_order = {"high": 0, "medium": 1, "low": 2}
    one_things.sort(key=lambda x: (priority_order.get(x["priority"], 2), x["role"]))

    return one_things


# =============================================================================
# IF THEY PICK X - DECISION TREE FOR DRAFT
# =============================================================================

def generate_pick_decision_tree(
    games: List[GameRecord],
    per_player: Dict[str, Any],
    counters: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate a decision tree structure for draft:
    "If they pick X, consider Y" with branching logic.

    Returns data structured for frontend visualization as a flowchart.
    """
    # Build pick-response data from games
    pick_responses: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(
        lambda: defaultdict(lambda: {"games": 0, "wins": 0, "our_picks": defaultdict(lambda: {"games": 0, "wins": 0})})
    )

    # For each game, track what they picked and what worked against it
    for g in games:
        opp_picks = {}
        our_picks = {}

        for p in g.opponent.players:
            if p.role and p.character:
                opp_picks[p.role] = p.character

        for p in g.team.players:
            if p.role and p.character:
                our_picks[p.role] = p.character

        opp_won = g.opponent.won is True

        # Record matchups
        for role, their_champ in opp_picks.items():
            pick_responses[role][their_champ]["games"] += 1
            if opp_won:
                pick_responses[role][their_champ]["wins"] += 1

            # What did we pick into it?
            our_champ = our_picks.get(role)
            if our_champ:
                pick_responses[role][their_champ]["our_picks"][our_champ]["games"] += 1
                if not opp_won:  # We won
                    pick_responses[role][their_champ]["our_picks"][our_champ]["wins"] += 1

    # Build decision tree nodes
    nodes = []
    edges = []
    node_id = 0

    # Create root node
    root_id = f"node_{node_id}"
    nodes.append({
        "id": root_id,
        "type": "root",
        "label": "Draft Start",
        "data": {},
    })
    node_id += 1

    # For each role, create champion nodes
    role_order = ["top", "jg", "mid", "bot", "sup"]
    role_nodes = {}

    for role in role_order:
        role_data = pick_responses.get(role, {})
        if not role_data:
            continue

        # Create role grouping node
        role_node_id = f"node_{node_id}"
        nodes.append({
            "id": role_node_id,
            "type": "role",
            "label": role.upper(),
            "data": {"role": role},
        })
        edges.append({
            "source": root_id,
            "target": role_node_id,
            "type": "role_branch",
        })
        role_nodes[role] = role_node_id
        node_id += 1

        # Top picks for this role
        sorted_picks = sorted(
            role_data.items(),
            key=lambda x: x[1]["games"],
            reverse=True
        )[:4]  # Top 4 picks per role

        for their_champ, data in sorted_picks:
            if data["games"] < 2:
                continue

            their_wr = data["wins"] / data["games"]

            # Create "if they pick X" node
            pick_node_id = f"node_{node_id}"
            nodes.append({
                "id": pick_node_id,
                "type": "opponent_pick",
                "label": their_champ,
                "data": {
                    "champion": their_champ,
                    "role": role,
                    "games": data["games"],
                    "their_winrate": their_wr,
                    "threat_level": "high" if their_wr >= 0.6 else "medium" if their_wr >= 0.45 else "low",
                },
            })
            edges.append({
                "source": role_node_id,
                "target": pick_node_id,
                "type": "if_pick",
                "label": f"If {their_champ}",
            })
            node_id += 1

            # Find best responses
            our_responses = []
            for our_champ, response_data in data["our_picks"].items():
                if response_data["games"] >= 1:
                    our_wr = response_data["wins"] / response_data["games"]
                    our_responses.append({
                        "champion": our_champ,
                        "games": response_data["games"],
                        "winrate": our_wr,
                    })

            our_responses.sort(key=lambda x: (x["winrate"], x["games"]), reverse=True)

            # Create response nodes (top 2)
            for i, response in enumerate(our_responses[:2]):
                response_node_id = f"node_{node_id}"

                if response["winrate"] >= 0.6:
                    recommendation = "strong_counter"
                    rec_label = "Strong Answer"
                elif response["winrate"] >= 0.45:
                    recommendation = "viable"
                    rec_label = "Viable"
                else:
                    recommendation = "avoid"
                    rec_label = "Avoid"

                nodes.append({
                    "id": response_node_id,
                    "type": "response",
                    "label": response["champion"],
                    "data": {
                        "champion": response["champion"],
                        "games": response["games"],
                        "winrate": response["winrate"],
                        "recommendation": recommendation,
                        "vs": their_champ,
                    },
                })
                edges.append({
                    "source": pick_node_id,
                    "target": response_node_id,
                    "type": "response",
                    "label": f"{response['winrate']:.0%} WR" if response["games"] >= 2 else "Limited data",
                })
                node_id += 1

            # Add avoid node if we have data on what didn't work
            bad_responses = [r for r in our_responses if r["winrate"] < 0.4 and r["games"] >= 2]
            if bad_responses:
                worst = bad_responses[-1]
                avoid_node_id = f"node_{node_id}"
                nodes.append({
                    "id": avoid_node_id,
                    "type": "avoid",
                    "label": f"Avoid: {worst['champion']}",
                    "data": {
                        "champion": worst["champion"],
                        "games": worst["games"],
                        "winrate": worst["winrate"],
                        "reason": f"Only {worst['winrate']:.0%} WR vs their {their_champ}",
                    },
                })
                edges.append({
                    "source": pick_node_id,
                    "target": avoid_node_id,
                    "type": "avoid",
                    "label": "Don't pick",
                })
                node_id += 1

    # Create summary for quick reference
    quick_reference = []
    for role in role_order:
        role_data = pick_responses.get(role, {})
        if not role_data:
            continue

        role_summary = {"role": role, "matchups": []}

        sorted_picks = sorted(role_data.items(), key=lambda x: x[1]["games"], reverse=True)[:3]

        for their_champ, data in sorted_picks:
            if data["games"] < 2:
                continue

            best_response = None
            best_wr = 0
            avoid_pick = None
            avoid_wr = 1

            for our_champ, response_data in data["our_picks"].items():
                if response_data["games"] >= 1:
                    wr = response_data["wins"] / response_data["games"]
                    if wr > best_wr:
                        best_wr = wr
                        best_response = our_champ
                    if wr < avoid_wr:
                        avoid_wr = wr
                        avoid_pick = our_champ

            role_summary["matchups"].append({
                "if_they_pick": their_champ,
                "consider": best_response,
                "consider_wr": best_wr,
                "avoid": avoid_pick if avoid_wr < 0.4 else None,
                "avoid_wr": avoid_wr if avoid_wr < 0.4 else None,
            })

        if role_summary["matchups"]:
            quick_reference.append(role_summary)

    return {
        "flowchart": {
            "nodes": nodes,
            "edges": edges,
        },
        "quick_reference": quick_reference,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
    }


# =============================================================================
# KILL PARTICIPATION WEB - WHO ENABLES WHO
# =============================================================================

def generate_kill_participation_web(
    games: List[GameRecord],
    per_player: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate a network graph showing which players enable each other.
    Analyzes kill participation patterns to find the real playmakers.

    Returns data structured for frontend network visualization.
    """
    # Track co-participation in kills
    # When a team gets kills, which players are typically involved together?

    player_names: Dict[str, str] = {}
    player_roles: Dict[str, str] = {}
    player_total_kills: Dict[str, int] = defaultdict(int)
    player_total_deaths: Dict[str, int] = defaultdict(int)
    player_games: Dict[str, int] = defaultdict(int)

    # Track which players appear in the same games (proxy for kill participation)
    # Since we don't have per-kill data, we use game-level stats
    co_occurrence: Dict[tuple, Dict[str, int]] = defaultdict(lambda: {"games": 0, "wins": 0})

    # Role-based synergy tracking
    role_synergy: Dict[tuple, Dict[str, Any]] = defaultdict(
        lambda: {"games": 0, "wins": 0, "total_kills": 0}
    )

    for g in games:
        game_players = []
        team_won = g.opponent.won is True
        team_kills = g.opponent.kills

        for p in g.opponent.players:
            if not p.player_id:
                continue

            game_players.append(p.player_id)
            player_total_kills[p.player_id] += p.kills
            player_total_deaths[p.player_id] += p.deaths
            player_games[p.player_id] += 1

            if p.name:
                player_names[p.player_id] = p.name
            if p.role:
                player_roles[p.player_id] = p.role

        # Track co-occurrence (players in the same game)
        for i in range(len(game_players)):
            for j in range(i + 1, len(game_players)):
                pair = tuple(sorted([game_players[i], game_players[j]]))
                co_occurrence[pair]["games"] += 1
                if team_won:
                    co_occurrence[pair]["wins"] += 1

        # Track role synergies
        role_players = {}
        for p in g.opponent.players:
            if p.role and p.player_id:
                role_players[p.role] = p.player_id

        # Key synergy pairs
        synergy_pairs = [
            ("jg", "mid"),   # Jungle-Mid synergy
            ("bot", "sup"),  # Bot lane synergy
            ("jg", "top"),   # Jungle-Top synergy
            ("jg", "bot"),   # Jungle-Bot synergy
            ("mid", "sup"),  # Roaming support
        ]

        for r1, r2 in synergy_pairs:
            if r1 in role_players and r2 in role_players:
                role_synergy[(r1, r2)]["games"] += 1
                if team_won:
                    role_synergy[(r1, r2)]["wins"] += 1
                role_synergy[(r1, r2)]["total_kills"] += team_kills

    # Build network graph
    nodes = []
    edges = []

    # Create player nodes
    for pid in player_games:
        games_count = player_games[pid]
        kills = player_total_kills[pid]
        deaths = player_total_deaths[pid]

        kda = kills / deaths if deaths > 0 else kills
        kills_per_game = kills / games_count if games_count > 0 else 0

        # Determine node size based on involvement
        if kills_per_game >= 4:
            involvement = "primary_carry"
            node_size = "large"
        elif kills_per_game >= 2.5:
            involvement = "secondary_carry"
            node_size = "medium"
        else:
            involvement = "enabler"
            node_size = "small"

        nodes.append({
            "id": pid,
            "label": player_names.get(pid, pid[:8]),
            "role": player_roles.get(pid, "unknown"),
            "data": {
                "games": games_count,
                "total_kills": kills,
                "total_deaths": deaths,
                "kda": kda,
                "kills_per_game": kills_per_game,
                "involvement": involvement,
            },
            "size": node_size,
        })

    # Create edges based on co-occurrence and synergy
    for (p1, p2), data in co_occurrence.items():
        if data["games"] < 2:
            continue

        winrate = data["wins"] / data["games"]

        # Determine edge strength
        if winrate >= 0.6:
            strength = "strong"
            edge_type = "synergy"
        elif winrate >= 0.45:
            strength = "moderate"
            edge_type = "neutral"
        else:
            strength = "weak"
            edge_type = "anti_synergy"

        r1 = player_roles.get(p1, "")
        r2 = player_roles.get(p2, "")

        edges.append({
            "source": p1,
            "target": p2,
            "data": {
                "games": data["games"],
                "wins": data["wins"],
                "winrate": winrate,
                "roles": f"{r1}-{r2}",
            },
            "strength": strength,
            "type": edge_type,
        })

    # Identify the playmaker (highest kill participation)
    playmaker = None
    playmaker_score = 0
    for pid in player_games:
        score = player_total_kills[pid] / player_games[pid] if player_games[pid] > 0 else 0
        if score > playmaker_score:
            playmaker_score = score
            playmaker = pid

    # Identify the enabler (support/jungle with high team winrate)
    enabler = None
    enabler_note = ""
    for pid in player_games:
        role = player_roles.get(pid, "")
        if role in ("sup", "jg"):
            games_count = player_games[pid]
            # Calculate winrate when this player is in the game
            wins = sum(1 for pair, data in co_occurrence.items()
                       if pid in pair for _ in range(data["wins"]))
            # Simplified: use deaths as inverse proxy for enabling
            deaths = player_total_deaths[pid]
            deaths_per_game = deaths / games_count if games_count > 0 else 0
            if deaths_per_game < 3 and games_count >= 3:
                enabler = pid
                enabler_note = f"Low deaths ({deaths_per_game:.1f}/game) while enabling team"

    # Generate insights
    insights = []

    if playmaker:
        name = player_names.get(playmaker, "Unknown")
        role = player_roles.get(playmaker, "")
        kpg = player_total_kills[playmaker] / player_games[playmaker]
        insights.append({
            "type": "playmaker",
            "player": name,
            "role": role,
            "insight": f"{name} is the primary playmaker ({kpg:.1f} kills/game)",
            "action": "Neutralize this player to shut down their offense",
        })

    if enabler:
        name = player_names.get(enabler, "Unknown")
        role = player_roles.get(enabler, "")
        insights.append({
            "type": "enabler",
            "player": name,
            "role": role,
            "insight": f"{name} is the key enabler - {enabler_note}",
            "action": "Disrupt their vision and roaming to break team synergy",
        })

    # Role synergy insights
    for (r1, r2), data in role_synergy.items():
        if data["games"] >= 3:
            winrate = data["wins"] / data["games"]
            avg_kills = data["total_kills"] / data["games"]
            if winrate >= 0.65:
                insights.append({
                    "type": "synergy",
                    "roles": f"{r1.upper()}-{r2.upper()}",
                    "insight": f"Strong {r1.upper()}-{r2.upper()} synergy ({winrate:.0%} WR when playing together)",
                    "action": f"Ward between {r1} and {r2} to spot their coordinated plays",
                })
            elif winrate <= 0.35:
                insights.append({
                    "type": "weakness",
                    "roles": f"{r1.upper()}-{r2.upper()}",
                    "insight": f"Weak {r1.upper()}-{r2.upper()} coordination ({winrate:.0%} WR)",
                    "action": f"Exploit the disconnect between {r1} and {r2}",
                })

    # Key duo identification
    best_duo = None
    best_duo_wr = 0
    for (p1, p2), data in co_occurrence.items():
        if data["games"] >= 3:
            wr = data["wins"] / data["games"]
            if wr > best_duo_wr:
                best_duo_wr = wr
                best_duo = (p1, p2, data)

    if best_duo and best_duo_wr >= 0.6:
        p1, p2, data = best_duo
        n1 = player_names.get(p1, "Unknown")
        n2 = player_names.get(p2, "Unknown")
        r1 = player_roles.get(p1, "")
        r2 = player_roles.get(p2, "")
        insights.append({
            "type": "duo",
            "players": [n1, n2],
            "insight": f"{n1} ({r1}) + {n2} ({r2}) = {best_duo_wr:.0%} winrate together",
            "action": "This duo is dangerous - consider banning one of their comfort picks",
        })

    return {
        "network": {
            "nodes": nodes,
            "edges": edges,
        },
        "playmaker": {
            "player_id": playmaker,
            "player_name": player_names.get(playmaker, "Unknown") if playmaker else None,
            "role": player_roles.get(playmaker, "") if playmaker else None,
        },
        "enabler": {
            "player_id": enabler,
            "player_name": player_names.get(enabler, "Unknown") if enabler else None,
            "role": player_roles.get(enabler, "") if enabler else None,
        },
        "insights": insights,
        "visualization_notes": {
            "node_size": "Based on kills per game (larger = more kills)",
            "edge_color": "Green = high winrate together, Red = low winrate together",
            "recommended_library": "vis.js, d3-force, or react-force-graph",
        },
    }


# =============================================================================
# GAME SCRIPT PREDICTION - MINUTE-BY-MINUTE
# =============================================================================

def generate_game_script(
    games: List[GameRecord],
    scenarios: List[Dict[str, Any]],
    series_momentum: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Predict what will happen during the game based on historical patterns.
    Since we don't have minute-by-minute data, we infer from outcomes and tendencies.

    Returns a timeline of expected events.
    """
    if not games:
        return {
            "timeline": [],
            "confidence": "low",
            "summary": "Insufficient data to predict game flow.",
        }

    total_games = len(games)
    wins = sum(1 for g in games if g.opponent.won is True)
    winrate = wins / total_games

    # Analyze kill patterns to determine tempo
    avg_kills = sum(g.opponent.kills for g in games) / total_games
    avg_deaths = sum(g.opponent.deaths for g in games) / total_games
    total_action = avg_kills + avg_deaths

    # Determine game tempo
    if total_action >= 28:
        tempo = "bloody"
        tempo_note = "Expect constant fighting"
    elif total_action >= 20:
        tempo = "aggressive"
        tempo_note = "They like to fight"
    elif total_action <= 14:
        tempo = "slow"
        tempo_note = "They play for scaling"
    else:
        tempo = "standard"
        tempo_note = "Normal game flow"

    # Determine primary style from scenarios
    primary_style = "standard"
    if scenarios:
        main = scenarios[0]
        primary_style = main.get("tempo", "mid-game")

    # Build timeline predictions
    timeline = []

    # Pre-game (Champ Select)
    timeline.append({
        "phase": "champ_select",
        "time": "Draft",
        "prediction": _get_draft_prediction(games, scenarios),
        "confidence": "high" if total_games >= 10 else "medium",
        "action": "Watch for their priority picks in first rotation",
    })

    # Early Game (0-5 min)
    early_prediction = _predict_early_game(games, tempo, primary_style)
    timeline.append({
        "phase": "early_game",
        "time": "0-5 min",
        "prediction": early_prediction["text"],
        "events": early_prediction["events"],
        "confidence": early_prediction["confidence"],
        "action": early_prediction["action"],
    })

    # Early-Mid (5-10 min)
    early_mid_prediction = _predict_early_mid_game(games, tempo, primary_style)
    timeline.append({
        "phase": "early_mid",
        "time": "5-10 min",
        "prediction": early_mid_prediction["text"],
        "events": early_mid_prediction["events"],
        "confidence": early_mid_prediction["confidence"],
        "action": early_mid_prediction["action"],
    })

    # Mid Game (10-20 min)
    mid_prediction = _predict_mid_game(games, tempo, primary_style, winrate)
    timeline.append({
        "phase": "mid_game",
        "time": "10-20 min",
        "prediction": mid_prediction["text"],
        "events": mid_prediction["events"],
        "confidence": mid_prediction["confidence"],
        "action": mid_prediction["action"],
    })

    # Late Game (20+ min)
    late_prediction = _predict_late_game(games, tempo, primary_style, winrate)
    timeline.append({
        "phase": "late_game",
        "time": "20+ min",
        "prediction": late_prediction["text"],
        "events": late_prediction["events"],
        "confidence": late_prediction["confidence"],
        "action": late_prediction["action"],
    })

    # Critical moments
    critical_moments = _identify_critical_moments(games, tempo, series_momentum)

    # Win condition prediction
    win_condition = _predict_win_condition(games, scenarios, tempo)

    # Generate summary
    summary_parts = []
    summary_parts.append(f"This is a {tempo} team ({tempo_note}).")

    if primary_style == "early-game":
        summary_parts.append("They want to snowball early - survive first 15 minutes.")
    elif primary_style == "late-game":
        summary_parts.append("They want to scale - don't let them farm for free.")
    elif primary_style == "high-tempo":
        summary_parts.append("Expect chaos - stay grouped and don't get picked.")

    summary_parts.append(f"Key moment: {critical_moments[0]['moment']}" if critical_moments else "")

    return {
        "timeline": timeline,
        "critical_moments": critical_moments,
        "win_condition": win_condition,
        "tempo": tempo,
        "tempo_note": tempo_note,
        "confidence": "high" if total_games >= 15 else "medium" if total_games >= 8 else "low",
        "summary": " ".join(summary_parts),
        "visualization_notes": {
            "format": "Horizontal timeline with phase markers",
            "colors": "Red for danger phases, Green for opportunity phases",
        },
    }


def _get_draft_prediction(games: List[GameRecord], scenarios: List[Dict[str, Any]]) -> str:
    """Predict their draft approach."""
    if not scenarios:
        return "Standard draft expected"

    main = scenarios[0]
    share = main.get("share", 0)
    style = main.get("name", "Standard")
    picks = main.get("signature_picks", {})

    if share >= 0.5:
        pick_list = ", ".join(list(picks.values())[:3]) if picks else "their comfort picks"
        return f"Expect {style} draft ({share:.0%} of games). Watch for: {pick_list}"
    else:
        return f"Varied drafts - could go {style} or adapt based on bans"


def _predict_early_game(
    games: List[GameRecord],
    tempo: str,
    style: str,
) -> Dict[str, Any]:
    """Predict early game (0-5 min)."""
    events = []

    if tempo in ("bloody", "aggressive") or style == "early-game":
        events.append({
            "event": "Level 1 invade possible",
            "probability": 0.4,
            "icon": "⚔️",
        })
        events.append({
            "event": "Early jungle skirmish",
            "probability": 0.6,
            "icon": "🌲",
        })
        text = "Expect early aggression. They may invade or fight for scuttle."
        action = "Ward pixel bush at 1:15, watch for level 2 ganks"
    elif tempo == "slow" or style == "late-game":
        events.append({
            "event": "Safe farming lanes",
            "probability": 0.7,
            "icon": "🌾",
        })
        text = "Passive early game expected. They'll farm and scale."
        action = "Look for aggressive plays - they won't match your energy"
    else:
        events.append({
            "event": "Standard lane phase",
            "probability": 0.6,
            "icon": "🎯",
        })
        text = "Standard early game. Watch for jungle pathing."
        action = "Track jungle, play for prio in winning lanes"

    return {
        "text": text,
        "events": events,
        "confidence": "medium",
        "action": action,
    }


def _predict_early_mid_game(
    games: List[GameRecord],
    tempo: str,
    style: str,
) -> Dict[str, Any]:
    """Predict early-mid game (5-10 min)."""
    events = []

    if tempo in ("bloody", "aggressive"):
        events.append({
            "event": "First dragon contest",
            "probability": 0.75,
            "icon": "🐉",
        })
        events.append({
            "event": "Mid roams to sidelanes",
            "probability": 0.6,
            "icon": "🏃",
        })
        text = "First objective fights coming. They'll contest dragon."
        action = "Set up vision 1 min before dragon spawn"
    else:
        events.append({
            "event": "Herald setup",
            "probability": 0.5,
            "icon": "👁️",
        })
        events.append({
            "event": "Tower trades possible",
            "probability": 0.4,
            "icon": "🏰",
        })
        text = "They'll look for herald or trade objectives."
        action = "Don't overforce - they might bait you"

    return {
        "text": text,
        "events": events,
        "confidence": "medium",
        "action": action,
    }


def _predict_mid_game(
    games: List[GameRecord],
    tempo: str,
    style: str,
    winrate: float,
) -> Dict[str, Any]:
    """Predict mid game (10-20 min)."""
    events = []

    if style == "early-game" and winrate >= 0.5:
        events.append({
            "event": "Snowball attempt",
            "probability": 0.7,
            "icon": "❄️",
        })
        events.append({
            "event": "Tower diving",
            "probability": 0.5,
            "icon": "💀",
        })
        text = "If ahead, they'll push their advantage hard. Tower dives likely."
        action = "Don't get caught out - group and clear waves safely"
    elif style == "late-game":
        events.append({
            "event": "Stalling and farming",
            "probability": 0.7,
            "icon": "⏳",
        })
        events.append({
            "event": "Avoiding fights",
            "probability": 0.6,
            "icon": "🏃",
        })
        text = "They'll avoid fights and try to scale. Force objectives."
        action = "Force dragon soul or baron - don't let them stall"
    else:
        events.append({
            "event": "5v5 teamfight",
            "probability": 0.5,
            "icon": "⚔️",
        })
        events.append({
            "event": "Baron dance",
            "probability": 0.4,
            "icon": "🟣",
        })
        text = "Standard mid game macro. Expect objective trading."
        action = "Maintain vision control, don't face-check"

    return {
        "text": text,
        "events": events,
        "confidence": "medium",
        "action": action,
    }


def _predict_late_game(
    games: List[GameRecord],
    tempo: str,
    style: str,
    winrate: float,
) -> Dict[str, Any]:
    """Predict late game (20+ min)."""
    events = []

    if tempo in ("bloody", "aggressive"):
        events.append({
            "event": "Forced 5v5 at soul/baron",
            "probability": 0.8,
            "icon": "💥",
        })
        text = "They'll force fights at soul point or baron."
        action = "Don't fight in choke points - use flanks"
    elif style == "late-game":
        events.append({
            "event": "Split push pressure",
            "probability": 0.5,
            "icon": "🔀",
        })
        events.append({
            "event": "Wait for mistake",
            "probability": 0.7,
            "icon": "👀",
        })
        text = "They scale well. Expect patient play waiting for a pick."
        action = "Don't get caught - one death loses the game"
    else:
        events.append({
            "event": "Elder/Baron contest",
            "probability": 0.8,
            "icon": "🐉",
        })
        text = "Game will be decided by one big fight."
        action = "Win the vision war before the fight"

    return {
        "text": text,
        "events": events,
        "confidence": "medium",
        "action": action,
    }


def _identify_critical_moments(
    games: List[GameRecord],
    tempo: str,
    series_momentum: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Identify critical moments where the game is decided."""
    moments = []

    mental = series_momentum.get("mental_profile", "stable")

    if tempo in ("bloody", "aggressive"):
        moments.append({
            "moment": "First blood fight (2-4 min)",
            "importance": "high",
            "reasoning": "They play aggressively early - first blood sets the tone",
            "your_action": "Win the level 2-3 skirmish",
        })

    moments.append({
        "moment": "First dragon contest (~5-6 min)",
        "importance": "high",
        "reasoning": "They prioritize drakes - this is where they're focused",
        "your_action": "Contest with number advantage or trade herald",
    })

    if mental == "tilter":
        moments.append({
            "moment": "After first lost fight",
            "importance": "critical",
            "reasoning": "They tilt after losses - capitalize immediately",
            "your_action": "Push your advantage hard after winning a fight",
        })

    moments.append({
        "moment": "Soul point (~22-25 min)",
        "importance": "critical",
        "reasoning": "Most games are decided here",
        "your_action": "Have vision 2 minutes before, group as 5",
    })

    return moments


def _predict_win_condition(
    games: List[GameRecord],
    scenarios: List[Dict[str, Any]],
    tempo: str,
) -> Dict[str, Any]:
    """Predict their win condition."""
    if tempo in ("bloody", "aggressive"):
        return {
            "their_win_condition": "Snowball through early kills and end before 30 min",
            "how_to_deny": "Survive early game, scale, and outteamfight",
            "key_champions": "Watch for their engage tools",
        }
    elif tempo == "slow":
        return {
            "their_win_condition": "Scale to 3+ items and win through superior teamfight",
            "how_to_deny": "Force fights before their carries are online",
            "key_champions": "Watch for hypercarries (Jinx, Aphelios, etc.)",
        }
    else:
        return {
            "their_win_condition": "Win neutral objectives and convert to map control",
            "how_to_deny": "Match their objective control, don't let them take free drakes",
            "key_champions": "Watch for objective control (Smite fights, zone control)",
        }


# =============================================================================
# MAIN INTEGRATION FUNCTION
# =============================================================================

def generate_enhanced_insights(
    games: List[GameRecord],
    per_player: Dict[str, Any],
    scenarios: List[Any],
    clusters: Dict[int, List[GameRecord]],
    draft_tendencies: Dict[str, Any],
    counters: Dict[str, Any],
    randomness: Dict[str, Any],
    opponent_name: str,
) -> Dict[str, Any]:
    """
    Generate all enhanced insights for the scouting report.
    """
    # Generate executive summary
    executive_summary = generate_executive_summary(
        games, per_player, scenarios, randomness, opponent_name
    )

    # Enhance player cards
    enhanced_players = enhance_player_cards(games, per_player)

    # Enhance scenarios with win conditions
    enhanced_scenarios = enhance_scenarios(games, scenarios, clusters)

    # Generate draft guide
    draft_guide = generate_draft_guide(
        games, per_player, draft_tendencies, counters, randomness
    )

    # Analyze trends
    trends = analyze_trends(games)

    # Generate preparation checklist
    prep_checklist = generate_preparation_checklist(
        games, enhanced_players, enhanced_scenarios, draft_guide
    )

    # =========================================================================
    # NEW FEATURES
    # =========================================================================

    # Blue Side vs Red Side Analysis
    side_analysis = analyze_side_preference(games, per_player)

    # Series Momentum / Mental Edge
    series_momentum = analyze_series_momentum(games)

    # Cheese Detector - Pocket Picks
    cheese_picks = detect_cheese_picks(games)

    # One Thing to Remember per Player
    one_thing_per_player = generate_one_thing_to_remember(
        games, enhanced_players, cheese_picks
    )

    # If They Pick X Decision Tree (for flowchart visualization)
    pick_decision_tree = generate_pick_decision_tree(games, per_player, counters)

    # The Story - Narrative Scouting Report
    the_story = generate_the_story(
        games=games,
        per_player=enhanced_players,
        scenarios=enhanced_scenarios,
        trends=trends,
        side_analysis=side_analysis,
        cheese_picks=cheese_picks,
        opponent_name=opponent_name,
    )

    # Kill Participation Web - Who enables who
    kill_web = generate_kill_participation_web(games, enhanced_players)

    # Game Script Prediction - Minute by minute
    game_script = generate_game_script(games, enhanced_scenarios, series_momentum)

    return {
        "executive_summary": executive_summary,
        "enhanced_players": enhanced_players,
        "enhanced_scenarios": enhanced_scenarios,
        "draft_guide": draft_guide,
        "trends": trends,
        "preparation_checklist": prep_checklist,
        # New features
        "the_story": the_story,
        "side_analysis": side_analysis,
        "series_momentum": series_momentum,
        "cheese_picks": cheese_picks,
        "one_thing_per_player": one_thing_per_player,
        "pick_decision_tree": pick_decision_tree,
        # Standout features
        "kill_participation_web": kill_web,
        "game_script": game_script,
    }
