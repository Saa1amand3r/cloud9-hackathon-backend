"""Report domain entity - the main aggregate."""

from dataclasses import dataclass, field
from typing import List

from ..value_objects.types import (
    NormalizedValue,
    Percentage,
    RandomnessLevel,
    TeamId,
    Timeframe,
)
from .draft import DraftPlan, DraftTendencies, StablePicksByRole
from .player import PlayerAnalysis, PlayerSummary
from .scenario import ScenarioCard


@dataclass
class ReportInfo:
    """Report metadata."""

    team_id: TeamId
    team_name: str
    games_analyzed: int
    opponent_winrate: Percentage
    average_kills: float
    average_deaths: float
    players: List[PlayerSummary]
    timeframe: Timeframe
    generated_at: str  # ISO 8601 timestamp


@dataclass
class OverviewAnalysis:
    """High-level overview of opponent."""

    randomness: RandomnessLevel
    randomness_score: NormalizedValue  # 0-1, higher = more chaotic
    strategic_insights: List[str]


@dataclass
class TeamAnalysisReport:
    """Complete team analysis report - main domain aggregate."""

    report_info: ReportInfo
    overview: OverviewAnalysis
    draft_plan: DraftPlan
    draft_tendencies: DraftTendencies
    stable_picks: List[StablePicksByRole]
    scenarios: List[ScenarioCard]
    player_analysis: List[PlayerAnalysis]
