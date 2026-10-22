import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('builder', REPO / 'scripts/build_patches.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

class PatchBuildTests(unittest.TestCase):
    def test_unknown_upstream_is_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            upstream = root / 'upstream'
            upstream.mkdir()
            for name in json.loads((REPO / 'patches/versions.lock.json').read_text())['bundles']:
                (upstream / name).write_text('wrong version')
            with self.assertRaisesRegex(ValueError, 'upstream_sha256_mismatch'):
                builder.build(upstream, root / 'output')
            self.assertFalse((root / 'output').exists())

if __name__ == '__main__':
    unittest.main()
