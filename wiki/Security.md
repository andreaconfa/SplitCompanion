# Security

Split Companion is designed for private households and small groups, not a public
multi-tenant service with untrusted users. It does not offer open registration.
Code review and tests are part of release preparation; they are not a security
certification or an independent penetration test.

## Internet exposure

Access through a VPN exposes less of the service. If you choose Internet access,
expose only your HTTPS proxy and block direct access to port 8000. TLS, certificates,
DNS, firewall rules and proxy protections are the operator's responsibility.
No proxy is distributed with the application.

| Risk | Application controls | Operator responsibilities |
| --- | --- | --- |
| Stolen credentials or sessions | Argon2id, HttpOnly/Secure cookies over HTTPS, TOTP MFA, CSRF, revocable sessions | HTTPS, unique passwords, safe recovery-code storage |
| Login guessing | Account/IP, MFA and setup rate limits | Correct proxy configuration and protection against distributed traffic |
| Spoofed proxy headers | Explicit trusted IPs/CIDRs, HTTPS origin/host checks | Overwrite forwarded headers and isolate the backend port |
| Unauthorized data access | Group and administrator authorization | Create only trusted users; the user directory and avatars are instance-wide |
| Malicious uploads | Size limits, image re-encoding, import validation | Proxy limits/timeouts, disk and resource monitoring |
| Denial of service | One worker, body and authentication limits | Global request/concurrency/time limits; the app is not an anti-DDoS service |
| Host compromise | Standalone Compose: non-root container, read-only filesystem, dropped capabilities, no-new-privileges | Keep Linux and the runtime updated, do not mount the Docker socket, isolate networks |
| Stolen backups | Restrictive permissions and checksums | Backups are unencrypted: encrypt copies and store them off-host |
| Revived old access after restore | Saved sessions and challenges are invalidated | Reconcile passwords, disabled accounts, recovery codes and push consent |

Administrators do not automatically gain access to groups they have not joined.
Group members can modify transactions according to product rules: this is not an
immutable ledger against authorized members themselves.

Optional web push contacts external providers. Endpoints are validated and private
and loopback addresses are excluded; operators may additionally restrict outbound
traffic. Notifications can reveal information on a lock screen. Configure device
privacy settings and disable push if unnecessary.

Keep the application, base image, dependencies and proxy updated. Reference images
by explicit version or digest. CI blocks known high/critical vulnerabilities for
which the scanner reports a fix. Unfixed base-image findings are advisory and do
not automatically block a candidate release. Publish scan results with the release
and review residual risks before Internet deployment. Self-hosting makes the
operator responsible for deployment, access and updates; it does not make known
vulnerabilities harmless or remove the need to maintain the application.

## Report a vulnerability

Use **Security → Report a vulnerability** when Private Vulnerability Reporting is
available on the GitHub repository. It must be enabled before the first public
release. Do not disclose exploit details or real data in a public issue. If the
private channel is not active, request activation without including sensitive details.

## References

- [OWASP Docker security guidance](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [Proxy and HTTPS](HTTPS-and-proxies.md)
- [Backup and recovery](Backups-and-updates.md)

## Home Assistant package

The Home Assistant variant briefly starts as root to read Supervisor options and
initialize its own persistent directories, then drops to UID/GID 10001 before
opening the application. Supervisor manages its container isolation; it does not
use the standalone Compose file. Protection mode remains enabled, and the package
requests no privileged mode, host networking, Docker socket or Home Assistant API.
Keep Supervisor and Home Assistant OS updated.

The initial setup code is temporarily stored in the App's protected options, like
other App secrets. Clear it after completing setup. Home Assistant backups contain
these options and application data; encrypt them and keep a copy off the device.
