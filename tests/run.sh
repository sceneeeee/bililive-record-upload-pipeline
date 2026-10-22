#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo"
python3 scripts/verify_release.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
node tests/test_upload_streams.cjs
node tests/test_immediate_upload.cjs
