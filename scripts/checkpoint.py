"""Stream stopped build state into <=1 GiB release chunks; manifest commits last."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

CHUNK_BYTES = 1024**3
SCHEMA = 1


def command(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def identity(root):
    files = [root/'upstream.json', root/'product.json', root/'config/mozconfig', root/'patches/series']
    files += sorted((root/'patches').glob('*.patch'))
    files += sorted((root/'scripts').glob('*.py')) + [root/'scripts/build.sh']
    digest = hashlib.sha256()
    for file in files:
        digest.update(str(file.relative_to(root)).encode()+b'\0'+file.read_bytes()+b'\0')
    return dict(schema=SCHEMA, inputs_sha256=digest.hexdigest(),
                upstream=json.loads((root/'upstream.json').read_text())['revision'],
                workspace=str(root.resolve()), home=str(Path.home().resolve()),
                architecture=platform.machine(), image=os.environ.get('ImageVersion'),
                os_version=command('sw_vers', '-productVersion'),
                xcode=command('xcodebuild', '-version'), sdk=command('xcrun', '--show-sdk-version'),
                python=sys.version, python_executable=sys.executable)


def source_digest(root):
    revision = json.loads((root/'upstream.json').read_text())['revision']
    actual = command('git', '-C', str(root/'source'), 'rev-parse', 'HEAD')
    if actual != revision:
        raise RuntimeError('Source HEAD differs from pinned revision')
    diff = subprocess.check_output(['git', '-C', str(root/'source'), 'diff', '--binary', 'HEAD'])
    return hashlib.sha256(diff).hexdigest()


def upload(tag, path):
    subprocess.run(['gh', 'release', 'upload', os.environ['RELEASE_TAG'], str(path)], check=True)


def save(root, tag):
    if not (root/'source/.bootstrap-complete').exists():
        raise RuntimeError('Bootstrap not completed: no resumable checkpoint will be published')
    metadata = identity(root)
    metadata['source_diff_sha256'] = source_digest(root)
    release = os.environ['RELEASE_TAG']
    env = dict(os.environ, COPYFILE_DISABLE='1')
    tar = subprocess.Popen(['tar', '-cf', '-', '-C', str(root), 'source',
                            '-C', str(Path.home()), '.mozbuild'], stdout=subprocess.PIPE, env=env)
    gzip = subprocess.Popen(['gzip', '-1'], stdin=tar.stdout, stdout=subprocess.PIPE)
    tar.stdout.close()
    parts = []
    try:
        with tempfile.TemporaryDirectory(prefix='checkpoint-save-') as directory:
            while True:
                part = Path(directory)/f'{tag}.part{len(parts):04d}'
                digest = hashlib.sha256()
                size = 0
                with part.open('wb') as target:
                    while size < CHUNK_BYTES:
                        data = gzip.stdout.read(min(4*1024**2, CHUNK_BYTES-size))
                        if not data:
                            break
                        target.write(data)
                        digest.update(data)
                        size += len(data)
                if not size:
                    part.unlink()
                    break
                upload(tag, part)
                parts.append(dict(name=part.name, bytes=size, sha256=digest.hexdigest()))
                part.unlink()  # Never retain a second full compressed archive on the runner.
                if len(parts) >= 900:
                    raise RuntimeError('Checkpoint exceeds safety bound')
            if gzip.wait() != 0 or tar.wait() != 0:
                raise RuntimeError('Archive creation failed; checkpoint is incomplete')
            metadata['parts'] = parts
            metadata['complete'] = True
            manifest = Path(directory)/(tag+'-manifest.json')
            manifest.write_text(json.dumps(metadata, indent=2)+'\n')
            upload(tag, manifest)  # Commit marker: only upload after all chunks succeeded.
        (root/'output/checkpoint.json').write_text(json.dumps(dict(tag=tag, complete=True, parts=len(parts)), indent=2)+'\n')
    finally:
        gzip.stdout.close()
        for process in (gzip, tar):
            if process.poll() is None:
                process.kill()
                process.wait()


def restore(root, tag):
    if not re.fullmatch(r'checkpoint-\d+-\d+', tag):
        raise ValueError('Invalid checkpoint tag')
    if (root/'source').exists() or (root/'.mozbuild').exists():
        raise RuntimeError('Restore requires empty destination')
    with tempfile.TemporaryDirectory(prefix='checkpoint-restore-') as directory:
        def download(name):
            path = Path(directory)/name
            subprocess.run(['gh', 'release', 'download', os.environ['RELEASE_TAG'], '--pattern', name, '--dir', directory], check=True)
            return path
        manifest = json.loads(download(tag+'-manifest.json').read_text())
        if not manifest.get('complete'):
            raise RuntimeError('Checkpoint has no complete manifest')
        expected = identity(root)
        for key, value in expected.items():
            if manifest.get(key) != value:
                raise RuntimeError(f'Incompatible checkpoint: {key}: saved={manifest.get(key)!r}, current={value!r}. Start a clean build.')
        parts = manifest.get('parts', [])
        if not 0 < len(parts) < 900:
            raise RuntimeError('Invalid checkpoint part count')
        tar = subprocess.Popen(['tar', '-xzf', '-', '-C', str(root)], stdin=subprocess.PIPE)
        try:
            for index, record in enumerate(parts):
                name = f'{tag}.part{index:04d}'
                if record['name'] != name or not 0 < record['bytes'] <= CHUNK_BYTES:
                    raise RuntimeError('Invalid part manifest')
                part = download(name)
                digest = hashlib.sha256()
                with part.open('rb') as file:
                    for data in iter(lambda: file.read(4*1024**2), b''):
                        digest.update(data)
                if part.stat().st_size != record['bytes'] or digest.hexdigest() != record['sha256']:
                    raise RuntimeError(f'Corrupt checkpoint chunk: {name}')
                with part.open('rb') as file:
                    shutil.copyfileobj(file, tar.stdin, length=4*1024**2)
                part.unlink()
            tar.stdin.close()
            if tar.wait() != 0:
                raise RuntimeError('Checkpoint extraction failed')
        finally:
            if not tar.stdin.closed:
                tar.stdin.close()
            if tar.poll() is None:
                tar.kill()
                tar.wait()
        if source_digest(root) != manifest['source_diff_sha256']:
            raise RuntimeError('Restored source diff differs from saved state')
        state = Path.home()/'.mozbuild'
        if state.exists():
            # Fresh ephemeral cloud runner only; do not merge stale toolchain state.
            shutil.rmtree(state)
        shutil.move(str(root/'.mozbuild'), state)
        (root/'output/restored-checkpoint.json').write_text(json.dumps(dict(tag=tag, verified=True), indent=2)+'\n')


if __name__ == '__main__':
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Cloud only'
    assert os.environ.get('GITHUB_REPOSITORY') == 'senrishi/mercury-refresh-build', 'Build repository only'
    mode, tag = sys.argv[1:]
    if mode not in ('save', 'restore'):
        raise ValueError(mode)
    globals()[mode](Path.cwd(), tag)
