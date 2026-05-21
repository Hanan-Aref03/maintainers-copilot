FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN pip install --no-cache-dir \
    streamlit \
    requests

COPY chatbot_streamlit /app/chatbot_streamlit
COPY shared /app/shared

EXPOSE 8501

CMD ["streamlit", "run", "chatbot_streamlit/app.py", "--server.address", "0.0.0.0", "--server.port", "8501", "--browser.gatherUsageStats", "false"]

