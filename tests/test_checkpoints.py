"""Synthetic fixtures only: never compile or launch Firefox locally."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

checkpoint = load('checkpoint')
bounded = load('bounded')

class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.root, self.home, self.assets = base/'work', base/'home', base/'assets'
        for path in (self.root/'source/obj-refresh', self.root/'output', self.home/'.mozbuild', self.assets):
            path.mkdir(parents=True)
        (self.root/'source/.bootstrap-complete').touch()
        (self.root/'source/obj-refresh/object.fixture').write_bytes(b'completed synthetic object'*100)
        (self.root/'source/relative-link').symlink_to('obj-refresh/object.fixture')
        (self.home/'.mozbuild/toolchain.fixture').write_text('synthetic toolchain')
        self.expected_time = (self.root/'source/obj-refresh/object.fixture').stat().st_mtime_ns//10**9
        self.saved_identity = dict(schema=1, inputs_sha256='fixture-key', upstream='fixture-revision')
        self.real_run = subprocess.run
        def mock_run(args, **kwargs):
            if args[:3] == ['gh','release','create']:
                return subprocess.CompletedProcess(args, 0)
            if args[:3] == ['gh','release','upload']:
                shutil.copy2(Path(args[4]), self.assets/Path(args[4]).name)
                return subprocess.CompletedProcess(args, 0)
            if args[:3] == ['gh','release','download']:
                name=args[args.index('--pattern')+1]
                directory=Path(args[args.index('--dir')+1])
                shutil.copy2(self.assets/name, directory/name)
                return subprocess.CompletedProcess(args, 0)
            return self.real_run(args, **kwargs)
        self.patches = [patch.object(checkpoint, 'identity', return_value=self.saved_identity),
                        patch.object(checkpoint, 'source_digest', return_value='fixture-diff'),
                        patch.object(checkpoint.Path, 'home', return_value=self.home),
                        patch.object(checkpoint.subprocess, 'run', side_effect=mock_run),
                        patch.dict('os.environ', {'GITHUB_SHA':'fixture-sha'}),
                        patch.object(checkpoint, 'CHUNK_BYTES', 256)]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def save(self):
        checkpoint.save(self.root, 'checkpoint-123-1')
    def reset(self):
        shutil.rmtree(self.root/'source')
        shutil.rmtree(self.home/'.mozbuild')
    def test_streaming_round_trip_preserves_objects_symlinks_and_timestamps(self):
        self.save()
        manifest=json.loads((self.assets/'manifest.json').read_text())
        self.assertGreater(len(manifest['parts']), 1)
        self.reset()
        checkpoint.restore(self.root, 'checkpoint-123-1')
        obj=self.root/'source/obj-refresh/object.fixture'
        self.assertEqual(obj.read_bytes(), b'completed synthetic object'*100)
        self.assertEqual(obj.stat().st_mtime_ns//10**9, self.expected_time)
        self.assertTrue((self.root/'source/relative-link').is_symlink())
        self.assertEqual((self.home/'.mozbuild/toolchain.fixture').read_text(), 'synthetic toolchain')
    def test_corruption_is_rejected(self):
        self.save(); self.reset()
        (self.assets/'checkpoint.part0000').write_bytes(b'corrupt')
        with self.assertRaisesRegex(RuntimeError, 'Corrupt checkpoint'):
            checkpoint.restore(self.root, 'checkpoint-123-1')
    def test_identity_mismatch_rejected_before_extracting(self):
        self.save(); self.reset()
        manifest=json.loads((self.assets/'manifest.json').read_text())
        manifest['inputs_sha256']='wrong'
        (self.assets/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(RuntimeError, 'Incompatible checkpoint'):
            checkpoint.restore(self.root, 'checkpoint-123-1')
        self.assertFalse((self.root/'source').exists())
    def test_incomplete_bootstrap_is_not_published(self):
        (self.root/'source/.bootstrap-complete').unlink()
        with self.assertRaisesRegex(RuntimeError, 'Bootstrap not completed'):
            self.save()
        self.assertEqual(list(self.assets.iterdir()), [])
    def test_bounded_command_timeout_and_normal_exit(self):
        self.assertEqual(bounded.run([sys.executable,'-c','import sys; sys.exit(3)'],time.time()+5),3)
        self.assertEqual(bounded.run([sys.executable,'-c','import time; time.sleep(60)'],time.time()+0.2),75)

if __name__ == '__main__':unittest.main()
