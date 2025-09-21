# Pitlane Sim-Gate Orchestrator — container image
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY examples ./examples

RUN pip install --upgrade pip && pip install -e .

# Default work dir for outputs
RUN mkdir -p /app/work
VOLUME ["/app/work"]

ENTRYPOINT ["simgate"]
CMD ["--help"]
