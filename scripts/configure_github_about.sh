#!/usr/bin/env bash
# Apply the suggested public GitHub About metadata.
# Run manually from a maintainer workstation with an authenticated gh CLI.
set -euo pipefail

command -v gh >/dev/null 2>&1 || {
  echo "GitHub CLI (gh) is required." >&2
  exit 1
}

repo="sceneeeee/bililive-record-upload-pipeline"
gh auth status >/dev/null

echo "Current metadata:"
gh repo view "$repo" --json description,homepageUrl,repositoryTopics

echo
echo "Applying repository description, homepage and topics..."
gh repo edit "$repo" \
  --description "Self-hosted Bilibili live recording and auto-upload pipeline with reproducible patches, conservative cleanup, and monitoring." \
  --homepage "https://github.com/sceneeeee/bililive-record-upload-pipeline/blob/main/docs/deployment.md" \
  --add-topic bilibili \
  --add-topic bililiverecorder \
  --add-topic bililive-tools \
  --add-topic live-stream-recording \
  --add-topic auto-upload \
  --add-topic self-hosted \
  --add-topic docker-compose \
  --add-topic systemd \
  --add-topic python \
  --add-topic video-automation

echo
echo "Updated metadata:"
gh repo view "$repo" --json description,homepageUrl,repositoryTopics
