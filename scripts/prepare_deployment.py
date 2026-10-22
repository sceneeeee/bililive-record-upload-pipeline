#!/usr/bin/env python3
import os
"""Prepare an existing stack for an explicitly approved future maintenance window.

Does not restart services. Refuses an existing stage; the current production stage
must never be overwritten. Runtime snapshots stay on the target host.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil

REPO = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get('STACK_ROOT', '/opt/bililive-stack'))
STAGE = Path(os.environ.get('PATCH_STAGE', str(ROOT / 'patches/uploader-3.20.0')))
LEGACY_BACKUP = "BACKUP=ROOT/'backups/uploader-backup'"

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundles', type=Path, default=REPO / 'build')
    parser.add_argument('--prepare', action='store_true', help='write backup and stage, without applying')
    args = parser.parse_args()
    if not args.prepare:
        parser.error('Pass --prepare only on the intended deployment host')
    if not ROOT.is_absolute() or ROOT.resolve() != ROOT or STAGE.resolve() != STAGE:
        raise SystemExit('Root/stage must be absolute, without symlink components')
    stage_relative = STAGE.relative_to(ROOT)
    if len(stage_relative.parts) < 2 or stage_relative.parts[0] != 'patches':
        raise SystemExit('Stage must be a subdirectory of the stack patches directory')
    if STAGE.exists():
        raise SystemExit('Stage already exists; preserve its manifest, backups and approval markers')
    lock = json.loads((REPO / 'patches/versions.lock.json').read_text())
    for name, item in lock['bundles'].items():
        if sha(args.bundles / name) != item['patched_sha256']:
            raise SystemExit('bundle mismatch:' + name)
    # Only the known baseline layout is supported; never rewrite arbitrary Compose.
    original = (ROOT / 'compose.yaml').read_bytes()
    if original != (REPO / 'compose/compose.base.example.yaml').read_bytes():
        raise SystemExit('Compose differs from the audited baseline; review and adapt before preparation')
    required = ['.env', 'compose.yaml', 'recorder/config.json', 'data/appConfig.json', 'data/presets.json']
    for rel in required:
        if not (ROOT / rel).is_file():
            raise SystemExit('Missing local runtime configuration:' + rel)
    backup = ROOT / 'backups' / ('maintenance-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(mode=0o700, parents=True, exist_ok=False)
    for rel in required:
        target = backup / rel
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
        target.chmod(0o600)
    STAGE.mkdir(mode=0o700, parents=True)
    for name in lock['bundles']:
        shutil.copyfile(args.bundles / name, STAGE / name)
    patched = STAGE / 'compose.yaml.patched'
    patched.write_text((REPO / 'compose/compose.example.yaml').read_text().replace(
        './patches/uploader-3.20.0/', './' + stage_relative.as_posix() + '/'))
    manifest = {'original_compose_sha256': hashlib.sha256(original).hexdigest(),
        'patched_compose_sha256': sha(patched),
        'original_core_sha256': lock['bundles']['index-DQV9sVEn.cjs']['original_sha256'],
        'original_server_sha256': lock['bundles']['index-ZJeYopVC.cjs']['original_sha256'],
        'patch_sha256': {n: v['patched_sha256'] for n, v in lock['bundles'].items()}}
    (STAGE / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    script = (REPO / 'scripts/apply_uploader_patch.py').read_text()
    if script.count(LEGACY_BACKUP) != 1:
        raise SystemExit('Archived apply script changed; manual compatibility review required')
    # Sole generated change: point the archived guard at this new private backup.
    script = script.replace(LEGACY_BACKUP, 'BACKUP=pathlib.Path(' + repr(str(backup)) + ')')
    script = script.replace("ROOT=pathlib.Path(os.environ.get('STACK_ROOT', '/opt/bililive-stack'))", 'ROOT=pathlib.Path(' + repr(str(ROOT)) + ')')
    script = script.replace("STAGE=pathlib.Path(os.environ.get('PATCH_STAGE', str(ROOT/'patches/uploader-3.20.0')))", 'STAGE=pathlib.Path(' + repr(str(STAGE)) + ')')
    (STAGE / 'apply.py').write_text(script)
    (STAGE / 'apply.py').chmod(0o750)
    for name in ['upload-streams-and-path.patch', 'immediate-upload.patch']:
        shutil.copyfile(REPO / 'patches' / name, STAGE / name)
    (backup / 'preparation.json').write_text(json.dumps({'stage': str(STAGE), 'backup': str(backup),
        'apply_script_sha256': sha(STAGE / 'apply.py'), 'manifest': manifest}, indent=2))
    (backup / 'preparation.json').chmod(0o600)
    print('Prepared, NOT applied. Private backup:', backup)
    print('Review stage, then explicitly approve running its apply.py --approved-window')

if __name__ == '__main__':
    main()
