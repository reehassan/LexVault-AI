FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

COPY . .

CMD [ "python", "manage.py", "runserver", "0.0.0.0:8000" ]