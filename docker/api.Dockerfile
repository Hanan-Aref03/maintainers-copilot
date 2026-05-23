FROM node:20-alpine AS widget-builder

WORKDIR /src/widget

COPY widget/package*.json ./
RUN npm ci

COPY widget/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=10 \
    PIP_PROGRESS_BAR=off \
    PYTHONPATH=/app

WORKDIR /app

RUN pip install --no-cache-dir --retries 10 --timeout 300 \
    fastapi \
    uvicorn \
    sqlalchemy \
    psycopg2-binary \
    pgvector \
    passlib[bcrypt] \
    python-multipart \
    requests \
    google-generativeai \
    hvac \
    redis \
    numpy \
    rank-bm25 \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-grpc

COPY app /app/app
COPY data_pipeline /app/data_pipeline
COPY shared /app/shared
COPY migrations /app/migrations
COPY scripts /app/scripts
COPY --from=widget-builder /src/widget/dist /app/widget/dist

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

