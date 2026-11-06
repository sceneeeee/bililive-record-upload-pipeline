# Bililive Recording & Auto-Upload Pipeline

A self-hosted integration for Bilibili live recording and automatic upload, combining [BililiveRecorder](https://github.com/BililiveRecorder/BililiveRecorder) with [biliLive-tools](https://github.com/renmu123/biliLive-tools).

[中文 README](../README.md) · [Deployment](deployment.md) · [Architecture](architecture.md) · [Validation](validation.md) · [Production evidence](production-evidence.md) · [Changelog](../CHANGELOG.md)

> This is an independent community integration, not an official release or endorsement by either upstream project. Historical deployments provide evidence that an ancestor workflow was used in practice, but the historical scheduler and cleaner differ from the current public implementation. See [production evidence](production-evidence.md) before interpreting those observations.

## Pinned components

| Component | Version | Role |
| --- | --- | --- |
| BililiveRecorder | 2.18.0 | Recording, segmentation and webhook |
| biliLive-tools | 3.20.0 | Post-processing, upload, submission and multipart handling |

Image digests and upstream bundle / patched bundle SHA256 values are tracked in `patches/versions.lock.json`. The build accepts only the pinned inputs and does not follow mutable upstream tags.

## Features

- Reproducible Linux/amd64 bundle extraction and patching with SHA256 verification.
- Upload stream lifecycle patch that closes source and throttled streams and carries source file identity metadata.
- Immediate post-processing upload scheduling while retaining periodic scanning as a fallback.
- Per-live serialization with separate pending request types for `handled`, `raw` and unspecified requests.
- Conservative SQLite-backed cleanup with task, callback, file identity, open-FD and API snapshot checks.
- Docker Compose examples, systemd units, monitoring, deployment preparation and rollback tooling.
- Offline Python / Node.js tests and GitHub Actions validation.

## Quick start

Requirements: Linux/amd64, Docker Compose, systemd, Python 3.10+, Node.js 22, GNU patch and Bash.

```sh
git clone https://github.com/sceneeeee/bililive-record-upload-pipeline.git
cd bililive-record-upload-pipeline
bash scripts/extract_upstream.sh
bash tests/run.sh
```

For a deployment, credential setup, recorder configuration, webhook and maintenance-window instructions, read the [deployment guide](deployment.md) first. The extraction step does not start or modify a production stack; generated upstream bundles stay in the ignored `build/` directory.

## Data deletion and safety

- The public sidecar cleaner defaults to retaining final upload failures. `--delete-final-failure` explicitly opts into irreversible deletion eligibility; all other safety checks still apply.
- Active, queued, retrying, cancelled, ambiguously linked or FD-open sources must be retained.
- Upstream `afterUploadDeletAction=delete` may delete successful sources before the sidecar cleaner can inspect them. The sidecar cannot retroactively protect an upstream deletion.
- Upload success does not mean Bilibili review approval or permanent remote availability. Keep independent backups if re-upload is important.
- A historical deployment used a different cleaner that allowed final-failure deletion. Do not silently carry that policy into the public default.

## Validation status

The repository has offline Python and Node.js tests, pinned-bundle checks, Compose/systemd validation and secret scanning. Historical production observations include real FLV segmentation, webhook/upload activity and repeated parent submission/edit operations. However:

- The historical scheduler bundle predates the current handled/raw pending-type fix.
- The historical cleaner and monitoring units are separate from the public implementation.
- Historical logs include storage-pressure and log-decoding incidents; full retry recovery rates and public multipart playback integrity were not established.
- The current public revision has not completed a full real-live end-to-end acceptance or a fresh-host install/rollback rehearsal.

See [validation scope](validation.md) and [production evidence](production-evidence.md). Do not treat CI success or ancestor-version operation as certification of the current public commit.

## Documentation

- [Deployment](deployment.md)
- [Architecture and state boundaries](architecture.md)
- [Operations and cleaner verification](operations.md)
- [Validation scope](validation.md)
- [Production evidence and version mapping](production-evidence.md)
- [Update and rollback](rollback.md)
- [Patch and SHA256 details](../patches/README.md)
- [Contributing](../CONTRIBUTING.md)
- [Security policy](../SECURITY.md)
- [Third-party notices](../THIRD_PARTY_NOTICES.md)

## License

New integration code is licensed under **GPL-3.0-only**. Upstream projects and bundled dependencies retain their own licenses and copyrights; see [third-party notices](../THIRD_PARTY_NOTICES.md).
