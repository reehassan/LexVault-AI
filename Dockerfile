FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN pip install uv && uv sync --frozen

COPY . .

RUN useradd --uid 1000 --create-home appuser && chown -R appuser:appuser /app

USER appuser