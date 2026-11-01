# Roadmap

Split Companion starts with a simple goal: make shared expenses easy to manage
on infrastructure you control. This is a direction for the project, not a release
schedule. Priorities may change with feedback, available time and adoption.

## First public release

- [x] Publish versioned Linux amd64 and arm64 images and matching source archives.
- [ ] Complete fresh-install, upgrade and restore checks for the supported deployments.
- [ ] Refine onboarding and documentation from feedback from early self-hosters.
- [ ] Continue dependency updates, security review and accessibility improvements.
- [ ] Make the native iOS app available after Apple review and approval.

The current server/PWA candidate already supports shared groups, settlements,
subscriptions, credits, imports, monthly statistics and administrator-managed accounts.
The iOS companion already includes widgets, an Apple Watch app and complications;
public availability is separate from implementation.

## Next: personal expense management

- [ ] A private space for individual expenses, separate from shared groups.
- [ ] Personal categories, recurring expenses and monthly spending summaries.
- [ ] Optional budgets and a clear view of personal spending trends.
- [ ] Clear handling of personal shares of group expenses to avoid double counting.

Personal records should remain private to their owner. This feature must not
change existing group balances or the rules for shared expenses. The exact design
and privacy model will be reviewed before implementation.

## If the project gains traction: Android

- [ ] A native Android companion connected to the same self-hosted backend.
- [ ] A consistent experience with web and iOS, including API compatibility checks.
- [ ] Explore Android widgets and platform-appropriate notifications.

Android is an intended next platform if there is enough demand and development
capacity. There is no committed release date. Android users can use the web app
and installable PWA in the meantime.

## Home Assistant

- [x] Package the server as a Home Assistant App (formerly an add-on), with persistent data and installation instructions.
- [x] Build and smoke-test amd64 and arm64 images.
- [ ] Explore an optional HACS integration for balances and upcoming payments in dashboards.

HACS integration and server installation are separate projects. App packaging targets
Home Assistant OS; a HACS integration would connect to an existing server.

## Further improvements to explore

- Additional languages beyond English and Italian.
- Better data portability, export options and import feedback.
- More useful statistics and filters for longer transaction histories.
- Accessibility, keyboard navigation and responsive layout refinements.
- Clearer operational diagnostics and easier backup/restore verification.

Managed cloud hosting, bank connections and a public multi-tenant service are not
part of the initial self-hosted release. Suggest use cases through issues without
including real financial records, credentials or other private information.
