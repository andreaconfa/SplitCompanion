# syntax=docker/dockerfile:1.7
FROM --platform=$BUILDPLATFORM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
COPY scripts/collect-licenses.mjs /build/collect-licenses.mjs
RUN npm run build && node /build/collect-licenses.mjs node_modules dist/third-party-notices.txt

FROM python:3.13-slim-trixie AS wheels
WORKDIR /build
COPY backend/requirements.lock ./
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.lock

FROM python:3.13-slim-trixie AS source
WORKDIR /source
COPY . .
RUN python scripts/make-source-archive.py --root /source --output /source.tar.gz

FROM python:3.13-slim-trixie AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SPLIT_COMPANION_SOURCE_ARCHIVE=/app/source.tar.gz \
    SPLIT_COMPANION_DB=/data/split-companion.db \
    SPLIT_COMPANION_FRONTEND_DIR=/app/frontend/dist \
    SPLIT_COMPANION_BACKUP_DIR=/backups \
    SPLIT_COMPANION_BACKUPS_ENABLED=true \
    SPLIT_COMPANION_SCHEDULER=true \
    SPLIT_COMPANION_MFA_REQUIRED=true \
    SPLIT_COMPANION_ALLOW_HTTP=false \
    SPLIT_COMPANION_TRUSTED_PROXY_IPS=""
RUN groupadd --gid 10001 splitcompanion \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin splitcompanion \
    && mkdir -p /data /backups /app/backend /app/frontend/dist \
    && chown 10001:10001 /data /backups
COPY backend/requirements.lock /tmp/requirements.lock
RUN --mount=from=wheels,source=/wheels,target=/wheels \
    python -m pip install --no-cache-dir --no-index --find-links=/wheels -r /tmp/requirements.lock \
    && python -m pip check \
    && python -m pip uninstall -y pip setuptools \
    && rm -rf /usr/local/lib/python3.13/ensurepip \
    && rm /tmp/requirements.lock
COPY --from=source /source.tar.gz /app/source.tar.gz
COPY LICENSE NOTICE /app/
COPY backend/app/ /app/backend/app/
COPY backend/migrations/ /app/backend/migrations/
COPY backend/alembic.ini /app/backend/alembic.ini
COPY --from=frontend /build/frontend/dist/ /app/frontend/dist/
WORKDIR /app/backend
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ready', timeout=4).read()"]
CMD ["python", "-m", "app.container"]

# Supervisor supplies a root-owned /data/options.json; the adapter drops to UID 10001.
FROM runtime AS homeassistant
ENV PYTHONPATH=/app/backend
ARG BUILD_VERSION
ARG BUILD_ARCH
LABEL io.hass.version=$BUILD_VERSION io.hass.type="app" io.hass.arch=$BUILD_ARCH
USER 0:0
COPY homeassistant/splitcompanion/run.py /app/homeassistant.py
CMD ["python", "/app/homeassistant.py"]

# Default docker build remains the standalone, non-root server.
FROM runtime AS standalone
