FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.24 /uv /uvx /bin/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY collector ./collector
RUN uv sync --locked --no-dev && useradd --uid 10001 --create-home collector
ENV PATH="/app/.venv/bin:$PATH"
USER collector
ENTRYPOINT ["chess-collector"]
CMD ["run"]
