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

## Localization and currency defaults

Clients may send `Accept-Language: en` or `it`; English is the fallback. API fields,
status codes and stored user content are unchanged. `/api/meta` and authenticated
session responses also expose `default_currency`, `supported_currencies` and
`supported_languages`. Older clients may ignore these additive fields.

Administrators read or change `/api/admin/settings`; writes require the existing
authentication and CSRF protections. An omitted currency on a new record uses the
server default. Explicit currency values and existing records retain their meaning.
Web push subscriptions may include `language` (`en` or `it`); otherwise the request
language is used. Clients should refresh the subscription after a language change.
