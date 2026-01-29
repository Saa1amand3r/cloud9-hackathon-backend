from typing import List

from core.domain.CharacterPick import CharacterPick


class Player:
    def __init__(self, player_id: int, nickname: str, comfortable_picks: List[CharacterPick]):
        self.player_id = player_id
        self.nickname = nickname
        self.comfortable_picks = comfortable_picks