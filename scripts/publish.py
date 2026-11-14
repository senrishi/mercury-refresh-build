"""Upload regular files exactly once; no tag creation from CI credentials."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

root=Path.cwd()
out=root/'output'
out.mkdir(exist_ok=True)
tag=os.environ['RELEASE_TAG']
result=os.environ.get('RESULT','failure')
mode=os.environ.get('BUILD_MODE','build')
(out/'RESULT.txt').write_text(f'Job status: {result}; mode: {mode}\nDevelopment files. No Developer ID signing or notarization. Failed/unvalidated files are diagnostics only.\n')
for name in ('upstream.json','product.json','LICENSE'):
    (out/name).write_bytes((root/name).read_bytes())
log=out/'build.log'
if log.exists():
    subprocess.run(['gzip','-f',str(log)],check=True)
# Include all regular files (also extensionless names); never hash a manifest into itself.
files=sorted(p for p in out.iterdir() if p.is_file() and p.name!='SHA256SUMS')
manifest=out/'SHA256SUMS'
with manifest.open('w') as target:
    for path in files:
        with path.open('rb') as source:
            digest=hashlib.file_digest(source,'sha256').hexdigest()
        target.write(f'{digest}  {path.name}\n')
files.append(manifest)
for path in files:
    subprocess.run(['gh','release','upload',tag,str(path),'--clobber'],check=True)
if result=='success' and mode=='build' and (out/'MercuryRefresh-arm64-development.dmg').exists():
    subprocess.run(['gh','release','edit',tag,'--draft=false','--prerelease','--title','MercuryRefresh ARM64 development — '+tag,'--notes-file',str(out/'RESULT.txt')],check=True)
print('Uploaded unique release assets:', ', '.join(p.name for p in files),flush=True)
