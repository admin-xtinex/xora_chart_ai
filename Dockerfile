FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY data/ ./data/
COPY config/ ./config/
COPY chart_reference/ ./chart_reference/

RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1
ENV PORT=8030

EXPOSE 8030

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import socket; s=socket.create_connection(('127.0.0.1',8030),5); s.close()" || exit 1

CMD ["uvicorn", "xora_chart.main:app", "--host", "0.0.0.0", "--port", "8030"]
