# Automated Scouting Report Generator (Python MVP)

This project generates a structured scouting report (JSON or text) from GRID data.

## Quickstart

```bash
export GRID_API_KEY="..."
python -m scouting.cli --title lol --team "Cloud9" --opponent "Team Liquid" --window-days 180 \
  --tournament-filter "LCS" \
  --output report.json --output-format json
```

Optional flags:
- `--save-raw raw.json` saves raw series + seriesState data
- `--save-normalized games.json` saves normalized games
- `--cache` enables on-disk cache (`.cache/grid` by default)
- `--from-raw raw.json` skips GRID requests
- `--team-id` / `--opponent-id` overrides team IDs

Role heuristics:
- `scouting/role_map.json` provides a default champion→role mapping.
- Set `SCOUTING_ROLE_MAP=/path/to/role_map.json` to override it.

## Output

The JSON report includes:
- `meta`, `data_coverage`, `opponent_overview`
- `per_player`, `draft_tendencies`, `scenarios`, `counters`, `randomness`
- `missing_data` flags

## Tests

```bash
pytest -q
```

## Notes
- Team mapping uses team IDs (no team0/team1 assumptions).
- AllSeries pagination is implemented to avoid missing series.
- SeriesState queries fall back to a basic query if extended fields aren’t supported.


## Generate a pdf report

```bash
python -m scouting.report_pdf --input report.json --output report.pdf   
```