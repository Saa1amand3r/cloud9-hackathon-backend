from scouting.matchups import build_matchup_table
from scouting.normalize import GameRecord, TeamGameState, PlayerPerf


def _game(our_win: bool, our_champ: str, their_champ: str) -> GameRecord:
    team = TeamGameState(
        team_id="teamA",
        won=our_win,
        score=1 if our_win else 0,
        kills=10,
        deaths=5,
        players=[
            PlayerPerf(
                player_id="p1",
                name=None,
                role="top",
                character=our_champ,
                kills=3,
                deaths=1,
            )
        ],
    )
    opp = TeamGameState(
        team_id="teamB",
        won=not our_win,
        score=0 if our_win else 1,
        kills=5,
        deaths=10,
        players=[
            PlayerPerf(
                player_id="p2",
                name=None,
                role="top",
                character=their_champ,
                kills=1,
                deaths=3,
            )
        ],
    )
    return GameRecord(
        series_id="s",
        game_number=1,
        start_time="2025-12-01T12:00:00Z",
        tournament={},
        team=team,
        opponent=opp,
        result="win" if our_win else "loss",
    )


def test_matchup_posterior_winrate() -> None:
    games = [_game(True, "Gnar", "Ornn"), _game(False, "Gnar", "Ornn")]
    table = build_matchup_table(games)
    stats = table[("top", "Gnar", "Ornn")]
    winrate = stats.posterior_winrate(alpha=2, beta=2)
    assert 0.0 < winrate < 1.0
    assert stats.games == 2
