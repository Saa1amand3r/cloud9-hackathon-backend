# Cloudy Poro Backend

Professional esports scouting and analysis API for League of Legends teams. Built with hexagonal architecture for maintainability and extensibility.

## Architecture

This project follows **hexagonal (ports & adapters) architecture** for clean separation of concerns:

```
src/
├── domain/                     # Core business entities
│   ├── entities/              # Domain objects (Player, Draft, Scenario, Report)
│   └── value_objects/         # Value types (Role, ChampionId, Percentage)
├── application/               # Use cases and business logic
│   ├── ports/                # Interfaces (ScoutingDataPort, ReportBuilderPort)
│   └── use_cases/            # Business operations (GenerateReportUseCase)
├── infrastructure/            # External adapters
│   └── adapters/             # GRID API adapter, future DB adapters
├── api/                       # HTTP/WebSocket layer
│   ├── rest/                 # REST endpoints
│   ├── websocket/            # WebSocket handlers
│   └── transformers/         # Response transformers
└── main.py                   # FastAPI application

scouting/                      # Core scouting analysis engine (unchanged)
```

## Quick Start

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### 2. Set Up Environment

Create a `.env` file:

```bash
# Required: GRID API key for esports data
GRID_API_KEY=your_api_key_here

# Optional: Enable caching
GRID_CACHE=true
GRID_CACHE_DIR=.cache/grid
```

### 3. Run the Server

```bash
# Using the new architecture
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Or using legacy endpoint (deprecated)
uvicorn main_legacy:app --reload --host 0.0.0.0 --port 8000
```

### 4. View API Documentation

Open http://localhost:8000/docs for interactive Swagger documentation.

---

## API Endpoints

### Health Check

```http
GET /health
```

Response:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "api_key_configured": true
}
```

### Get Team Analysis (REST)

```http
GET /api/teams/{team_id}/analysis?ourTeam=Cloud9
```

Query Parameters:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `team_id` | string | Yes | Team name to analyze (opponent) |
| `ourTeam` | string | No | Your team name (default: Cloud9) |
| `startDate` | string | No | Analysis start date (ISO 8601) |
| `endDate` | string | No | Analysis end date (ISO 8601) |
| `lastNGames` | int | No | Analyze only last N games |

Example:
```bash
curl "http://localhost:8000/api/teams/T1/analysis?ourTeam=Cloud9"
```

### Generate Analysis (POST)

```http
POST /api/analysis/generate
Content-Type: application/json

{
  "teamName": "Cloud9",
  "opponentName": "T1",
  "windowDays": 180,
  "tournamentFilter": "LCK"
}
```

### WebSocket Report Generation

Connect to `ws://localhost:8000/ws/report` for real-time progress updates.

Send:
```json
{
  "action": "generate",
  "teamName": "T1",
  "opponentName": "T1",
  "ourTeam": "Cloud9",
  "windowDays": 180
}
```

Receive progress updates:
```json
{
  "status": "processing",
  "progress": 45,
  "message": "Analyzing draft patterns..."
}
```

Final response includes the complete report:
```json
{
  "status": "completed",
  "progress": 100,
  "message": "Report ready!",
  "report": { ... }
}
```

---

## Response Format (Frontend Compatible)

The API returns a `TeamAnalysisReport` matching the frontend's expected format:

```typescript
interface TeamAnalysisReport {
  reportInfo: {
    teamId: string;
    teamName: string;
    gamesAnalyzed: number;
    opponentWinrate: number;      // 0-100
    averageKills: number;
    averageDeaths: number;
    players: PlayerSummary[];
    timeframe: TimeframeInfo;
    generatedAt: string;          // ISO 8601
  };
  overview: {
    randomness: 'predictable' | 'moderate' | 'chaotic';
    randomnessScore: number;      // 0-1
    strategicInsights: string[];
  };
  draftPlan: {
    banPlan: string[];            // Champion IDs
    draftPriority: 'flexibility' | 'comfort' | 'counter' | 'early_power';
    counterPicks: CounterPickStrategy[];
    strategicNotes: string[];
  };
  draftTendencies: {
    priorityPicks: ChampionPriority[];
  };
  stablePicks: StablePicksByRole[];
  scenarios: ScenarioCard[];
  playerAnalysis: PlayerAnalysis[];
}
```

See `src/domain/entities/` for complete type definitions.

---

## Development

### Project Structure

```
backend/
├── src/                   # New hexagonal architecture
├── scouting/             # Core analysis engine
├── tests/                # Test suite
├── main_legacy.py        # Legacy API (deprecated)
├── pyproject.toml        # Dependencies
└── README.md
```

### Running Tests

```bash
pytest -q
```

### Adding New Features

1. **Domain Layer**: Add entities/value objects in `src/domain/`
2. **Application Layer**: Create use case in `src/application/use_cases/`
3. **Infrastructure**: Add adapters in `src/infrastructure/adapters/`
4. **API**: Add endpoints in `src/api/rest/routes.py`

### Code Quality

- Follow Python type hints
- Use dataclasses for domain entities
- Keep adapters thin - business logic in use cases
- Write tests for new functionality

---

## Frontend Integration

### Configuration

The frontend should be configured with:

```env
# .env file in frontend
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws/report
VITE_USE_MOCK=false
VITE_OUR_TEAM=Cloud9
```

### CORS

The backend allows requests from:
- `http://localhost:5173` (Vite dev server)
- `http://localhost:3000`
- `https://cloudyporo.com` (production)

---

## CLI Usage

Generate reports via command line:

```bash
export GRID_API_KEY="..."
python -m scouting.cli \
  --title lol \
  --team "Cloud9" \
  --opponent "Team Liquid" \
  --window-days 180 \
  --tournament-filter "LCS" \
  --output report.json
```

### CLI Flags

| Flag | Description |
|------|-------------|
| `--title` | Game title (lol) |
| `--team` | Your team name |
| `--opponent` | Opponent team name |
| `--window-days` | Days to analyze (default: 180) |
| `--tournament-filter` | Filter by tournament name |
| `--output` | Output file path |
| `--cache` | Enable API response caching |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GRID_API_KEY` | Yes | API key for GRID esports data |
| `GRID_CACHE` | No | Enable caching ("true" or "1") |
| `GRID_CACHE_DIR` | No | Cache directory (default: `.cache/grid`) |
| `SCOUTING_ROLE_MAP` | No | Path to custom role_map.json |

---

## Error Handling

The API returns structured errors:

```json
{
  "error": {
    "code": "TEAM_NOT_FOUND",
    "message": "Team not found or no data available",
    "details": { "teamId": "unknown-team" }
  }
}
```

| Code | Status | Description |
|------|--------|-------------|
| `TEAM_NOT_FOUND` | 404 | No data for the specified team |
| `NO_DATA` | 404 | No matches in the time window |
| `INVALID_REQUEST` | 400 | Invalid request parameters |
| `INTERNAL_ERROR` | 500 | Server error |

---

## Migration from Legacy API

If migrating from the old `/api/scouting/report` endpoint:

| Old Endpoint | New Endpoint |
|--------------|--------------|
| `POST /api/scouting/report` | `POST /api/analysis/generate` |
| `GET /api/scouting/report?team=X&opponent=Y` | `GET /api/teams/{opponent}/analysis?ourTeam=X` |

The new API returns data in the frontend-compatible format directly.

---

## License

MIT
