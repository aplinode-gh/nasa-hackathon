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
- The service is designed to replace the previous Next.js API routes with FastAPI endpoints.
- Feature modules for pest alerts, disease detection, and profit/loss calculator are intentionally excluded.
