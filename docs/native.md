# Build from source and run natively

The corresponding source is included in each release and is available at
`/api/source` in official container builds. The native iOS app is not required.

## Get the source

Download the corresponding source archive from the [release](https://github.com/andreaconfa/SplitCompanion/releases), or clone the release tag:

```sh
git clone --branch v1.2.0-rc.4 --single-branch https://github.com/andreaconfa/SplitCompanion.git
cd SplitCompanion
```

While the repository is private, access requires permission from its owner.

## Build the container on Linux

From the source directory:

```sh
docker build --platform linux/amd64 -t splitcompanion:1.2.0-rc.4 .
cp .env.example .env
sed -i 's|^SPLIT_COMPANION_IMAGE=.*|SPLIT_COMPANION_IMAGE=splitcompanion:1.2.0-rc.4|' .env
sudo install -d -m 0700 -o 10001 -g 10001 data backups
docker compose up -d
docker compose exec app python -m app.cli setup-token
```

The distributed container targets **Linux amd64 (x86-64)** only. Node builds the web app in a separate stage. The runtime
image contains Python, the compiled web app and corresponding source; it does not
download dependencies or compile code at startup.

## Run natively on Linux

Requirements: Python 3.13, Node 22 with npm, and SQLite on local storage. Network
access and any compiler tools required by dependencies are needed during the build.
Use a dedicated unprivileged account and a single process. Do not run the live
instance with `uvicorn --workers` or `--reload`.

From the source directory:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock
(cd frontend && npm ci --no-audit --no-fund && npm run build)
node scripts/collect-licenses.mjs frontend/node_modules frontend/dist/third-party-notices.txt
mkdir -m 700 data backups
python3.13 scripts/make-source-archive.py --output /tmp/splitcompanion-source.tar.gz
mv /tmp/splitcompanion-source.tar.gz data/source.tar.gz
export SPLIT_COMPANION_DB="$PWD/data/split-companion.db"
export SPLIT_COMPANION_BACKUP_DIR="$PWD/backups"
export SPLIT_COMPANION_SOURCE_ARCHIVE="$PWD/data/source.tar.gz"
export SPLIT_COMPANION_FRONTEND_DIR="$PWD/frontend/dist"
export SPLIT_COMPANION_HOST=127.0.0.1
export SPLIT_COMPANION_ALLOW_HTTP=true
export SPLIT_COMPANION_MFA_REQUIRED=true
export SPLIT_COMPANION_BACKUPS_ENABLED=true
export SPLIT_COMPANION_PUSH_ENABLED=false
export SPLIT_COMPANION_TIMEZONE=UTC
export PYTHONPATH="$PWD/backend"
.venv/bin/python -m app.container
```

`app.container` is also the native launcher: it checks directories and web assets,
locks the instance, validates the schema, runs migrations and starts the server.
In another terminal with the same environment settings, generate the setup code:

```sh
.venv/bin/python -m app.cli setup-token
```

For automatic startup, configure your own supervisor/systemd service with these
environment variables, the dedicated user, the source working directory and the
virtual environment's Python executable. Do not start another scheduler.
See [external HTTPS](proxy.md) and [operations](operations.md).

## Development and tests

```sh
.venv/bin/python -m pip install -r backend/requirements-dev.lock
.venv/bin/python -m pytest backend/tests -q
.venv/bin/python -m ruff check backend/app backend/tests
(cd frontend && npm ci && npm test && npm run build)
```

Tests create synthetic data. Never point them at a live database. For frontend
development, `npm run dev` forwards `/api` to a local backend on port 8000.

When modifying the application, regenerate its distributed source archive.
AGPL requires corresponding source, not source from a different version.
