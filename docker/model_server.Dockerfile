FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN pip install --upgrade pip && \
    pip install fastapi uvicorn google-generativeai

COPY model_server /app/model_server

EXPOSE 8001

CMD ["uvicorn", "model_server.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
