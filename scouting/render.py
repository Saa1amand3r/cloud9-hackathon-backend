from __future__ import annotations

from typing import Any, Dict


def render_text(report: Dict[str, Any]) -> str:
    meta = report.get("meta", {})
    overview = report.get("opponent_overview", {})
    randomness = report.get("randomness", {})
    scenarios = report.get("scenarios", [])
    counters = report.get("counters", {}).get("by_role", {})

    lines = []
    lines.append("SCOUTING REPORT")
    lines.append(f"Opponent: {meta.get('opponent_name')} | Team: {meta.get('team_name')}")
    lines.append(f"Window: {meta.get('window_gte')} -> {meta.get('window_lte')}")
    lines.append("")

    lines.append("Overview")
    lines.append(
        f"Games: {overview.get('games', 0)} | Wins: {overview.get('wins', 0)} | "
        f"Losses: {overview.get('losses', 0)} | Avg K/D: "
        f"{overview.get('avg_kills', 0):.2f}/{overview.get('avg_deaths', 0):.2f}"
    )
    lines.append(
        f"Randomness: {randomness.get('score', 0):.1f} ({randomness.get('interpretation')})"
    )
    lines.append("")

    lines.append("Scenarios")
    for s in scenarios[:4]:
        lines.append(
            f"- Scenario {s.get('scenario_id')}: share {s.get('share', 0):.2f} | "
            f"winrate {s.get('winrate', 0):.2f} | volatility {s.get('volatility', 0):.2f}"
        )
        sig = s.get("signature_picks") or {}
        if sig:
            lines.append("  signature: " + ", ".join(f"{r}:{c}" for r, c in sig.items()))
        lines.append("  punish: " + (s.get("punish_plan") or ""))

    lines.append("")
    lines.append("Counter Ideas")
    for role, items in counters.items():
        if not items:
            continue
        lines.append(f"- {role}")
        for item in items[:3]:
            lines.append(
                f"  {item.get('our_champ')} vs {item.get('their_champ')} | "
                f"wr {item.get('expected_winrate', 0):.2f} | samples {item.get('samples', 0)}"
            )

    return "\n".join(lines)
