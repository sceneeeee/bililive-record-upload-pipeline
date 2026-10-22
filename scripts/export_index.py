#!/usr/bin/env python3
"""Export regular staged blobs to an empty directory for an external scanner."""
import argparse
from pathlib import Path, PurePosixPath
import subprocess

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    if args.destination.exists():
        raise SystemExit('Destination must not exist')
    args.destination.mkdir(mode=0o700,parents=True)
    for entry in subprocess.check_output(['git','ls-files','--stage','-z']).split(b'\0'):
        if not entry: continue
        metadata, name=entry.split(b'\t',1)
        mode, sha, stage=metadata.split()
        if stage!=b'0' or mode not in {b'100644',b'100755'}:
            raise SystemExit('Only regular files from a resolved index are supported')
        rel=PurePosixPath(name.decode())
        if rel.is_absolute() or '..' in rel.parts: raise SystemExit('Unsafe path')
        target=args.destination/str(rel)
        target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        target.write_bytes(subprocess.check_output(['git','cat-file','blob',sha.decode()]))
    print('Staged files exported; scan this directory and Git history separately')
if __name__=='__main__': main()
