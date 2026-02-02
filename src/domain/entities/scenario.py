"""Scenario/playstyle domain entities."""

from dataclasses import dataclass, field
from typing import Dict, List

from ..value_objects.types import ChampionId, NormalizedValue, Percentage, PunishAction


@dataclass
class ScenarioStats:
    """Statistics describing a scenario/playstyle."""

    teamfightiness: NormalizedValue
    early_aggression: NormalizedValue
    draft_volatility: NormalizedValue
    macro: NormalizedValue


@dataclass
class PunishStrategy:
    """Strategy to punish/counter a scenario."""

    action: PunishAction
    targets: List[ChampionId]
    description: str


@dataclass
class ScenarioCard:
    """Game scenario/playstyle cluster."""

    scenario_id: str
    name: str
    description: str | None
    likelihood: Percentage
    winrate: Percentage
    stats: ScenarioStats
    punish_strategy: PunishStrategy
