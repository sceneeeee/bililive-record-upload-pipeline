#!/usr/bin/env bash
# Future authorized deployment only; backs up every destination before mutation.
set -euo pipefail
if [[ ${1:-} != --install || $EUID != 0 ]]; then
    echo 'Usage: sudo scripts/install_maintenance.sh --install (after deployment review)' >&2
    exit 1
fi
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
stack_root=${STACK_ROOT:-/opt/bililive-stack}
backup="$stack_root/backups/maintenance-units-$(date +%Y%m%d-%H%M%S)"
if [[ "$stack_root" != /* || "$stack_root" =~ [[:space:]] ]]; then
    echo 'STACK_ROOT must be absolute and contain no whitespace' >&2; exit 1
fi
if [[ -e /etc/bililive-pipeline/maintenance.env ]]; then
    echo 'Review existing maintenance.env before updating (installer preserves it)'
fi
test -f "$stack_root/.env"
test -f "${PATCH_STAGE:-$stack_root/patches/uploader-3.20.0}/applied.json"
test ! -e "$backup"
install -d -m 0700 "$backup"
for name in pipeline-upload-cleaner.py pipeline-recorder-monitor.py pipeline-api-patch-window.py; do
    target="/usr/local/sbin/$name"
    if [[ -e "$target" ]]; then cp -p -- "$target" "$backup/$name"; fi
    install -m 0750 "$repo/scripts/$name" "$target"
done
for source in "$repo"/systemd/*; do
    name=$(basename -- "$source")
    target="/etc/systemd/system/$name"
    if [[ -e "$target" ]]; then cp -p -- "$target" "$backup/$name"; fi
    python3 - "$source" "$target" "$stack_root" "${PATCH_STAGE:-$stack_root/patches/uploader-3.20.0}" <<'RENDER'
from pathlib import Path
import sys
source, target, root, stage = sys.argv[1:]
text = Path(source).read_text().replace('/opt/bililive-stack/patches/uploader-3.20.0', stage)
text = text.replace('/opt/bililive-stack', root)
Path(target).write_text(text)
Path(target).chmod(0o644)
RENDER
done
systemd-analyze verify /etc/systemd/system/pipeline-upload-cleaner.service /etc/systemd/system/pipeline-recorder-monitor.service /etc/systemd/system/pipeline-recorder-monitor.timer /etc/systemd/system/pipeline-api-patch-window.service /etc/systemd/system/pipeline-api-patch-window.timer
install -d -m 0755 /etc/bililive-pipeline
if [[ ! -e /etc/bililive-pipeline/maintenance.env ]]; then
    printf 'STACK_ROOT=%s\nPATCH_STAGE=%s\nCLEANER_POLICY_ARGS=\n' "$stack_root" "${PATCH_STAGE:-$stack_root/patches/uploader-3.20.0}" > /etc/bililive-pipeline/maintenance.env
    chmod 0600 /etc/bililive-pipeline/maintenance.env
fi
systemctl daemon-reload
# Do not schedule the archived API change again; preserve approval markers.
systemctl enable --now pipeline-upload-cleaner.service pipeline-recorder-monitor.timer
echo "Installed. Backup: $backup. API window timer was not enabled."
