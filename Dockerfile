FROM python:3.12-slim

WORKDIR /app

# System deps (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better layer caching)
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY data/ ./data/
COPY chart_reference/ ./chart_reference/

RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1
ENV PORT=8030

EXPOSE 8030

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8030/api/v1/health || exit 1

CMD ["uvicorn", "xora_chart.main:app", "--host", "0.0.0.0", "--port", "8030"]
