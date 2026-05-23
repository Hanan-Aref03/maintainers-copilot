FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=10 \
    PIP_PROGRESS_BAR=off

WORKDIR /app

RUN pip install --upgrade pip && \
    pip install --retries 10 --timeout 300 alembic sqlalchemy psycopg2-binary pgvector

COPY migrations/alembic.ini /app/alembic.ini
COPY migrations /app/migrations
COPY app /app/app

CMD ["alembic", "upgrade", "head"]
