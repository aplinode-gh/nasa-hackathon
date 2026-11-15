# Model inference service for the Field Shift entry.
#
# This image contains only what the API needs at request time: the FastAPI app
# and the packaged model bundle (model_store/). Raw NASA POWER pulls, cleaned
# daily parquet and training matrices are deliberately excluded.
#
# Build from the repository root:
#   docker build -f apps/model-api/Dockerfile -t fieldshift-model-api apps/model-api
# Run:
#   docker run -p 8001:8001 fieldshift-model-api

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MODEL_STORE_DIR=/app/model_store \
    PORT=8001

# libgomp is required by the XGBoost binary.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first so source edits do not invalidate the layer cache.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY model_store ./model_store

# Fail the build rather than starting a service with no models.
RUN python -c "import os, pathlib; \
    d = pathlib.Path(os.environ['MODEL_STORE_DIR']); \
    models = list(d.glob('models/*_q*.json')); \
    assert models, 'model_store is empty - run scripts/package_models.py'; \
    print(f'{len(models)} model files present')"

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/health" || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
