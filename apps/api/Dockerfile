FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY archmind ./archmind
EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "archmind.main:app", "--host", "0.0.0.0", "--port", "8000"]
