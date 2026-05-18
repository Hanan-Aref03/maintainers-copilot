FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY scripts/health_server.py /app/health_server.py

EXPOSE 80

CMD ["python", "/app/health_server.py", "--port", "80", "--name", "widget"]
