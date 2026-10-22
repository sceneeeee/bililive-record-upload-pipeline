#!/usr/bin/env python3
"""Rebuild the exact production bundles from SHA256-locked upstream files."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build(upstream, output):
    lock = json.loads((REPO / 'patches/versions.lock.json').read_text())
    upstream, output = Path(upstream), Path(output)
    with tempfile.TemporaryDirectory(prefix='pipeline-patches-') as work:
        work = Path(work)
        for name, spec in lock['bundles'].items():
            source = upstream / name
            if sha(source) != spec['original_sha256']:
                raise ValueError('upstream_sha256_mismatch:' + name)
            shutil.copyfile(source, work / name)
            subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i',
                str(REPO / 'patches' / spec['patch'])], cwd=work, check=True, capture_output=True)
            if sha(work / name) != spec['patched_sha256']:
                raise ValueError('patched_sha256_mismatch:' + name)
        output.mkdir(parents=True, exist_ok=True)
        for name, spec in lock['bundles'].items():
            target = output / name
            if target.exists() and sha(target) != spec['patched_sha256']:
                raise ValueError('refuse_to_overwrite_different_output:' + name)
        for name in lock['bundles']:
            shutil.copyfile(work / name, output / name)
    print(json.dumps({name: sha(output / name) for name in lock['bundles']}, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=REPO / 'build')
    args = parser.parse_args()
    build(args.upstream, args.output)
