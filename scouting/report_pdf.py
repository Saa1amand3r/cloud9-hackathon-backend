from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.lib.styles import getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import inch  # noqa: E402
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # noqa: E402


def _load_report(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_plot(fig, path: str) -> str:
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _plot_strategy_clusters(report: Dict[str, Any], out_path: str) -> Optional[str]:
    clusters = report.get("visualization", {}).get("strategy_clusters") or []
    if not clusters:
        return None

    # Build stacked bars from pick_buckets
    buckets = sorted({k for c in clusters for k in (c.get("pick_buckets") or {}).keys()})
    if not buckets:
        return None
    labels = [f"S{c.get('scenario_id')}" for c in clusters]
    shares = [c.get("share", 0.0) for c in clusters]
    winrates = [c.get("winrate", 0.0) for c in clusters]

    fig, ax = plt.subplots(figsize=(7, 3.5))
    bottoms = [0.0] * len(clusters)
    for b in buckets:
        vals = [float((c.get("pick_buckets") or {}).get(b, 0.0)) for c in clusters]
        ax.bar(labels, vals, bottom=bottoms, label=b)
        bottoms = [b0 + v for b0, v in zip(bottoms, vals)]

    ax2 = ax.twinx()
    ax2.plot(labels, winrates, color="black", marker="o", linewidth=1.5, label="winrate")
    ax2.set_ylim(0, 1)
    ax.set_title("Strategy Clusters (Pick Buckets + Winrate)")
    ax.set_ylabel("Pick Bucket Share")
    ax2.set_ylabel("Winrate")
    ax.legend(loc="upper left", fontsize=8)
    ax2.legend(loc="upper right", fontsize=8)
    return _save_plot(fig, out_path)


def _plot_scenario_radar(report: Dict[str, Any], out_path: str) -> Optional[str]:
    clusters = report.get("visualization", {}).get("strategy_clusters") or []
    axes = report.get("visualization", {}).get("scenario_fingerprint_axes") or []
    if not clusters or not axes:
        return None

    fig = plt.figure(figsize=(6, 4))
    ax = fig.add_subplot(111, polar=True)
    angles = [n / float(len(axes)) * 2 * math.pi for n in range(len(axes))]
    angles += angles[:1]

    for c in clusters[:4]:
        fp = c.get("fingerprint") or {}
        vals = [float(fp.get(a, 0.0) or 0.0) for a in axes]
        vals += vals[:1]
        ax.plot(angles, vals, linewidth=1.5, label=f"S{c.get('scenario_id')}")
        ax.fill(angles, vals, alpha=0.1)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(axes, fontsize=8)
    ax.set_yticklabels([])
    ax.set_title("Scenario Fingerprint (Radar)")
    ax.legend(loc="upper right", bbox_to_anchor=(1.2, 1.1), fontsize=7)
    return _save_plot(fig, out_path)


def _plot_counter_matrix(report: Dict[str, Any], out_path: str) -> Optional[str]:
    matrix = report.get("visualization", {}).get("counter_matrix") or {}
    if not matrix:
        return None

    roles = list(matrix.keys())[:4]
    if not roles:
        return None

    fig, axes = plt.subplots(1, len(roles), figsize=(5 * len(roles), 4))
    if len(roles) == 1:
        axes = [axes]

    for ax, role in zip(axes, roles):
        data = matrix.get(role, {})
        rows = data.get("rows") or []
        cols = data.get("cols") or []
        cells = data.get("cells") or []
        if not rows or not cols or not cells:
            ax.axis("off")
            ax.set_title(f"{role} (no data)")
            continue
        # Build heatmap values
        values = []
        for r_idx in range(len(rows)):
            row_vals = []
            for c_idx in range(len(cols)):
                cell = cells[r_idx][c_idx]
                row_vals.append(cell.get("winrate") if cell else None)
            values.append(row_vals)

        # Plot
        im = ax.imshow(
            [[v if v is not None else 0 for v in row] for row in values],
            vmin=0,
            vmax=1,
            cmap="Blues",
        )
        ax.set_xticks(range(len(cols)))
        ax.set_xticklabels(cols, rotation=45, ha="right", fontsize=7)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels(rows, fontsize=7)
        ax.set_title(f"Counter Matrix ({role})")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    return _save_plot(fig, out_path)


def _plot_style_triangle(report: Dict[str, Any], out_path: str) -> Optional[str]:
    style = report.get("insights", {}).get("style_triangle") or {}
    team = style.get("team") or {}
    opp = style.get("opponent") or {}
    if not team or not opp:
        return None

    def _vec(s: Dict[str, Any]) -> List[float]:
        return [float(s.get("aggression", 0.0)), float(s.get("control", 0.0)), float(s.get("flexibility", 0.0))]

    team_vals = _vec(team)
    opp_vals = _vec(opp)
    axes = ["Aggression", "Control", "Flexibility"]

    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    x = [0, 1, 0.5, 0]
    y = [0, 0, math.sqrt(3) / 2, 0]
    ax.plot(x, y, color="gray")

    def _plot_point(vals, label, color):
        s = sum(vals)
        if s <= 0 or all(v == 0 for v in vals):
            px, py = 0.5, math.sqrt(3) / 6
        else:
            a, b, c = [v / s for v in vals]
            px = 0.5 * (2 * b + c) / (a + b + c)
            py = (math.sqrt(3) / 2) * (c / (a + b + c))
        ax.scatter([px], [py], color=color, s=60, label=label)

    _plot_point(team_vals, "Team", "#2a6fdb")
    _plot_point(opp_vals, "Opponent", "#db5a2a")
    ax.text(0, -0.05, axes[0], ha="center", fontsize=8)
    ax.text(1, -0.05, axes[1], ha="center", fontsize=8)
    ax.text(0.5, math.sqrt(3) / 2 + 0.05, axes[2], ha="center", fontsize=8)
    ax.set_title("Style Triangle")
    ax.axis("off")
    ax.legend(loc="upper right", fontsize=8)
    return _save_plot(fig, out_path)


def _plot_top_priority_picks(report: Dict[str, Any], out_path: str) -> Optional[str]:
    draft = report.get("draft_tendencies") or {}
    picks = draft.get("priority_picks") or []
    if not picks:
        return None
    top = picks[:10]
    labels = [p.get("character") for p in top]
    values = [float(p.get("share") or 0.0) for p in top]
    fig, ax = plt.subplots(figsize=(6.5, 3.5))
    ax.barh(labels[::-1], values[::-1], color="#4a7ebb")
    ax.set_title("Opponent Priority Picks (Share)")
    ax.set_xlabel("Share")
    return _save_plot(fig, out_path)


def _plot_player_volatility(report: Dict[str, Any], out_path: str) -> Optional[str]:
    players = list((report.get("per_player") or {}).values())
    if not players:
        return None
    players.sort(key=lambda p: p.get("volatility", 0), reverse=True)
    top = players[:10]
    labels = [p.get("name") or p.get("player_id") for p in top]
    values = [float(p.get("volatility") or 0.0) for p in top]
    fig, ax = plt.subplots(figsize=(6.5, 3.5))
    ax.barh(labels[::-1], values[::-1], color="#7c4ab8")
    ax.set_xlim(0, 1)
    ax.set_title("Player Volatility (Entropy)")
    ax.set_xlabel("Volatility")
    return _save_plot(fig, out_path)


def _plot_signature_cluster_share(report: Dict[str, Any], out_path: str) -> Optional[str]:
    sig = report.get("insights", {}).get("signature_clusters", {}).get("opponent") or {}
    clusters = sig.get("clusters") or []
    if not clusters:
        return None
    labels = [f"C{c.get('cluster_id')}" for c in clusters]
    shares = [float(c.get("share") or 0.0) for c in clusters]
    winrates = [float(c.get("winrate") or 0.0) for c in clusters]
    fig, ax = plt.subplots(figsize=(6.5, 3.5))
    ax.bar(labels, shares, color="#2f9e8f")
    ax2 = ax.twinx()
    ax2.plot(labels, winrates, color="black", marker="o", linewidth=1.5)
    ax.set_title("Signature Cluster Share + Winrate")
    ax.set_ylabel("Share")
    ax2.set_ylabel("Winrate")
    ax2.set_ylim(0, 1)
    return _save_plot(fig, out_path)


def _plot_roster_stability(report: Dict[str, Any], out_path: str) -> Optional[str]:
    roster = report.get("insights", {}).get("roster_stability") or {}
    opp = roster.get("opponent") or {}
    team = roster.get("team") or {}
    if not opp and not team:
        return None
    labels = ["Opponent", "Team"]
    values = [float(opp.get("top5_share") or 0.0), float(team.get("top5_share") or 0.0)]
    fig, ax = plt.subplots(figsize=(4.5, 3.2))
    ax.bar(labels, values, color=["#db5a2a", "#2a6fdb"])
    ax.set_ylim(0, 1)
    ax.set_title("Roster Stability (Top‑5 Share)")
    return _save_plot(fig, out_path)


def _build_stable_table(report: Dict[str, Any]) -> Table:
    stable = report.get("insights", {}).get("stable_champions") or {}
    opp = stable.get("opponent") or []
    team = stable.get("team") or []
    rows = [["Opponent Stable Champs", "Winrate", "Games"], ["Team Stable Champs", "Winrate", "Games"]]

    def _row(items: List[Dict[str, Any]]) -> List[str]:
        if not items:
            return ["-", "-", "-"]
        top = items[:5]
        champs = ", ".join([c.get("character") for c in top if c.get("character")])
        winrate = f"{(top[0].get('winrate') or 0):.2f}"
        games = str(top[0].get("games") or 0)
        return [champs or "-", winrate, games]

    rows.append(_row(opp))
    rows.append(_row(team))
    table = Table(rows, colWidths=[3.6 * inch, 1.0 * inch, 0.8 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("BACKGROUND", (0, 1), (-1, 1), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
            ]
        )
    )
    return table


def build_pdf(input_path: str, output_path: str) -> None:
    report = _load_report(input_path)

    styles = getSampleStyleSheet()
    story: List[Any] = []
    story.append(Paragraph("Scouting Report", styles["Title"]))
    meta = report.get("meta") or {}
    story.append(Paragraph(f"{meta.get('team_name')} vs {meta.get('opponent_name')}", styles["Heading2"]))
    story.append(Spacer(1, 0.2 * inch))

    # Overview + key takeaways
    overview = report.get("opponent_overview") or {}
    randomness = report.get("randomness") or {}
    plan = report.get("plan") or {}
    wins = overview.get("wins", 0)
    losses = overview.get("losses", 0)
    games = overview.get("games", 0)
    winrate = (wins / games) if games else 0.0

    story.append(Paragraph("Snapshot", styles["Heading3"]))
    story.append(
        Paragraph(
            f"Games analyzed: <b>{games}</b> • Opponent winrate: <b>{winrate:.0%}</b> "
            f"• Avg K/D: <b>{overview.get('avg_kills', 0):.1f}/{overview.get('avg_deaths', 0):.1f}</b>",
            styles["BodyText"],
        )
    )
    story.append(
        Paragraph(
            f"Randomness: <b>{randomness.get('interpretation','n/a')}</b> "
            f"(score {randomness.get('score',0):.0f}/100). {randomness.get('advice','')}",
            styles["BodyText"],
        )
    )
    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("Draft Plan", styles["Heading3"]))
    ban_plan = ", ".join(plan.get("ban_plan") or []) or "-"
    story.append(Paragraph(f"<b>Ban plan:</b> {ban_plan}", styles["BodyText"]))
    if plan.get("draft_plan"):
        story.append(Paragraph(f"<b>Draft plan:</b> {plan['draft_plan']}", styles["BodyText"]))
    story.append(Spacer(1, 0.2 * inch))

    # Stable champs table
    story.append(Paragraph("Stable Picks (Quick View)", styles["Heading3"]))
    story.append(_build_stable_table(report))
    story.append(Spacer(1, 0.2 * inch))

    # Scenarios summary text
    scenarios = report.get("scenarios") or []
    if scenarios:
        story.append(Paragraph("Scenario Cards (Text)", styles["Heading3"]))
        for s in scenarios:
            sid = s.get("scenario_id")
            share = s.get("share", 0.0)
            winrate = s.get("winrate", 0.0)
            punish = s.get("punish_plan", "")
            story.append(
                Paragraph(
                    f"Scenario {sid}: share <b>{share:.0%}</b>, winrate <b>{winrate:.0%}</b>. "
                    f"Punish: {punish}",
                    styles["BodyText"],
                )
            )
        story.append(Spacer(1, 0.2 * inch))

    # Roster stability + stable overlap
    insights = report.get("insights") or {}
    roster = insights.get("roster_stability") or {}
    overlap = insights.get("stable_overlap") or {}
    story.append(Paragraph("Roster Stability & Shared Comforts", styles["Heading3"]))
    opp_rs = roster.get("opponent") or {}
    team_rs = roster.get("team") or {}
    story.append(
        Paragraph(
            f"Opponent roster stability (top‑5 share): <b>{(opp_rs.get('top5_share') or 0):.2f}</b> "
            f"across {opp_rs.get('games_total', 0)} games. "
            f"Team roster stability: <b>{(team_rs.get('top5_share') or 0):.2f}</b>.",
            styles["BodyText"],
        )
    )
    shared = overlap.get("shared_champions") or []
    story.append(
        Paragraph(
            f"Shared stable champs (direct contest risk): <b>{', '.join(shared[:8]) if shared else '-'}</b>",
            styles["BodyText"],
        )
    )
    story.append(Spacer(1, 0.2 * inch))

    # Draft tendencies (priority + flex)
    draft = report.get("draft_tendencies") or {}
    priority = [p.get("character") for p in (draft.get("priority_picks") or []) if p.get("character")]
    flex = draft.get("flex_picks") or []
    story.append(Paragraph("Draft Tendencies", styles["Heading3"]))
    story.append(
        Paragraph(
            f"Priority picks: <b>{', '.join(priority[:10]) if priority else '-'}</b>",
            styles["BodyText"],
        )
    )
    story.append(
        Paragraph(
            f"Flex picks (multi‑role): <b>{', '.join(flex[:10]) if flex else '-'}</b>",
            styles["BodyText"],
        )
    )
    story.append(Spacer(1, 0.2 * inch))

    # Per-player tendencies (top comfort + volatility)
    per_player = report.get("per_player") or {}
    if per_player:
        story.append(Paragraph("Key Player Tendencies", styles["Heading3"]))
        # Sort by volatility descending to highlight chaotic players
        rows = list(per_player.values())
        rows.sort(key=lambda r: r.get("volatility", 0), reverse=True)
        for p in rows[:10]:
            comfort = p.get("comfort_picks") or []
            comfort_list = [c.get("character") for c in comfort if c.get("character")]
            story.append(
                Paragraph(
                    f"{p.get('name') or p.get('player_id')}: "
                    f"comfort <b>{', '.join(comfort_list) if comfort_list else '-'}</b>, "
                    f"volatility <b>{p.get('volatility', 0):.2f}</b>.",
                    styles["BodyText"],
                )
            )
        story.append(Spacer(1, 0.2 * inch))

    # Signature clusters (gameplan cards)
    sig = insights.get("signature_clusters") or {}
    opp_sig = sig.get("opponent") or {}
    if opp_sig:
        story.append(Paragraph("Signature Cluster Cards (Opponent)", styles["Heading3"]))
        for c in (opp_sig.get("clusters") or [])[:4]:
            champs = ", ".join(c.get("top_champs") or [])
            story.append(
                Paragraph(
                    f"Cluster {c.get('cluster_id')}: share <b>{(c.get('share') or 0):.0%}</b>, "
                    f"winrate <b>{(c.get('winrate') or 0):.0%}</b>, "
                    f"top champs: <b>{champs or '-'}</b>.",
                    styles["BodyText"],
                )
            )
        story.append(Spacer(1, 0.2 * inch))

    # Player similarity graph summary
    sim = insights.get("player_similarity") or {}
    opp_sim = sim.get("opponent") or {}
    edges = opp_sim.get("edges") or []
    if edges:
        story.append(Paragraph("Player Similarity (Champion Pool Overlap)", styles["Heading3"]))
        for e in edges[:8]:
            a = e.get("player_a", {})
            b = e.get("player_b", {})
            story.append(
                Paragraph(
                    f"{a.get('name') or a.get('id')} ↔ {b.get('name') or b.get('id')}: "
                    f"Jaccard <b>{(e.get('similarity') or 0):.2f}</b> "
                    f"(shared: {', '.join(e.get('shared_champs') or [])})",
                    styles["BodyText"],
                )
            )
        story.append(Spacer(1, 0.2 * inch))

    # Counterfactual bans
    cf = report.get("insights", {}).get("counterfactual_bans") or []
    if cf:
        c = cf[0]
        story.append(Paragraph("Counterfactual Ban Impact", styles["Heading3"]))
        story.append(
            Paragraph(
                f"If they lose <b>{c.get('ban_champ')}</b>, replacement <b>{c.get('replacement')}</b> "
                f"projects ~{(c.get('estimated_winrate_drop') or 0):.0%} winrate drop.",
                styles["BodyText"],
            )
        )
        story.append(Spacer(1, 0.2 * inch))

    with tempfile.TemporaryDirectory() as tmp:
        # Graphs
        plots = [
            (
                "strategy.png",
                _plot_strategy_clusters,
                "Strategy clusters: stacked bars show pick‑style buckets per scenario; line is winrate.",
            ),
            (
                "radar.png",
                _plot_scenario_radar,
                "Scenario fingerprint: radar of aggression, volatility, teamfightiness, and macro (if available).",
            ),
            (
                "matrix.png",
                _plot_counter_matrix,
                "Counter matrix: rows = opponent likely champs, columns = your answers; color = smoothed winrate.",
            ),
            (
                "style.png",
                _plot_style_triangle,
                "Style triangle: relative balance of aggression, control, and flexibility for team vs opponent.",
            ),
            (
                "priority.png",
                _plot_top_priority_picks,
                "Priority picks: opponent’s most frequent champions in this window.",
            ),
            (
                "volatility.png",
                _plot_player_volatility,
                "Player volatility: higher entropy = wider champion pool / less predictable.",
            ),
            (
                "clusters.png",
                _plot_signature_cluster_share,
                "Signature clusters: share of each gameplan + winrate trend.",
            ),
            (
                "roster.png",
                _plot_roster_stability,
                "Roster stability: share of games played by the top 5 players.",
            ),
        ]
        for name, fn, caption in plots:
            path = os.path.join(tmp, name)
            img = fn(report, path)
            if img and os.path.exists(img):
                story.append(Paragraph(caption, styles["BodyText"]))
                story.append(Image(img, width=6.5 * inch, height=3.5 * inch))
                story.append(Spacer(1, 0.2 * inch))

        doc = SimpleDocTemplate(output_path, pagesize=letter)
        doc.build(story)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render scouting report JSON to PDF.")
    parser.add_argument("--input", required=True, help="Path to report.json")
    parser.add_argument("--output", required=True, help="Path to output PDF")
    args = parser.parse_args()
    build_pdf(args.input, args.output)


if __name__ == "__main__":
    main()
