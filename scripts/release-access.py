"""Fail before compilation if fixed release/tag or asset upload access is wrong."""
import json
import os
from pathlib import Path
import re
import subprocess

def gh(*args):return subprocess.check_output(['gh',*args],text=True).strip()
repo=os.environ['GITHUB_REPOSITORY']
assert repo=='senrishi/mercury-refresh-build'
assert json.loads(gh('api','repos/'+repo))['private'] is False
release=os.environ['RELEASE_TAG']
assert re.fullmatch(r'(verify|build)-[0-9a-f]{12}-\d+',release), 'Run scripts/dispatch.py first'
ref=json.loads(gh('api',f'repos/{repo}/git/ref/tags/{release}'))
assert ref['object']['type']=='commit' and ref['object']['sha']==os.environ['GITHUB_SHA'], 'Release tag must match workflow revision'
existing=json.loads(gh('release','view',release,'--json','isDraft'))
assert existing['isDraft'], 'Use a fresh draft release for each build'
Path('output').mkdir(exist_ok=True)
probe=Path('output')/f'upload-probe-{os.environ["GITHUB_RUN_ID"]}-{os.environ["GITHUB_RUN_ATTEMPT"]}.json'
probe.write_text(json.dumps({'run_id':os.environ['GITHUB_RUN_ID'],'sha':os.environ['GITHUB_SHA'],'upload_permission':'verified by successful upload'})+'\n')
gh('release','upload',release,str(probe),'--clobber')
print('Fixed tag, draft release and CI upload permission verified before compilation.',flush=True)
