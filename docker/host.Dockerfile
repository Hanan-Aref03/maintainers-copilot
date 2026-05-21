FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY scripts/health_server.py /app/health_server.py

EXPOSE 80

CMD ["python", "/app/health_server.py", "--port", "80", "--name", "host"]


FROM nginx:alpine
COPY demo/host/index.html /usr/share/nginx/html/index.html
COPY demo/host/nginx.conf /etc/nginx/conf.d/default.conf
