#!/usr/bin/env python3
"""Review tracked/index/history blobs; never print matching secret values."""
import argparse
import re
from pathlib import PurePosixPath
import subprocess

PATTERNS = [
    ('private_key', re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ('github_token', re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,})\b')),
    ('aws_access_key', re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b')),
    ('jwt', re.compile(rb'\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\b')),
    ('cookie_value', re.compile(rb'(?i)\b(?:SESSDATA|bili_jct|DedeUserID__ckMd5)\s*[=:]\s*["\x27]?[A-Za-z0-9%_-]{10,}')),
    ('url_credentials', re.compile(rb'https?://[^\s/:"\x27]+:[^\s/@"\x27]+@')),
    ('literal_credential', re.compile(rb'(?im)^\s*["\x27]?(?:password|passwd|token|secret|api_key|BILILIVE_TOOLS_PASSKEY|BILILIVE_TOOLS_BILIKEY|BREC_HTTP_BASIC_PASS)["\x27]?\s*[:=]\s*["\x27]([A-Za-z0-9_%/+=.-]{8,})["\x27]')),
]
FORBIDDEN_DIRS = {'.ssh', '.aws', '.codex', '.agents', 'data', 'video', 'cover', 'backups', 'logs', 'audit', 'evidence', 'state', 'node_modules', '__pycache__', 'build'}
FORBIDDEN_EXT = {'.flv', '.mp4', '.mkv', '.m4s', '.db', '.sqlite', '.sqlite3', '.log', '.jsonl', '.tar', '.zip', '.pem', '.key', '.pyc'}

def git(*args):
    return subprocess.check_output(['git', *args])

def findings(name, data):
    p = PurePosixPath(name)
    result = []
    if (p.name == 'temp_report.md' or (p.name.startswith('.env') and p.name != '.env.example')
            or ('recorder' in p.parts and p.parts[:2] != ('examples', 'recorder'))
            or p.suffix.lower() in FORBIDDEN_EXT or set(p.parts) & FORBIDDEN_DIRS
            or p.name.startswith(('id_rsa', 'id_ed25519', 'patched-tools-', 'reference-tools-'))
            or re.fullmatch(r'index-.*\.cjs', p.name)
            or re.search(r'\.(?:db|sqlite3?)-(?:wal|shm|journal)$', p.name)):
        result.append('forbidden_filename')
    if len(data) > 256 * 1024:
        result.append('oversized_or_vendor_bundle')
    if b'\0' in data:
        result.append('binary_blob')
    for label, pattern in PATTERNS:
        if pattern.search(data):
            result.append(label)
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staged', action='store_true')
    parser.add_argument('--history', action='store_true')
    args = parser.parse_args()
    items = []
    if args.history:
        for line in git('rev-list', '--objects', '--all').decode().splitlines():
            sha, _, name = line.partition(' ')
            if name and git('cat-file', '-t', sha).strip() == b'blob':
                items.append((name, git('cat-file', 'blob', sha)))
    else:
        for entry in git('ls-files', '--stage', '-z').split(b'\0'):
            if not entry:
                continue
            meta, raw = entry.split(b'\t', 1)
            mode, _, stage = meta.split()
            if stage != b'0':
                raise SystemExit('unresolved_index')
            if mode == b'160000':
                continue  # Scan each pinned submodule repository separately.
            if mode not in {b'100644', b'100755'}:
                raise SystemExit('non_regular_index_file')
            name = raw.decode()
            data = git('show', ':' + name) if args.staged else open(name, 'rb').read()
            items.append((name, data))
    failures = [(name, findings(name, data)) for name, data in items]
    failures = [(name, reasons) for name, reasons in failures if reasons]
    for name, reasons in failures:
        print(name + ': ' + ','.join(reasons))
    if failures:
        raise SystemExit(1)
    print(f'PASS: {len(items)} blobs reviewed; no forbidden files or credential patterns')

if __name__ == '__main__':
    main()
