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
5. Start the App and open its **Log** tab. Copy the automatically generated value
   after **Split Companion initial setup code:**.
6. Choose **Open Web UI** and paste the code to create the first administrator
   within 30 minutes. If it expires or you lose it, restart the App and use the
   newest code from the Log tab. A restart replaces the previous code.
7. Complete two-factor authentication and keep recovery codes safe. After setup,
   the code is invalidated and subsequent starts no longer generate or print one.
8. Enable **Start on boot**, optionally **Watchdog**, and **Show in sidebar**.
   **Open Web UI** now opens Split Companion inside Home Assistant.

No manual setup-code option is required. Old `initial_setup_code` options from
previous releases are ignored, including values that previously prevented startup.
The database stores only the code's hash. The initial code is intentionally shown
in the protected Home Assistant App log so the operator can retrieve it; do not
share that log while setup is pending. Application request logs never contain it.
Existing configured instances keep their users and data and skip this step.

## Network and HTTPS

**Open Web UI** and **Show in sidebar** use Home Assistant Ingress. The internal
listener on port 8099 accepts only the Supervisor at `172.30.32.2`; it is not
published on the host. Split Companion still requires its own account and, when
enabled, two-factor authentication. Home Assistant user headers do not grant
Split Companion permissions. Sessions in the sidebar are separate from direct
browser sessions and their cookies are scoped to the Ingress path.

The direct address remains `http://HOME_ASSISTANT_HOST:8000` for native clients
and browsers. Change or disable the exposed port in the App's **Network** section;
Ingress works without exposing it. HTTP is intended only for a trusted local
network. Use the direct address in native clients, not the temporary Ingress URL.

For Internet access and the full iPhone PWA experience, provide your own external
HTTPS reverse proxy. Set **Public origin** to the exact HTTPS URL with no trailing
path, **Trusted proxy IPs** to the proxy addresses/CIDRs only, and disable **Allow
HTTP**. Use that HTTPS address for installing the PWA and web push. Never trust
all addresses. No proxy or certificate service is bundled. These direct-origin
settings do not prevent the sidebar from working through Home Assistant's own
HTTP or HTTPS origin.

PWA installation, service-worker registration and browser push controls are disabled
inside Ingress. Use the direct HTTPS address for those features. Ordinary app
features, language selection, avatars, imports and downloads remain available in
the sidebar. Ingress supports only same-origin embedding by Home Assistant.

The implementation follows the [official Ingress requirements](https://developers.home-assistant.io/docs/apps/presentation/).

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

## Updating from rc.5 or rc.6

Version `1.2.1-rc.1` fixes the disabled Update button caused by the legacy
`-homeassistant` version suffix. Refresh the App store, then update the existing
App. Its slug, settings and persistent data remain unchanged. Do not reinstall.
The App now pulls `ghcr.io/andreaconfa/splitcompanion-homeassistant`, with the same
version as the server and no suffix in the version number.

## Troubleshooting

- **App missing:** update the repository list and check that the device uses
  amd64 or aarch64. 32-bit ARM is not supported.
- **Setup code rejected:** restart the App and copy the newest automatic code from
  its Log tab. It expires after 30 minutes. After too many failed attempts, wait
  for the attempt limit to clear; restarting does not bypass that limit.
- **App fails to start:** check timezone, origin, proxy ranges and writable storage.
  Errors never require deleting the database.
- **Sidebar unavailable:** restart the App after updating, then reopen **Open Web UI**.
  Only the Supervisor can connect to its internal Ingress port. Do not publish port 8099.
- **Direct URL unavailable:** check the configured host port and firewall.
- **PWA unavailable:** a local HTTP URL is not enough; use trusted HTTPS.

The images are built and smoke-tested on Linux amd64 and arm64. Those checks cover
options, privilege dropping, setup, backups, persistence, and a simulated Supervisor
Ingress session (assets, login, CSRF and logout); they do not substitute
for an installation test on every supported Home Assistant OS device.
