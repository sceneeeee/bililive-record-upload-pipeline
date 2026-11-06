## Summary

Describe the behavior changed and link the related issue, if any.

## Compatibility and safety

- [ ] Pinned upstream versions and image digests remain unchanged, or the compatibility update is documented and verified.
- [ ] Upload retry behavior and handled/raw request ordering are considered.
- [ ] Multipart merge and parent/child task relationships are considered.
- [ ] Cleanup identity, callbacks, open FDs, restart recovery and final-failure retention are considered.
- [ ] No production deployment, restart or destructive operation is included.

## Validation

- [ ] `bash scripts/extract_upstream.sh`
- [ ] `bash tests/run.sh`
- [ ] `bash tests/validate_units.sh`
- [ ] Relevant Compose/systemd validation
- [ ] SHA256 lock and release manifest reviewed
- [ ] `git diff --check`
- [ ] Secret and forbidden-file scan reviewed

Explain skipped checks and attach only synthetic or sanitized evidence.

## Release and documentation

- [ ] User-visible changes are documented.
- [ ] Known limitations and rollback implications are documented.
- [ ] No credentials, recordings, databases, raw logs, backups or `temp_report.md` are included.
