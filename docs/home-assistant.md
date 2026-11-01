# Home Assistant installation

Install Split Companion as a Home Assistant App (formerly an add-on) on **Home
Assistant OS**, with **amd64 or aarch64/arm64** hardware. This installs the full
server and web/PWA. It is not a HACS integration and does not create dashboard
entities. Home Assistant Container users should use the standalone Docker image.

[![Add the Split Companion repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fandreaconfa%2FSplitCompanion)

## Install and configure

1. In Home Assistant, open **Settings → Apps → Install app → ⋮ → Repositories**
   (older versions call this **Add-ons → Add-on Store**).
2. Add `https://github.com/andreaconfa/SplitCompanion`.
3. Install **Split Companion** from this repository.
4. In **Configuration**, choose your IANA timezone, for example `Europe/London`.
   Keep two-factor authentication enabled.
5. Generate a random setup code in a password manager: 32–128 letters, digits,
   hyphens or underscores. Paste it into **Initial setup code** and save.
6. Start the App, then choose **Open Web UI**. Use the same setup code to create
   the first administrator. The code expires after 30 minutes. If it expires,
   choose a new random code, save and restart. Restarting with the same code does
   not renew it or reset failed attempts.
7. Complete two-factor authentication, keep recovery codes safe, then clear
   **Initial setup code** in the App configuration and save. Setup stays closed.
8. Enable **Start on boot** and optionally **Watchdog**.

The setup code is stored in Home Assistant's protected App options while it is
configured. Split Companion stores only its hash in its database and never prints
it in ordinary logs. Do not share App configuration files or backups.

## Network and HTTPS

The default address is `http://HOME_ASSISTANT_HOST:8000`. Change the exposed port
in the App's **Network** section if port 8000 is occupied. HTTP is intended only
for a trusted local network. The App has its own accounts; Home Assistant login
does not replace Split Companion login.

For Internet access and the full iPhone PWA experience, provide your own external
HTTPS reverse proxy. Set **Public origin** to the exact HTTPS URL with no trailing
path, **Trusted proxy IPs** to the proxy addresses/CIDRs only, and disable **Allow
HTTP**. Then use that HTTPS address in your browser instead of the direct
HTTP Open Web UI link. Never trust all addresses. Set `push_enabled` and a VAPID contact only if
you want web push. No proxy or certificate service is bundled.

This first package uses **Open Web UI** on its own port. It does not use Home
Assistant Ingress or a sidebar iframe. The direct origin supports the existing
API, CSRF protections, native clients and PWA service worker without path rewriting.

## Data, backups and updates

Home Assistant persists the App's `/data` directory across container updates:

- `/data/instance`: database, secret and push keys.
- `/data/backups`: complete daily and pre-migration application backups.
- `/data/options.json`: options managed by Home Assistant.

The server runs as UID/GID 10001 after a short initialization of its own two
storage directories. It does not need privileged mode, the Docker socket, host
networking, Home Assistant API access or shared configuration folders.

Include this App in Home Assistant backups and copy backups off the device. The
App uses cold backups: Home Assistant stops it while capturing its files. Daily
application backups are kept in the same persistent App volume and protect against
logical mistakes, not disk failure. Keep a Home Assistant backup before updates.

Update through Home Assistant. Updating preserves data; uninstalling and deleting
App data does not. Do not downgrade after a database migration without restoring
the matching backup. To move to standalone Docker, restore the matching App backup
first, then move the complete `instance` contents (including `secret.key`) to the
standalone data directory with the server stopped. Never run two servers against
one database or discard the secret.

## Language and currency

Choose **English** or **Italiano** in Split Companion Settings. English is the
default. Administrators can change the server's default currency in **Settings →
Administration**. It applies to new records only; existing expenses, balances and
subscription charges keep their currencies. There is no currency conversion.

## Troubleshooting

- **App missing:** update the repository list and check that the device uses
  amd64 or aarch64. 32-bit ARM is not supported.
- **Setup code rejected:** use a fresh random code and restart; confirm it meets
  the length/character rules. Never paste a login password into this field.
- **App fails to start:** check timezone, origin, proxy ranges and writable storage.
  Errors never require deleting the database.
- **Open Web UI unavailable:** check the configured host port and firewall.
- **PWA unavailable:** a local HTTP URL is not enough; use trusted HTTPS.

The images are built and smoke-tested on Linux amd64 and arm64. Those checks cover
options, privilege dropping, setup, backups and persistence; they do not substitute
for an installation test on every supported Home Assistant OS device.
