FROM node:24-alpine AS frontend
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
ARG VITE_APP_ENV=prod
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY mcp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY mcp/app_logging.py mcp/server.py mcp/web_app.py mcp/access.py mcp/auth_routes.py mcp/auth_store.py mcp/mailer.py mcp/request_guard.py ./
COPY --from=frontend /build/dist ./static
RUN groupadd --gid 10001 search && useradd --uid 10001 --gid search --no-create-home search \
    && mkdir -p /app/.local/logs && chown -R 10001:10001 /app/.local
ENV PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
CMD ["python", "web_app.py"]
