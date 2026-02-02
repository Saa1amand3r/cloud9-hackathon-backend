"""Transform backend report format to frontend expected format."""

import logging
from datetime import datetime
from typing import Any, Dict, List
from ...domain.value_objects.types import Role

logger = logging.getLogger(__name__)


def _to_camel_case(snake_str: str) -> str:
    """Convert snake_case to camelCase."""
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def _get_role_standard(role_str: str | None) -> str:
    """Standardize role names."""
    if not role_str:
        return "mid"
    role_lower = role_str.lower()
    role_map = {
        "top": "top",
        "toplane": "top",
        "top_lane": "top",
        "jungle": "jungle",
        "jng": "jungle",
        "jungler": "jungle",
        "mid": "mid",
        "midlane": "mid",
        "mid_lane": "mid",
        "middle": "mid",
        "adc": "adc",
        "bot": "adc",
        "botlane": "adc",
        "bot_lane": "adc",
        "carry": "adc",
        "marksman": "adc",
        "support": "support",
        "sup": "support",
        "supp": "support",
    }
    return role_map.get(role_lower, "mid")


def _normalize_champion_name(name: str) -> str:
    """Normalize champion names for Riot's Data Dragon API.

    Data Dragon uses specific formats:
    - No spaces: "MissFortune" not "Miss Fortune"
    - No apostrophes: "KaiSa" not "Kai'Sa"
    - Some special cases like "Wukong" not "MonkeyKing"
    """
    if not name:
        return name

    # Special case mappings for champions with different internal names
    special_cases = {
        "Renata Glasc": "Renata",
        "RenataGlasc": "Renata",
        "Nunu & Willump": "Nunu",
        "NunuWillump": "Nunu",
        "Bel'Veth": "Belveth",
        "BelVeth": "Belveth",
        "Cho'Gath": "Chogath",
        "ChoGath": "Chogath",
        "Dr. Mundo": "DrMundo",
        "Jarvan IV": "JarvanIV",
        "Kai'Sa": "Kaisa",
        "KaiSa": "Kaisa",
        "Kha'Zix": "Khazix",
        "KhaZix": "Khazix",
        "K'Sante": "KSante",
        "KSante": "KSante",
        "LeBlanc": "Leblanc",
        "Lee Sin": "LeeSin",
        "Master Yi": "MasterYi",
        "Miss Fortune": "MissFortune",
        "Rek'Sai": "RekSai",
        "RekSai": "RekSai",
        "Tahm Kench": "TahmKench",
        "Twisted Fate": "TwistedFate",
        "Vel'Koz": "Velkoz",
        "VelKoz": "Velkoz",
        "Xin Zhao": "XinZhao",
    }

    # Check special cases first
    if name in special_cases:
        return special_cases[name]

    # Remove spaces, apostrophes, and periods
    normalized = name.replace(" ", "").replace("'", "").replace(".", "")

    return normalized


def _get_randomness_level(randomness: Dict[str, Any]) -> str:
    """Convert randomness score to level."""
    score = randomness.get("score", 0.5)
    interpretation = randomness.get("interpretation", "moderate")

    if interpretation == "chaotic" or score >= 0.65:
        return "chaotic"
    elif interpretation == "predictable" or score < 0.35:
        return "predictable"
    return "moderate"


def _get_draft_priority(plan: Dict[str, Any], randomness: Dict[str, Any]) -> str:
    """Determine draft priority based on analysis."""
    interpretation = randomness.get("interpretation", "moderate")
    if interpretation == "chaotic":
        return "flexibility"
    elif interpretation == "predictable":
        return "counter"
    return "comfort"


