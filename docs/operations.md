# Backups, updates and account recovery

## What to keep

The `data` directory contains SQLite, the application secret, VAPID push keys and
operational state. Uploaded avatars and icons are stored in the database.
The `backups` directory contains consistent archives with the database, secrets
and a checksum manifest.

Backups are **unencrypted** and contain private information. Restrict access,
encrypt off-host copies and keep a copy on another host. Never attach them to
GitHub issues or commit them to Git.

```sh
docker compose exec app python -m app.cli backup-full --output-dir /backups --kind manual
```

Daily backups run at 03:00 in the configured timezone by default, retaining the
latest 14 daily backups. Manual and pre-migration backups are kept separately from
that rotation. Monitor disk space and administrator diagnostics.

## Update

Create a backup and record the current image version/digest. Set the new image
version/digest, run `docker compose pull`, then `docker compose up -d`. For a local
image archive, use `docker load` instead of `pull`. Do not delete or change the
`data` and `backups` directories. Only one application instance may write the database.

Startup validates schema, integrity, permissions and assets and takes a backup
before migrations. If a required check fails, startup stops without automatically
restoring old data. Inspect:

```sh
docker compose ps
docker compose logs --tail 100 app
curl --fail http://localhost:8000/api/ready
```

A Docker healthcheck can mark a container unhealthy, but does not itself restart
it. Downgrading the image does not undo migrations: use the matching image and
backup. Do not overwrite newer transactions with an older backup without reconciliation.

## Offline restore into a new directory

Stop the service and preserve its current data. Create an empty directory and
run the CLI using an image compatible with the backup. From the Compose directory,
replace the archive name and image version in this example with your actual values:

```sh
docker compose stop app
sudo install -d -m 0700 -o 10001 -g 10001 data-restored
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --mount "type=bind,src=$PWD/data-restored,dst=/data" \
  --mount "type=bind,src=$PWD/backups,dst=/backups,readonly" \
  splitcompanion:1.2.0-rc.3 python -m app.cli restore /backups/ARCHIVE.tar.gz --confirm
```

The command verifies the archive, checksums, database integrity and compatibility.
Set `SPLIT_COMPANION_DATA_DIR=./data-restored` before restarting. Saved sessions and
pending MFA challenges are invalidated during restore, so users must sign in again.
The original MFA secret is preserved, keeping enrolled authenticators usable.

A backup also restores old passwords, account state, recovery codes and push
consent. Before exposing the instance again, reconcile disabled accounts, changed
passwords and consumed recovery codes. Regenerate recovery codes when necessary.

## Recover an account

```sh
docker compose exec app python -m app.cli reset-password USERNAME
docker compose exec app python -m app.cli reset-mfa USERNAME
```

The password is requested without echo; do not pass it as a shell argument.
MFA reset is a sensitive administrator operation: verify the person's identity.
Disabling administrators does not reopen initial setup.

## Diagnostics

`/api/health` retains its `{"status":"ok"}` response. `/api/ready` checks service
readiness. `/api/admin/status` requires an administrator and reports scheduler,
backup and notification status. Push delivery failures do not disable accounting.
Use logs and request IDs to investigate errors without sharing passwords, cookies,
imports or database files.
