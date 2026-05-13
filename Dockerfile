# ── Base ──────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Системные зависимости одним слоем
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Dependencies ──────────────────────────────────────────────────────────────
FROM base AS deps

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Final ─────────────────────────────────────────────────────────────────────
FROM deps AS final

# Непривилегированный пользователь с фиксированным UID=1000
# (совпадает с владельцем примонтированных томов на хосте)
RUN groupadd -r -g 1000 appuser && useradd -r -u 1000 -g appuser appuser

COPY --chown=appuser:appuser . .

RUN mkdir -p /app/data /app/media /app/logs \
    && chown -R appuser:appuser /app/data /app/media /app/logs

USER appuser

# Без --reload в продакшне; ENV управляется docker-compose
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--no-access-log"]
