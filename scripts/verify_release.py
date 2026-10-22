#!/usr/bin/env python3
"""Verify locked build artifacts and shipped source files offline."""
import argparse
import hashlib
import json
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundles', type=Path, default=REPO / 'build')
    args = parser.parse_args()
    lock = json.loads((REPO / 'patches/versions.lock.json').read_text())
    for name, spec in lock['bundles'].items():
        if hashlib.sha256((args.bundles / name).read_bytes()).hexdigest() != spec['patched_sha256']:
            raise SystemExit('bundle_mismatch:' + name)
    for name, spec in json.loads((REPO / 'patches/release-files.sha256.json').read_text()).items():
        if hashlib.sha256((REPO / name).read_bytes()).hexdigest() != spec['sha256']:
            raise SystemExit('release_source_mismatch:' + name)
    print('PASS: locked sources, units, Compose and both rebuilt bundles match')
if __name__ == '__main__': main()
