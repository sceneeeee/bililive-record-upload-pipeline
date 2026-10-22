#!/usr/bin/env bash
# Current production rollback preserves the existing audited window guard.
set -euo pipefail
if [[ ${1:-} != --approved-window || $EUID != 0 ]]; then
    echo 'Usage: sudo scripts/rollback_api.sh --approved-window (requires a newly approved window)' >&2
    exit 1
fi
stage=${PATCH_STAGE:-${STACK_ROOT:-/opt/bililive-stack}/patches/uploader-3.20.0}
test -f "$stage/apply.py"
systemctl disable --now pipeline-api-patch-window.timer
systemctl disable --now pipeline-upload-cleaner.service
# The deployed guard validates live, task, callback, merge window and source hashes.
python3 "$stage/apply.py" --approved-window --rollback
