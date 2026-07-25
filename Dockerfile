FROM python:3.14-slim

WORKDIR /app

# libmagic1 is required by python-magic (apps/documents/services/validation.py)
# for real MIME-type sniffing on uploaded files. Without it, any import of
# validation.py fails at container startup with "failed to find libmagic".
# Do not remove this even though nothing in pyproject.toml references it —
# it's a system-level C library, not a Python package.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN pip install uv && uv sync --frozen

COPY . .

RUN useradd --uid 1000 --create-home appuser && chown -R appuser:appuser /app

USER appuser
