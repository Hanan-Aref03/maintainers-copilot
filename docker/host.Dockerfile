FROM nginx:alpine

RUN apk add --no-cache wget

COPY demo/host/index.html /usr/share/nginx/html/index.html
COPY demo/host/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
