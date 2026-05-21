FROM node:20-alpine AS widget-builder

WORKDIR /src/widget

COPY widget/package*.json ./
RUN npm ci

COPY widget/ ./
RUN npm run build

FROM nginx:alpine

RUN apk add --no-cache wget

COPY --from=widget-builder /src/widget/dist /usr/share/nginx/html

EXPOSE 80
