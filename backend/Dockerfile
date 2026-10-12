FROM python:3.12-slim

# Install system dependencies for OpenCV, InsightFace and image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution and environment management
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /uvx /bin/

WORKDIR /app

# Copy dependency specifications
COPY pyproject.toml uv.lock README.md ./

# Install production dependencies
RUN uv sync --frozen --no-dev --link-mode=copy

# Copy backend source code and migrations
COPY src ./src
COPY scripts ./scripts
COPY sql ./sql
COPY yolo26n.pt ./
COPY data/weights ./data/weights

ENV PATH="/app/.venv/bin:$PATH"
ENV DETECT_AI_HOST="0.0.0.0"
ENV DETECT_AI_PORT="8000"

EXPOSE 8000

CMD ["uvicorn", "detect_ai.main:app", "--host", "0.0.0.0", "--port", "8000"]
