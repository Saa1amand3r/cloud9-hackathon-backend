from typing import List

from core.domain.Player import Player


class Team:
    def __init__(self, team_id: int, name: str, wins:int, losses: int, avg_kills:float,
                 avg_deaths:float, members: List[Player]):
        self.team_id = team_id
        self.name = name
        self.wins = wins
        self.losses = losses
        self.avg_kills = avg_kills
        self.avg_deaths = avg_deaths
        self.members = members
    