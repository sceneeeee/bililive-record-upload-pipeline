# Release procedure

GitHub Release is a source-code publication step. It is **not** a production deployment approval.

## Versioning

The repository version is independent of upstream BililiveRecorder 2.18.0 and biliLive-tools 3.20.0.

- Patch: backward-compatible bug fixes.
- Minor: backward-compatible features.
- Major: breaking behavior, configuration or compatibility changes.
- Pre-releases: `v0.1.0-rc.1`, `v0.1.0-rc.2`, etc., for review before a stable release.

Do not invent historical tags. The initial public commit is not retroactively assigned a release date.

## Current release recommendation

Prepare `v0.1.0-rc.1` as a **draft pre-release** only after the checklist below. The current public implementation has offline test evidence, and its historical ancestor has production-use evidence, but the historical scheduler and cleaner are not identical to the current public implementation. Do not label the current revision production-certified.

## Pre-release checklist

1. Confirm the target commit, branch, clean working tree and absence of `temp_report.md`, credentials, recordings, databases, raw logs and backups.
2. Rebuild the locked upstream bundles with `bash scripts/extract_upstream.sh`.
3. Run `bash tests/run.sh` and `bash tests/validate_units.sh`.
4. Validate both Compose examples with synthetic credentials.
5. Run Python compilation, shell syntax checks and Node syntax checks.
6. Run Gitleaks against the staged tree and full Git history, plus `scripts/scan_repository.py --staged` and `--history`.
7. Verify `patches/release-files.sha256.json` and `patches/versions.lock.json`.
8. Review third-party notices, patch diffs, known limitations and the production evidence matrix.
9. Confirm the GitHub Actions run for the exact target commit is green.
10. Review the generated GitHub source archive. Do not attach upstream bundles, production configuration, credentials, videos, databases or logs.

## Draft release notes

Use [the v0.1.0-rc.1 draft notes](release-notes/v0.1.0-rc.1.md). Replace any unresolved checklist items with actual evidence or explicit UNKNOWN statements before publication.

Suggested title: `v0.1.0-rc.1 — Reproducible recording and upload integration`.

Mark it as a pre-release. Do not publish a stable `v0.1.0` until the current public revision has completed its required end-to-end validation and the outstanding evidence gaps are addressed.

## GitHub CLI examples

Run these commands from a maintainer workstation after reviewing the target commit and CI. They create a draft only; they do not deploy to production.

```sh
gh release create v0.1.0-rc.1 \
  --verify-tag \
  --draft \
  --prerelease \
  --title "v0.1.0-rc.1 — Reproducible recording and upload integration" \
  --notes-file docs/release-notes/v0.1.0-rc.1.md
```

The tag must already exist and point to the reviewed commit. Review the draft in GitHub before publishing it.

## GitHub repository About metadata

Suggested description:

`Self-hosted Bilibili live recording and auto-upload pipeline with reproducible patches, conservative cleanup, and monitoring.`

Suggested topics:

`bilibili`, `bililiverecorder`, `bililive-tools`, `live-stream-recording`, `auto-upload`, `self-hosted`, `docker-compose`, `systemd`, `python`, `video-automation`.

Suggested homepage: the repository deployment guide.

Use `gh repo edit` to apply the values after checking existing metadata; do not overwrite unrelated settings.
