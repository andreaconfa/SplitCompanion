# External HTTPS reverse proxy

Split Companion serves HTTP on port 8000. The container does not install, run or
configure a proxy, certificates, DNS or TLS renewal. Use your own Nginx Proxy
Manager, Caddy, Nginx or equivalent infrastructure.

1. Set up a DNS name and a certificate trusted by your clients.
2. Forward the entire origin, including the web app and `/api`, to port 8000.
   A subpath such as `/split/` is not supported.
3. Preserve the original `Host` header. The proxy must **overwrite**
   `X-Forwarded-Proto` and `X-Forwarded-For`, not trust client-supplied values.
4. Configure `.env`:

   ```dotenv
   SPLIT_COMPANION_PUBLIC_ORIGIN=https://split.example.org
   SPLIT_COMPANION_TRUSTED_PROXY_IPS=192.0.2.10
   SPLIT_COMPANION_ALLOW_HTTP=false
   ```

   Replace these documentation-only addresses. Use the proxy IP **as seen by the
   container**. Do not trust `*`, `0.0.0.0/0`, `::/0` or unnecessarily broad LAN
   ranges. With `PUBLIC_ORIGIN`, cookies become Secure and requests must match the
   configured host and scheme. `/api/health` and `/api/ready` remain local probes.
5. Apply changes with `docker compose up -d` and check login through HTTPS.

The default `127.0.0.1` binding works for a proxy on the same host. A proxy in
another container cannot reach the host's loopback interface. Attach it through
your own dedicated Docker network override, or bind only to a private interface
reachable by that proxy and enforce firewall restrictions. Do not expose port
8000 to the Internet. Docker port publishing may bypass some firewall frontends;
verify reachability from outside the server.

Set concurrency limits, request rate limits and read timeouts on the proxy. Allow
request bodies up to 12 MiB; the app enforces smaller endpoint-specific limits.
A lower proxy limit may block imports. Multiple proxy hops require a verified
configuration for the original client IP; otherwise rate limiting may group all
users together or rely on spoofed headers.

TLS terminates at your proxy. Protect the proxy-to-application connection too.
Do not cache `/api` responses, cookies or authenticated pages. `PUBLIC_ORIGIN`
must match the actual client-facing origin, without a trailing slash or path.
