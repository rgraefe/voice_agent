FROM node:22-bookworm-slim AS frontend
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS api
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY voice ./voice
RUN pip install --no-cache-dir . && useradd --create-home --uid 10001 founder && mkdir -p /app/.local && chown founder:founder /app/.local
COPY --from=frontend /ui/dist ./frontend/dist
USER founder
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
