from core.domain.Character import Character


class CharacterPick:
    def __init__(self, character:Character, weight:float, share:float):
        self.character = character
        self.weight = weight
        self.share = share