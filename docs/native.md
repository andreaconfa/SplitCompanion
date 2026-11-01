# Build e avvio dai sorgenti

Il sorgente della stessa versione è incluso nella release e scaricabile da
`/api/source` sulle immagini ufficiali. L’app nativa iOS non è necessaria.

## Costruire il container

Dalla cartella dei sorgenti:

```sh
docker build -t splitcompanion:1.2.0-rc.1 .
cp .env.example .env
sudo install -d -m 0700 -o 10001 -g 10001 data backups
docker compose up -d
```

Per scegliere esplicitamente l’architettura: aggiungi `--platform linux/amd64`
oppure `--platform linux/arm64`. Node compila il web in uno stadio separato;
l’immagine finale contiene Python, web compilato e il sorgente corrispondente.
Al primo avvio non vengono scaricate dipendenze.

## Avvio nativo Linux

Requisiti: Python 3.13, Node 22 con npm, SQLite su disco locale. Servono rete e
strumenti di compilazione eventualmente richiesti dai pacchetti durante la build.
Usa un account dedicato senza privilegi e un singolo processo. Non usare
`uvicorn --workers` o `--reload` per l’istanza reale.

Dalla cartella dei sorgenti:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock
(cd frontend && npm ci --no-audit --no-fund && npm run build)
node scripts/collect-licenses.mjs frontend/node_modules frontend/dist/third-party-notices.txt
mkdir -m 700 data backups
python3.13 scripts/make-source-archive.py --output /tmp/splitcompanion-source.tar.gz
# Per un percorso durevole, sposta l’archivio nella directory privata dell’istanza.
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

`app.container` è anche il launcher nativo: verifica permessi e asset, blocca una
seconda istanza sullo stesso volume, controlla lo schema, esegue le migrazioni e
avvia il server. In un altro terminale con la stessa configurazione:

```sh
.venv/bin/python -m app.cli setup-token
```

Per l’avvio automatico configura il tuo supervisor/systemd con queste variabili,
l’utente dedicato, la directory di lavoro dei sorgenti e l’eseguibile della venv.
Non creare un secondo scheduler. Consulta [proxy](proxy.md) e [operazioni](operations.md).

## Sviluppo e test

```sh
.venv/bin/python -m pip install -r backend/requirements-dev.lock
.venv/bin/python -m pytest backend/tests -q
.venv/bin/python -m ruff check backend/app backend/tests
(cd frontend && npm ci && npm test && npm run build)
```

I test creano dati sintetici: non configurarli sul database reale. Per il frontend
in sviluppo, `npm run dev` inoltra `/api` a un backend locale sulla porta 8000.

Quando modifichi il sorgente, rigenera l’archivio distribuito: AGPL richiede il
sorgente corrispondente, non il codice di una versione precedente.
