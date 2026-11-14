"""Regression: extensionless checksums, unique uploads, and no directory uploads."""
import hashlib
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/publish.py'
class PublishTests(unittest.TestCase):
    def test_unique_assets_and_independent_checksums(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            output=root/'output'; output.mkdir()
            for name in ('LICENSE','product.json','upstream.json'):(root/name).write_text(name)
            (output/'file with spaces.dmg').write_bytes(b'synthetic package')
            (output/'SHA256SUMS').write_text('obsolete checksum content')
            (output/'directory').mkdir()
            uploads=[]
            def run(args,**kwargs):
                self.assertEqual(args[:3],['gh','release','upload'])
                uploads.append(Path(args[4]))
                return subprocess.CompletedProcess(args,0)
            with patch('pathlib.Path.cwd',return_value=root),patch.dict(os.environ,{'RELEASE_TAG':'fixture','RESULT':'failure','BUILD_MODE':'verify'}),patch('subprocess.run',side_effect=run):
                runpy.run_path(str(SCRIPT),run_name='__main__')
            names=[p.name for p in uploads]
            self.assertEqual(len(names),len(set(names)))
            self.assertIn('SHA256SUMS',names)
            self.assertIn('LICENSE',names)
            self.assertNotIn('directory',names)
            for line in (output/'SHA256SUMS').read_text().splitlines():
                digest,name=line.split('  ',1)
                self.assertNotEqual(name,'SHA256SUMS')
                self.assertEqual(hashlib.sha256((output/name).read_bytes()).hexdigest(),digest)
