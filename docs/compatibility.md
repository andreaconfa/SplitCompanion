# Client compatibility

`GET /api/meta` is public and does not expose secrets. It returns `server_version`,
`api_version`, `capabilities`, `setup_required`, `source_available` and the
`compatibility.min_api_version` / `max_api_version` range. This release supports API 1.

Product version is informational: a 1.3 server is not automatically incompatible
with a 1.2 client. Clients should check the API contract and required capabilities.
Compatible additions retain API 1; breaking changes require a new contract version.

A client requiring a newer API should ask the user to update the server. A server
supporting only newer APIs requires a client update. Missing, malformed or
unreachable metadata does not prove compatibility: show update/retry guidance and
avoid unverified financial writes.

The bundled web app is built with the backend. Separately distributed clients
should check on connection, after reconnection and before writes. This does not
replace authentication, authorization or server-side input validation.

The native iOS companion checks compatibility and explains whether to update the
app, update the server, retry or change servers. Its source is not part of this
server/web distribution.
