# Contributing

Start by describing the problem and how to reproduce it with synthetic data.
Do not attach databases, real exports, passwords, tokens, personal photos or
private server addresses. For vulnerabilities, follow [SECURITY.md](SECURITY.md)
instead of opening a public issue with exploit details.

Preserve the accounting rules: integer amounts, separate currencies, idempotent
recurring charges, group access control and import provenance. Add regression
tests where appropriate and follow the [development guide](docs/native.md).
Server/web contributions use AGPL-3.0. Preserve dependency notices and keep the
distributed source archive consistent with the application.

Do not add personal configuration or reverse proxy services to the application
Compose file. Native Linux installations must remain possible without Docker.
Breaking API changes require an explicit contract version change.

Use English for documentation and examples. Use fictional names and reserved
example domains/IP addresses. Screenshots must use synthetic data and must not
expose real users, server addresses, account details or credentials.
