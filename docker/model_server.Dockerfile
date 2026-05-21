FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY scripts/health_server.py /app/health_server.py

EXPOSE 8001

CMD ["python", "/app/health_server.py", "--port", "8001", "--name", "model-server"]


