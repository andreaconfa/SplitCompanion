# Configuration

Docker Compose reads `.env` next to `compose.yaml`. Never publish that file.
The example contains no credentials. On first initialization, the application
generates an instance secret and stores it in `data/secret.key`.

| Compose variable | Default | Purpose |
| --- | --- | --- |
| `SPLIT_COMPANION_IMAGE` | `ghcr.io/andreaconfa/splitcompanion:1.2.1-rc.2` | Official image; pin a release version or digest |
| `SPLIT_COMPANION_DATA_DIR` | `./data` | Existing persistent host directory, owned by UID/GID 10001 |
| `SPLIT_COMPANION_BACKUP_DIR` | `./backups` | Existing host backup directory, owned by UID/GID 10001 |
| `SPLIT_COMPANION_BIND` | `127.0.0.1` | Host interface on which to publish the port |
| `SPLIT_COMPANION_PORT` | `8000` | Host port; the container always listens on port 8000 |
| `SPLIT_COMPANION_TIMEZONE` | `UTC` | IANA timezone for recurring charges and backups, e.g. `Europe/London` |
| `SPLIT_COMPANION_MFA_REQUIRED` | `true` | Require two-factor authentication |
| `SPLIT_COMPANION_ALLOW_HTTP` | `true` | Explicitly allow local HTTP; disable for external HTTPS access |
| `SPLIT_COMPANION_PUBLIC_ORIGIN` | empty | Exact HTTPS origin served by your external proxy |
| `SPLIT_COMPANION_TRUSTED_PROXY_IPS` | empty | Only the IP addresses/CIDRs of trusted proxies |
| `SPLIT_COMPANION_PUSH_ENABLED` | `false` | Enable optional web push delivery |
| `SPLIT_COMPANION_PUSH_VAPID_SUBJECT` | empty | Operator-controlled `mailto:` contact or HTTPS URL |
| `SPLIT_COMPANION_BACKUP_HOUR` | `3` | Daily backup hour in the configured timezone, from 0 to 23 |
| `SPLIT_COMPANION_BACKUP_RETENTION` | `14` | Number of daily backups to keep |

The supplied Compose configuration enables the scheduler and backups. For a test
instance, use an override that disables the scheduler and push, with different
data and backup directories. Never use production data for tests.

## Secrets and advanced settings

The backend accepts `SPLIT_COMPANION_SECRET_KEY` or
`SPLIT_COMPANION_SECRET_KEY_FILE`, never both. For an externally managed secret,
create a Compose override, mount the file read-only and make it readable by UID
10001. The automatically generated persistent secret is sufficient for most installs.
With an existing database, a missing original secret stops startup rather than
silently generating a replacement.

For a native installation, `DB`, `BACKUP_DIR`, `SOURCE_ARCHIVE` and `FRONTEND_DIR`
(with the `SPLIT_COMPANION_` prefix) refer to Linux filesystem paths.
`SESSION_HOURS` controls session duration (default 168, allowed range 1–8760).
The full settings model is in `backend/app/config.py`.

## Storage requirements

Use Docker Engine on Linux with a local filesystem that supports SQLite WAL locking.
Keep one application replica and one worker per database. NFS/SMB storage is not
supported. Test a full restore on your chosen storage before relying on backups.

## Troubleshooting

- **Permission denied:** ensure only the dedicated data/backup directories are
  owned by and writable to UID/GID 10001. Do not loosen global permissions.
- **Host rejected or HTTPS required:** check the forwarded host, scheme, public
  origin and the proxy's source IP as seen by the container.
- **Invalid setup code:** generate a new code in this instance and use it within
  30 minutes. Setup closes permanently after the first administrator is created.
- **PWA or notifications unavailable:** check trusted HTTPS, Home Screen installation
  and device permissions. An HTTP address on a private network is not sufficient.
- **Database busy:** check for a second instance or worker on the same database.
  Reload and inspect transaction history before repeating financial operations.
- **Newer database schema:** use a compatible image or a verified restore. Do not
  delete the database to bypass the check.

## Language and default currency

The web/PWA starts in English. Choose **English** or **Italiano** under **Settings →
Appearance → Language**. The preference stays in that browser; the native iOS
companion has its own setting. User-entered names, descriptions and imported data
are never translated. Date and number formatting follow the interface language;
the server timezone continues to control recurring charges and backup scheduling.

Administrators choose the default currency under **Settings → Administration** in the web app
(**Server administration** in the native iOS app).
The initial default is EUR. Supported defaults use two decimal places:
AED, AUD, BRL, CAD, CHF, CNY, CZK, DKK, EUR, GBP, HKD, HUF, ILS, INR, MXN, NOK, NZD,
PLN, RON, SEK, SGD, TRY, USD and ZAR. The choice is stored in the database and included
in backups. It is proposed for new expenses, subscriptions and settlements.

Changing the default does not convert, relabel or rewrite existing records.
Recurring charges keep their subscription currency, and balances remain separate
for each currency. Language and currency are independent settings.
