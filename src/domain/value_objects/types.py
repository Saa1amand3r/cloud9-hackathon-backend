"""Domain value objects and type aliases."""

from dataclasses import dataclass
from enum import Enum
from typing import NewType

# Type aliases for domain clarity
ChampionId = NewType("ChampionId", str)
PlayerId = NewType("PlayerId", str)
TeamId = NewType("TeamId", str)
Percentage = NewType("Percentage", float)  # 0-100
NormalizedValue = NewType("NormalizedValue", float)  # 0-1


class Role(str, Enum):
    """Player role/position in game."""

    TOP = "top"
    JUNGLE = "jungle"
    MID = "mid"
    ADC = "adc"
    SUPPORT = "support"


class RandomnessLevel(str, Enum):
    """Team unpredictability classification."""

    PREDICTABLE = "predictable"
    MODERATE = "moderate"
    CHAOTIC = "chaotic"


class DraftPriority(str, Enum):
    """Draft strategy priority."""

    FLEXIBILITY = "flexibility"
    COMFORT = "comfort"
    COUNTER = "counter"
    EARLY_POWER = "early_power"


class PunishAction(str, Enum):
    """Action type for punish strategy."""

    BAN = "ban"
    PICK = "pick"
    COUNTER = "counter"
    PLAYSTYLE = "playstyle"


@dataclass(frozen=True)
class Timeframe:
    """Analysis timeframe value object."""

    start_date: str  # ISO 8601 date
    end_date: str  # ISO 8601 date
    patch_version: str | None = None
