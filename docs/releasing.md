# Prepare a public release

This branch contains server/web source and documentation with a fresh public
history. Do not use `git push --mirror` or `--all` from a repository that also
contains private branches. Create a clone of only the release branch, without
private tags, inspect refs/remotes and push only the intended branch.

## Before publication

1. Choose a GitHub repository and registry namespace. Enable Private Vulnerability
   Reporting and verify GHCR package permissions.
2. Check files, history, commit identities, screenshots, source archives and image
   layers. Scan for secrets and personal references. Do not add real exports,
   `.env`, databases, backups, certificates or native iOS source. Use synthetic demo data.
3. Run Python tests, frontend tests, TypeScript, the web build and
   `scripts/container-smoke.py` on both Linux amd64 and arm64 hosts with local storage.
   The smoke test creates and destroys only its own new temporary directories.
4. Update `backend/app/version.py`, image tags and documentation consistently.
   The workflow accepts `vX.Y.Z` or `vX.Y.Z-rc.N` and rejects tag/version mismatches.
5. Push the verified candidate commit to a staging branch and tag it. Keep the
   default branch on the previous version until the images exist. Publish a GitHub
   release on that candidate commit. `release.yml` tests and scans
   the build, starts both Linux amd64 and arm64 images and publishes its version tag at `ghcr.io/<owner>/<repository>:<version>`.
6. Release attachments use `env.example` for the configuration template; copy it
   to `.env` when installing. The source tree keeps `.env.example`. GitHub rewrites
   attachment names that start with a dot, so checksums must use the attachment name.
7. Check that the package is public and test an anonymous pull from a clean host.
   Put the exact image name and digest in release notes and examples. Never
   overwrite versions already delivered to users. Only after both standard and
   Home Assistant image tags are anonymously pullable, fast-forward the default
   branch to the candidate commit and publish the matching Wiki. This prevents
   Home Assistant from offering an update whose image is not available yet.

Publishing runs only for a published GitHub release, not ordinary pushes. Private
preparation does not publish a package. There is no automatic `latest` tag.
Repository visibility and package visibility are separate settings.

## Manual build and attachments

```sh
docker build --platform linux/amd64 -t splitcompanion:1.2.1-rc.2 .
docker save -o splitcompanion-amd64.tar splitcompanion:1.2.1-rc.2
python3 scripts/make-source-archive.py --output splitcompanion-source.tar.gz
sha256sum splitcompanion-amd64.tar splitcompanion-source.tar.gz > SHA256SUMS
```

Distribute corresponding source with binaries. Images also include
`/app/source.tar.gz`, downloadable at `/api/source`. The frontend build generates
`third-party-notices.txt`; Python packages retain their notices and metadata in
the image. Do not remove third-party notices.

## GitHub Wiki

The wiki lives in `wiki/` and can also be read directly in the repository.
Prepare files for the separate GitHub Wiki repository:

```sh
python3 scripts/export-wiki.py --output /tmp/splitcompanion-wiki
```

The command creates a new output directory and adjusts links for GitHub Wiki.
It does not create remote repositories or publish content. Commit those files to
your wiki repository after enabling it. Update the wiki with each release and
check links on the destination service.

The release workflow also tests and publishes the Home Assistant variant using
`ghcr.io/<owner>/<repository>-homeassistant:<version>`. Keep its manifest version
identical to the server release, with no image-variant suffix. Both packages must
be public before advancing the default branch. A new GHCR package may start private;
verify its visibility and anonymous downloads separately.

Home Assistant uses AwesomeVersion to compare App versions. The regression suite
checks upgrades from both legacy `1.2.0-rc.N-homeassistant` packages and future
candidate/stable version ordering. Do not append `-homeassistant` to the version: use
the separate image repository to distinguish the variant.
