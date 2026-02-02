"""Player domain entity."""

from dataclasses import dataclass, field
from typing import List

from ..value_objects.types import (
    ChampionId,
    NormalizedValue,
    Percentage,
    PlayerId,
    Role,
)


@dataclass
class ChampionPoolEntry:
    """Champion in a player's pool."""

    champion_id: ChampionId
    games_played: int
    winrate: Percentage
    is_comfort: bool


@dataclass
class PlayerTendencies:
    """Statistical tendencies for a player."""

    early_game_aggression: NormalizedValue
    teamfight_participation: NormalizedValue
    solo_kill_rate: NormalizedValue
    vision_score: NormalizedValue


@dataclass
class PlayerSummary:
    """Brief player information."""

    player_id: PlayerId
    nickname: str
    role: Role


@dataclass
class PlayerAnalysis:
    """Comprehensive player analysis."""

    player_id: PlayerId
    nickname: str
    role: Role
    entropy: NormalizedValue  # 0-1, higher = wider pool / less predictable
    champion_pool: List[ChampionPoolEntry] = field(default_factory=list)
    tendencies: PlayerTendencies | None = None
