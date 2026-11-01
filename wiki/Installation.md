# Docker installation

A single application container, with persistent data on your Linux host.

## Quick start on Linux

You need Docker Engine with the Compose plugin and a local disk on a Linux server
(amd64 / x86-64 or arm64 / aarch64). Run **one replica and one worker**. Do not put SQLite on NFS or SMB.

1. Download `compose.yaml` and `env.example` from the [same release](https://github.com/andreaconfa/SplitCompanion/releases/tag/v1.2.0-rc.5).
2. Prepare the configuration and persistent directories:

   ```sh
   cp env.example .env
   sudo install -d -m 0700 -o 10001 -g 10001 data backups
   ```

3. The example selects `ghcr.io/andreaconfa/splitcompanion:1.2.0-rc.5`. You can pin
   the digest from the release instead.
   Alternatively, [build from source](Build-from-source.md).
4. Start the application and generate the initial setup code:

   ```sh
   docker compose pull
   docker compose up -d
   docker compose exec app python -m app.cli setup-token
   ```

5. Open `http://localhost:8000` on the server and create the administrator account.
   The code expires after 30 minutes and can only be used once. Complete two-factor
   authentication and store your recovery codes somewhere safe.

The default binding is **127.0.0.1**, accessible only on the server. To connect from
a trusted LAN, set `SPLIT_COMPANION_BIND` to the server's LAN address and recreate
the container. HTTP does not encrypt credentials or data. For Internet access or
a phone PWA, configure your own [external HTTPS reverse proxy](HTTPS-and-proxies.md).

## Update the container, keep your data

| Host directory | Container path | Contents |
| --- | --- | --- |
| `./data` | `/data` | SQLite database, instance secret, push keys and operational state |
| `./backups` | `/backups` | Complete backup archives |

Choose different absolute host paths in `.env` if needed. Both directories must
exist and be writable by UID/GID `10001:10001`. Do not use `chmod 777`.
Recreating the container keeps these directories intact. Keep the entire `data`
directory, not just the `.db` file: losing the secret prevents MFA recovery.

```sh
docker compose exec app python -m app.cli backup-full --output-dir /backups --kind manual
# Set the new image version or digest in .env, then:
docker compose pull
docker compose up -d
docker compose ps
```

For archive-based installations, use `docker load` instead of `pull`.
Read the [backup and restore guide](Backups-and-updates.md) before downgrading.


## Next steps

- [Configuration and troubleshooting](Configuration.md)
- [HTTPS and proxies](HTTPS-and-proxies.md)
- [Install the PWA](PWA.md)
- [Backup and account recovery](Backups-and-updates.md)
