FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    google-generativeai \
    numpy \
    scikit-learn \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-grpc

COPY model_server /app/model_server
COPY data_pipeline /app/data_pipeline
COPY shared /app/shared

EXPOSE 8001

CMD ["uvicorn", "model_server.app.main:app", "--host", "0.0.0.0", "--port", "8001"]

