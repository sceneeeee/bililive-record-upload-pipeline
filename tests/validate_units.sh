#!/usr/bin/env bash
# Verify copies with executable paths mapped to this checkout; no services started.
set -euo pipefail
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
python3 - "$repo" "$tmp" <<'PY'
from pathlib import Path
import sys
repo, target = map(Path, sys.argv[1:])
for p in (repo/'systemd').iterdir():
    text=p.read_text().replace('/usr/local/sbin/',str(repo/'scripts')+'/')
    (target/p.name).write_text(text)
(target/'docker.service').write_text('[Service]\nType=oneshot\nExecStart=/bin/true\n')
PY
SYSTEMD_UNIT_PATH="$tmp:/usr/lib/systemd/system:/lib/systemd/system" systemd-analyze verify --man=no "$tmp"/pipeline-*.service "$tmp"/pipeline-*.timer
