import json
from pathlib import Path

from scouting.grid_ingest import RawSeriesRecord
from scouting.normalize import normalize_records


def test_normalize_maps_team_and_opponent_by_id() -> None:
    fixture = Path("tests/fixtures/series_state_sample.json")
    data = json.loads(fixture.read_text(encoding="utf-8"))
    record = RawSeriesRecord(
        series_id="series1",
        start_time="2025-12-01T12:00:00Z",
        tournament={"id": "tour1", "name": "LCS Spring"},
        teams=[
            {"baseInfo": {"id": "teamA", "name": "Cloud9"}},
            {"baseInfo": {"id": "teamB", "name": "Team Liquid"}},
        ],
        series_state=data["seriesState"],
    )

    games = normalize_records([record], team_id="teamA", opponent_id="teamB")
    assert len(games) == 1
    g = games[0]
    assert g.team.team_id == "teamA"
    assert g.opponent.team_id == "teamB"
    assert g.result == "win"
    assert g.opponent.players[0].character == "Ornn"
