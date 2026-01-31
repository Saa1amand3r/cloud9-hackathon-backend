from scouting.normalize import GameRecord, TeamGameState, PlayerPerf
from scouting.randomness import compute_randomness


def _game(idx: int, champ: str) -> GameRecord:
    team = TeamGameState(team_id="teamA", won=True, score=1, kills=10, deaths=5, players=[])
    opp = TeamGameState(
        team_id="teamB",
        won=False,
        score=0,
        kills=5,
        deaths=10,
        players=[
            PlayerPerf(
                player_id=f"p{idx}",
                name=None,
                role="top",
                character=champ,
                kills=1,
                deaths=2,
            )
        ],
    )
    return GameRecord(
        series_id="s",
        game_number=idx,
        start_time=f"2025-12-0{idx}T12:00:00Z",
        tournament={},
        team=team,
        opponent=opp,
        result="win",
    )


def test_randomness_score_in_range() -> None:
    games = [_game(1, "Gnar"), _game(2, "Ornn"), _game(3, "Gnar")]
    r = compute_randomness(games)
    assert 0.0 <= r["score"] <= 100.0
    assert 0.0 <= r["draft_entropy"] <= 1.0
