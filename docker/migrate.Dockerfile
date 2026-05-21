FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN pip install --upgrade pip && \
    pip install alembic sqlalchemy psycopg2-binary pgvector

COPY migrations/alembic.ini /app/alembic.ini
COPY migrations /app/migrations
COPY app /app/app

CMD ["alembic", "upgrade", "head"]