def _extract_players_from_report(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract unique players from per_player data."""
    per_player = report.get("per_player", {})
    players = []
    seen_ids = set()

    for player_id, player_data in per_player.items():
        if player_id in seen_ids:
            continue
        seen_ids.add(player_id)

        role = _get_role_standard(player_data.get("role"))
        players.append({
            "playerId": player_id,
            "nickname": player_data.get("name", player_id),
            "role": role,
        })

    # Sort by role order
    role_order = {"top": 0, "jungle": 1, "mid": 2, "adc": 3, "support": 4}
    players.sort(key=lambda p: role_order.get(p["role"], 5))

    return players[:5]  # Limit to 5 players


def _extract_stable_picks_by_role(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract stable picks grouped by role."""
    per_player = report.get("per_player", {})

    # Get stable champions data which has actual game stats
    stable_champions = report.get("insights", {}).get("stable_champions", {}).get("opponent", [])

    # Create a map of champion -> stats
    champ_stats = {}
    for champ_data in stable_champions:
        champ_name = champ_data.get("character")
        if champ_name:
            champ_stats[champ_name] = {
                "games": champ_data.get("games", 0),
                "wins": champ_data.get("wins", 0),
                "winrate": champ_data.get("winrate", 0) * 100,  # Convert to percentage
            }

    role_picks: Dict[str, List[Dict[str, Any]]] = {
        "top": [],
        "jungle": [],
        "mid": [],
        "adc": [],
        "support": [],
    }

    for player_id, player_data in per_player.items():
        role = _get_role_standard(player_data.get("role"))
        comfort_picks = player_data.get("comfort_picks", [])

        for pick in comfort_picks[:3]:  # Top 3 per player
            champion = pick.get("character") or pick.get("champion")
            if not champion:
                continue

            # Get stats from stable_champions if available
            stats = champ_stats.get(champion, {})
            games = stats.get("games", 0)
            winrate = stats.get("winrate", 0)

            # Fallback: estimate from pick share if no stable data
            if games == 0:
                total_games = report.get("opponent_overview", {}).get("games", 1)
                games = int(pick.get("share", 0) * total_games)
                winrate = 50.0  # Unknown, use neutral

            # Simple KDA estimate (we don't have per-champion KDA)
            kda = 2.5  # Placeholder since we don't have per-champion KDA data

            role_picks[role].append({
                "championId": _normalize_champion_name(champion),
                "role": role,
                "gamesPlayed": games,
                "winrate": round(winrate, 1),
                "kda": kda,
                "isSignaturePick": pick.get("share", 0) >= 0.25,
            })

    # Build result grouped by role
    result = []
    for role in ["top", "jungle", "mid", "adc", "support"]:
        picks = role_picks[role]
        # Sort by games played and limit to 3
        picks.sort(key=lambda p: p["gamesPlayed"], reverse=True)
        if picks:
            result.append({
                "role": role,
                "picks": picks[:3],
            })

    return result


def _extract_draft_tendencies(report: Dict[str, Any]) -> Dict[str, Any]:
    """Extract draft tendencies from report."""
    draft = report.get("draft_tendencies", {})
    priority_picks = draft.get("priority_picks", [])

    tendencies = []
    for i, pick in enumerate(priority_picks[:10]):
        champion = pick.get("character") or pick.get("champion")
        if not champion:
            continue

        # Priority picks have "share" which is already the pick rate as a decimal (0.0 to 1.0)
        pick_rate = pick.get("share", 0) * 100  # Convert to percentage

        # Ban rate - currently not tracked in scouting data
        ban_rate = pick.get("ban_rate", 0)

        tendencies.append({
            "championId": _normalize_champion_name(champion),
            "pickRate": round(pick_rate, 1),
            "banRate": round(ban_rate, 1),
            "priority": i + 1,
        })

    return {"priorityPicks": tendencies}


def _extract_scenarios(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract scenario cards from report."""
    scenarios = report.get("scenarios", [])
    enhanced_scenarios = report.get("enhanced_scenarios", [])

    result = []
    seen_ids = set()

    for i, scenario in enumerate(scenarios[:5]):
        scenario_id = scenario.get("scenario_id", i)

        # Skip if we've already processed this scenario ID (deduplication)
        if scenario_id in seen_ids:
            continue
        seen_ids.add(scenario_id)

        share = scenario.get("share", 0) * 100  # Convert to percentage
        winrate = scenario.get("winrate", 0) * 100

        # Get enhanced data if available
        enhanced = next(
            (s for s in enhanced_scenarios if s.get("scenario_id") == scenario_id),
            {}
        )

        # Extract signature picks for stats
        sig_picks = scenario.get("signature_picks", {})
        volatility = scenario.get("volatility", 0.5)

        # Determine punish strategy
        punish_plan = scenario.get("punish_plan", "") or enhanced.get("how_to_beat", "")
        action = "ban"
        targets = []

        if sig_picks:
            # Normalize champion names for images
            targets = [_normalize_champion_name(champ) for champ in list(sig_picks.values())[:2]]
        if "pick" in punish_plan.lower():
            action = "pick"
        elif "counter" in punish_plan.lower():
            action = "counter"
        elif "play" in punish_plan.lower() or "style" in punish_plan.lower():
            action = "playstyle"
            targets = []

        # Generate a readable name
        name = enhanced.get("name", f"Scenario {scenario_id}")
        if not name or name == f"Scenario {scenario_id}":
            if volatility > 0.7:
                name = "Chaos Flex"
            elif share > 40:
                name = "Primary Style"
            elif winrate > 60:
                name = "High Win Comp"
            else:
                name = f"Style {scenario_id + 1}"

        result.append({
            "scenarioId": str(scenario_id),
            "name": name,
            "description": enhanced.get("description"),
            "likelihood": round(share, 1),
            "winrate": round(winrate, 1),
            "stats": {
                "teamfightiness": enhanced.get("teamfightiness", 0.5),
                "earlyAggression": enhanced.get("early_aggression", 0.5),
                "draftVolatility": volatility,
                "macro": enhanced.get("macro", 0.5),
            },
            "punishStrategy": {
                "action": action,
                "targets": targets,
                "description": punish_plan or f"Counter this style",
            },
        })

    return result


def _extract_player_analysis(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract player analysis from report."""
    per_player = report.get("per_player", {})
    enhanced_players = report.get("enhanced_players", {})

    # Get stable champions data for winrate info
    stable_champions = report.get("insights", {}).get("stable_champions", {}).get("opponent", [])
    champ_stats = {}
    for champ_data in stable_champions:
        champ_name = champ_data.get("character")
        if champ_name:
            champ_stats[champ_name] = {
                "games": champ_data.get("games", 0),
                "wins": champ_data.get("wins", 0),
                "winrate": champ_data.get("winrate", 0) * 100,
            }

    result = []
    for player_id, player_data in per_player.items():
        # Get enhanced data if available
        # enhanced_players is a dict with player_id as keys
        enhanced = enhanced_players.get(player_id, {}) if isinstance(enhanced_players, dict) else {}

        role = _get_role_standard(player_data.get("role"))

        # Volatility is 0-1, but frontend expects percentage (0-100)
        # Actually, frontend might expect 0-1 for normalized values. Let's keep it 0-1.
        entropy = player_data.get("volatility", 0.5)

        # Build champion pool
        comfort_picks = player_data.get("comfort_picks", [])
        pick_distribution = player_data.get("pick_distribution", [])
        total_games = report.get("opponent_overview", {}).get("games", 1)

        champion_pool = []
        for pick in comfort_picks[:5]:
            champion = pick.get("character") or pick.get("champion")
            if not champion:
                continue

            # Get stats from stable_champions if available
            stats = champ_stats.get(champion, {})
            games = stats.get("games", 0)
            winrate = stats.get("winrate", 0)

            # Fallback: estimate from pick share
            if games == 0:
                games = int(pick.get("share", 0) * total_games)
                # Find winrate from pick_distribution if available
                dist_entry = next((p for p in pick_distribution if p.get("character") == champion), None)
                winrate = 50.0  # Unknown, use neutral

            champion_pool.append({
                "championId": _normalize_champion_name(champion),
                "gamesPlayed": games,
                "winrate": round(winrate, 1),
                "isComfort": pick.get("share", 0) >= 0.2,
            })

        # Build tendencies
        tendencies = {
            "earlyGameAggression": enhanced.get("early_aggression", 0.5),
            "teamfightParticipation": enhanced.get("teamfight_participation", 0.7),
            "soloKillRate": enhanced.get("solo_kill_rate", 0.3),
            "visionScore": enhanced.get("vision_score", 0.5),
        }

        result.append({
            "playerId": player_id,
            "nickname": player_data.get("name", player_id),
            "role": role,
            "entropy": round(entropy, 2),  # Keep as 0-1 normalized value
            "championPool": champion_pool,
            "tendencies": tendencies,
        })

    # Sort by role order
    role_order = {"top": 0, "jungle": 1, "mid": 2, "adc": 3, "support": 4}
    result.sort(key=lambda p: role_order.get(p["role"], 5))

    return result


def _extract_counter_picks(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract counter pick strategies."""
    counters = report.get("counters", {})
    draft = report.get("draft_tendencies", {})
    priority_picks = draft.get("priority_picks", [])

    result = []
    seen_targets = set()

    # Get top priority picks to suggest counters for
    for pick in priority_picks[:5]:
        target = pick.get("character") or pick.get("champion")
        if not target or target in seen_targets:
            continue
        seen_targets.add(target)

        # Find counters for this target
        role_counters = counters.get("by_role", {})
        suggested = []

        for role, role_data in role_counters.items():
            # role_data is already the list of counter dicts
            if not isinstance(role_data, list):
                continue
            for counter_info in role_data:
                if counter_info.get("enemy_pick") == target:
                    counter_champ = counter_info.get("our_pick")
                    if counter_champ and counter_champ not in suggested:
                        suggested.append(counter_champ)

        if suggested:
            result.append({
                "targetChampion": _normalize_champion_name(target),
                "suggestedCounters": [_normalize_champion_name(c) for c in suggested[:3]],
            })

    return result


def transform_report_to_frontend(
    raw_report: Dict[str, Any],
    meta: Dict[str, Any],
) -> Dict[str, Any]:
    """Transform backend raw report to frontend expected format.

    Args:
        raw_report: Raw report from scouting module
        meta: Request metadata

    Returns:
        Frontend-compatible TeamAnalysisReport
    """
    import logging
    logger = logging.getLogger(__name__)

    # Extract key data sections
    try:
        outcomes = raw_report.get("opponent_overview", {})
        randomness = raw_report.get("randomness", {})
        plan = raw_report.get("plan", {})
        exec_summary = raw_report.get("executive_summary", {})
        draft_guide = raw_report.get("draft_guide", {})
        report_meta = raw_report.get("meta", {})
        logger.info("Successfully extracted top-level sections")
    except Exception as e:
        logger.error(f"Error extracting top-level sections: {e}")
        raise

    # Calculate statistics
    total_games = outcomes.get("games", 0)  # Field is "games", not "total"
    wins = outcomes.get("wins", 0)
    avg_kills = outcomes.get("avg_kills", 0)
    avg_deaths = outcomes.get("avg_deaths", 0)

    # Build report info
    try:
        logger.info("Building report info...")
        report_info = {
            "teamId": report_meta.get("opponent_id", meta.get("opponent", "unknown")),
            "teamName": report_meta.get("opponent_name", meta.get("opponent", "Unknown Team")),
            "gamesAnalyzed": total_games,
            "opponentWinrate": round((wins / total_games * 100) if total_games > 0 else 0, 1),
            "averageKills": round(avg_kills, 1),
            "averageDeaths": round(avg_deaths, 1),
            "players": _extract_players_from_report(raw_report),
            "timeframe": {
                "startDate": report_meta.get("window_gte", "")[:10] if report_meta.get("window_gte") else "",
                "endDate": report_meta.get("window_lte", "")[:10] if report_meta.get("window_lte") else "",
                "patchVersion": None,
            },
            "generatedAt": datetime.utcnow().isoformat() + "Z",
        }
        logger.info("Successfully built report info")
    except Exception as e:
        logger.error(f"Error building report info: {e}")
        raise

    # Build overview
    strategic_insights = []
    if exec_summary.get("key_strengths"):
        strategic_insights.extend(exec_summary["key_strengths"][:2])
    if exec_summary.get("key_weaknesses"):
        strategic_insights.extend(exec_summary["key_weaknesses"][:2])
    if exec_summary.get("game_plan_recommendation"):
        strategic_insights.append(exec_summary["game_plan_recommendation"])
    if not strategic_insights:
        strategic_insights = [
            plan.get("draft_plan", "Prepare flexible draft strategy"),
            f"Focus on denying {', '.join(plan.get('ban_plan', [])[:3])}",
        ]

    overview = {
        "randomness": _get_randomness_level(randomness),
        "randomnessScore": round(randomness.get("score", 0.5) / 100, 2) if randomness.get("score", 0) > 1 else round(randomness.get("score", 0.5), 2),
        "strategicInsights": strategic_insights[:6],
    }

    # Build draft plan
    try:
        logger.info("Building draft plan...")
        ban_plan = plan.get("ban_plan", [])
        if draft_guide.get("must_ban"):
            logger.info(f"draft_guide['must_ban'] type: {type(draft_guide['must_ban'])}")
            logger.info(f"draft_guide['must_ban'] first item type: {type(draft_guide['must_ban'][0]) if draft_guide['must_ban'] else 'empty'}")
            must_bans = [b.get("champion") for b in draft_guide["must_ban"] if b.get("champion")]
            ban_plan = must_bans + [b for b in ban_plan if b not in must_bans]

        draft_plan = {
            "banPlan": [_normalize_champion_name(c) for c in ban_plan[:5] if c],
            "draftPriority": _get_draft_priority(plan, randomness),
            "counterPicks": _extract_counter_picks(raw_report),
            "strategicNotes": [],
        }
        logger.info("Successfully built draft plan")
    except Exception as e:
        logger.error(f"Error building draft plan: {e}")
        raise

    # Build full response
    try:
        logger.info("Extracting draft tendencies...")
        draft_tendencies = _extract_draft_tendencies(raw_report)
        logger.info("Extracting stable picks...")
        stable_picks = _extract_stable_picks_by_role(raw_report)
        logger.info("Extracting scenarios...")
        scenarios = _extract_scenarios(raw_report)
        logger.info("Extracting player analysis...")
        player_analysis = _extract_player_analysis(raw_report)
        logger.info("All extractions complete")
    except Exception as e:
        logger.error(f"Error in final extraction phase: {e}")
        raise

    return {
        "reportInfo": report_info,
        "overview": overview,
        "draftPlan": draft_plan,
        "draftTendencies": draft_tendencies,
        "stablePicks": stable_picks,
        "scenarios": scenarios,
        "playerAnalysis": player_analysis,
    }
