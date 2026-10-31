# Tax Assist AI — backend image (Sprint 3 Wave F, design §3).
#
# Runtime contract (documented, load-bearing):
#   - ONE uvicorn worker. The append-only audit stream serializes writes
#     through a process-wide lock (audit_logger.py) and the SQLite store
#     relies on WAL + single-process access (db.py). Scaling horizontally
#     by bumping --workers would corrupt both invariants — scale by adding
#     containers behind the reverse proxy instead.
#   - Binds 0.0.0.0 INSIDE the container only; docker-compose publishes it
#     on 127.0.0.1 of the host and TLS terminates at the reverse proxy.
#   - The /health endpoint is public and rate-limit exempt, so the probe
#     below is safe (200 ok / 503 degraded -> unhealthy).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=prod

WORKDIR /app

# Dependencies first: the pinned requirements layer caches independently
# of the application code.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code.
COPY . .

# State + log directories the volumes mount onto. Created up-front and
# chowned so the named volumes inherit uid 10001 ownership on first use.
RUN mkdir -p /app/data /app/logs \
    && addgroup --gid 10001 app \
    && adduser --uid 10001 --ingroup app --disabled-password --gecos "" app \
    && chown -R app:app /app/data /app/logs

USER 10001:10001

EXPOSE 8000

# HEALTHCHECK via stdlib urllib only (no curl/wget in the slim image).
# A 503 (degraded db/audit check) or a connection failure makes the
# container unhealthy — exactly what the orchestrator should see.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]

# Single worker = documented correctness requirement (see header).
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
