ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20
FROM ${BUILD_FROM}

# Install uv and build dependencies for lxml
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libxml2-dev \
    libxslt-dev \
    python3-dev

# Set working directory
WORKDIR /app

# Copy dependency files and install (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY src/ ./src/

# Remove build dependencies to keep image small
RUN apk del gcc musl-dev python3-dev

EXPOSE 8080

CMD ["uv", "run", "--no-dev", "python", "-m", "src.main"]
