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
```

`0018` creates `seasons`, `expenses`, and `projected_costs`; `0019` creates
`detect_scans`, `detect_chats`, and `detect_messages`; `0020` creates
`pest_alerts`. Existing migrations must already be applied.

## Feature endpoints

- `GET/POST /api/profit-loss`, `GET/PATCH/DELETE /api/profit-loss/{id}`
- `GET/POST /api/profit-loss/{id}/expenses`, `PATCH/DELETE .../expenses/{expenseId}`
- `POST /api/profit-loss/{id}/projected-costs`, `/archive`, `/restore`
- `POST /api/detect` (multipart image), `GET /api/detect/history`, `GET /api/detect/image/{scanId}`
- `GET/POST /api/detect/chats`, `GET /api/detect/messages/{chatId}`, `POST /api/detect/chat`, `POST /api/detect/save`, `DELETE /api/detect/scans/{scanId}`
- `GET /api/pest/forecast`, `GET /api/pest/alerts`, `GET /api/pest/alerts/{id}`, `POST /api/pest/alerts/{id}/read`, `POST /api/pest/growth-stage`

Detection and the detect chat use `OPENAI_API_KEY` when available and fall back
to a deterministic local diagnosis/reply so the UI remains usable without
credentials. Pest forecasts use `OPENWEATHER_API_KEY` when available and fall
back to demo weather data.
