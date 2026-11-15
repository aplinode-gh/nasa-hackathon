# Backend Service (FastAPI)

This folder contains the FastAPI backend for the project.

## Local setup

```bash
cd apps/backend
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` values, then run:

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

## Notes

- Database migrations are stored in `db/migrations/`.
- The service replaces the previous Next.js API routes with FastAPI endpoints.
- Feature modules for pest alerts, disease detection, and the profit/loss calculator are included.

## Applying migrations

Run each migration file in numeric order against the Neon/Postgres database:

```bash
psql "$DATABASE_URL_UNPOOLED" -f db/migrations/0018_profit_loss.sql
psql "$DATABASE_URL_UNPOOLED" -f db/migrations/0019_detect.sql
psql "$DATABASE_URL_UNPOOLED" -f db/migrations/0020_pest_alerts.sql
psql "$DATABASE_URL_UNPOOLED" -f db/migrations/0021_crop_recommendation_align.sql
psql "$DATABASE_URL_UNPOOLED" -f db/migrations/0022_pest_prediction.sql
```

`0018` creates `seasons`, `expenses`, and `projected_costs`; `0019` creates
`detect_scans`, `detect_chats`, and `detect_messages`; `0020` creates
`pest_alerts`; `0021` aligns the crop-recommendation tables with the varchar-id
crops catalogue and seeds crops/soil/rotation/price data; `0022` adds pest
predictions, incidence, treatments, price snapshots, and extends pest alerts.
Existing migrations must already be applied.

Additional environment variables used by these modules:

```bash
PEST_CRON_SECRET=      # protects POST /api/cron/pest-prediction
DETECT_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
HUGGINGFACE_API_KEY=   # optional PlantVillage inference
HUGGINGFACE_MODEL=linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification
```

Price scrapers remain an external ingestion job that posts to
`POST /api/prices/ingest`; the API validates and stores their rows.

## Advisor agents

`app/services/ai/` contains a small agent runtime (tools, handoffs, streaming
tool-call loop). The advisor is a triage agent that routes to seven specialists:

- Crop Advisor — diseases, pests, agronomy, fertilizer, livestock
- Crop Recommendation Advisor — what to plant, rotation planning
- Weather Advisor — forecasts, spray windows
- Farm Data Advisor — farms, records, profit/loss, recommendations
- Prices Advisor — mandi prices and sell/hold guidance
- Schemes Advisor — subsidies, Kissan Card, insurance
- Agronomist Handoff — expert escalation

Tools live in `app/services/advisor_tools.py` (17 tools) and cover farms,
records, soil-crop fit, weather, market prices, seasons, expenses, profit/loss,
crop candidates, knowledge base, and conversation memory. Input/output
guardrails are in `app/services/ai/guardrails.py`.

`app/services/app_control_tools.py` implements the app-control agent's 13 tools
(navigation, summaries, record CRUD with confirmation) and emits navigation
buttons/action cards over SSE.

The runtime uses OpenAI-compatible chat completions (`OPENAI_API_KEY`,
`OPENAI_BASE_URL`, `ADVISOR_MODEL`). Without a key the endpoints return a
service-unavailable response; deterministic fallbacks remain for detection.

## Scheduled jobs

- `POST /api/cron/predict-prices` — refresh 14-day price forecasts (`CRON_SECRET`)
- `POST /api/cron/pest-prediction` — score 7-day pest risk, store predictions,
  create alerts/notifications, and email when SMTP is configured (`PEST_CRON_SECRET`)

## Feature endpoints

- `GET/POST /api/profit-loss`, `GET/PATCH/DELETE /api/profit-loss/{id}`
- `GET/POST /api/profit-loss/{id}/expenses`, `PATCH/DELETE .../expenses/{expenseId}`
- `POST /api/profit-loss/{id}/projected-costs`, `/archive`, `/restore`
- `POST /api/detect` (multipart image), `GET /api/detect/history`, `GET /api/detect/image/{scanId}`
- `GET/POST /api/detect/chats`, `GET /api/detect/messages/{chatId}`, `POST /api/detect/chat`, `POST /api/detect/save`, `DELETE /api/detect/scans/{scanId}`
- `GET /api/pest/forecast`, `GET /api/pest/alerts`, `GET /api/pest/alerts/{id}`, `POST /api/pest/alerts/{id}/read`, `POST /api/pest/growth-stage`
- `POST /api/cron/pest-prediction`, `POST /api/cron/predict-prices`
- `GET/POST /api/advisor/conversations`, `POST /api/advisor/chat`
- `GET/POST /api/app-control/conversations`, `POST /api/app-control/chat`

Detection and the detect chat use `OPENAI_API_KEY` when available and fall back
to a deterministic local diagnosis/reply so the UI remains usable without
credentials. Pest forecasts use `OPENWEATHER_API_KEY` when available and fall
back to demo weather data.
