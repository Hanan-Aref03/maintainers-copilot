FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY scripts/health_server.py /app/health_server.py

EXPOSE 8501

CMD ["python", "/app/health_server.py", "--port", "8501", "--name", "streamlit"]
