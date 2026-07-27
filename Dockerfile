FROM python:3.14-slim

WORKDIR /app

# Required by python-magic
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Tell uv NOT to create /app/.venv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Make Python/Celery use that environment
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml uv.lock ./

RUN pip install uv \
    && uv sync --frozen

RUN useradd --uid 1000 --create-home appuser

COPY --chown=appuser:appuser . .

USER appuser