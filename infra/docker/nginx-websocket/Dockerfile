# syntax=docker/dockerfile:1
# Optional edge nginx for WebSocket-friendly load balancing when not using Ingress.
FROM nginx:1.27-alpine
COPY infra/docker/nginx-websocket/default.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
HEALTHCHECK CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
