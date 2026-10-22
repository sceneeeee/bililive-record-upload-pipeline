import ast
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('preparation', REPO / 'scripts/prepare_deployment.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class PreparationTests(unittest.TestCase):
    def test_reproducible_stage_and_private_backup_without_changing_stack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'stack'
            root.mkdir()
            for rel in ['.env', 'compose.yaml', 'recorder/config.json', 'data/appConfig.json', 'data/presets.json']:
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes((REPO / 'compose/compose.base.example.yaml').read_bytes() if rel == 'compose.yaml' else b'{}')
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            stage = root / 'patches/uploader-3.20.0'
            with patch.object(module, 'ROOT', root), patch.object(module, 'STAGE', stage), patch.object(sys, 'argv', ['prepare', '--prepare']), contextlib.redirect_stdout(io.StringIO()):
                module.main()
            for rel, data in before.items():
                self.assertEqual((root / rel).read_bytes(), data)
            manifest = json.loads((stage / 'manifest.json').read_text())
            lock = json.loads((REPO / 'patches/versions.lock.json').read_text())
            for name, item in lock['bundles'].items():
                self.assertEqual(module.sha(stage / name), item['patched_sha256'])
                self.assertEqual(manifest['patch_sha256'][name], item['patched_sha256'])
            generated = (stage / 'apply.py').read_text()
            ast.parse(generated)
            backup = next((root / 'backups').iterdir())
            self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
            for rel, data in before.items():
                self.assertEqual((backup / rel).read_bytes(), data)
                self.assertEqual((backup / rel).stat().st_mode & 0o777, 0o600)
            self.assertIn('BACKUP=pathlib.Path(' + repr(str(backup)) + ')', generated)
            self.assertFalse((stage / 'approved.json').exists())

    def test_existing_stage_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage = root / 'patches/uploader-3.20.0'
            stage.mkdir(parents=True)
            marker = stage / 'applied.json'
            marker.write_text('{}')
            with patch.object(module, 'ROOT', root), patch.object(module, 'STAGE', stage), patch.object(sys, 'argv', ['prepare', '--prepare']):
                with self.assertRaisesRegex(SystemExit, 'Stage already exists'):
                    module.main()
            self.assertEqual(marker.read_text(), '{}')
            self.assertFalse((root / 'backups').exists())

if __name__ == '__main__':
    unittest.main()
