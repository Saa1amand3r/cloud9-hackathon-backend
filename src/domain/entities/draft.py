"""Draft-related domain entities."""

from dataclasses import dataclass, field
from typing import List

from ..value_objects.types import ChampionId, DraftPriority, Percentage, Role


@dataclass
class CounterPickStrategy:
    """Counter pick recommendation."""

    target_champion: ChampionId
    suggested_counters: List[ChampionId]


@dataclass
class DraftPlan:
    """Strategic draft recommendations."""

    ban_plan: List[ChampionId]
    draft_priority: DraftPriority
    counter_picks: List[CounterPickStrategy] = field(default_factory=list)
    strategic_notes: List[str] = field(default_factory=list)


@dataclass
class ChampionPriority:
    """Champion draft priority statistics."""

    champion_id: ChampionId
    pick_rate: Percentage
    ban_rate: Percentage
    priority: int  # 1 = highest priority


@dataclass
class DraftTendencies:
    """Team draft tendencies."""

    priority_picks: List[ChampionPriority]


@dataclass
class StablePick:
    """Stable/consistent champion pick."""

    champion_id: ChampionId
    role: Role
    games_played: int
    winrate: Percentage
    kda: float
    is_signature_pick: bool


@dataclass
class StablePicksByRole:
    """Stable picks grouped by role."""

    role: Role
    picks: List[StablePick]
