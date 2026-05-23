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
    streamlit \
    requests

COPY chatbot_streamlit /app/chatbot_streamlit
COPY shared /app/shared

EXPOSE 8501

CMD ["streamlit", "run", "chatbot_streamlit/app.py", "--server.address", "0.0.0.0", "--server.port", "8501", "--browser.gatherUsageStats", "false"]

