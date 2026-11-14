"""Prepare a fixed tag/release with gh credentials, then dispatch cloud work. Never compiles."""
import argparse
import json
from pathlib import Path
import subprocess
import time

repo='senrishi/mercury-refresh-build'
def gh(*args):return subprocess.check_output(['gh',*args],text=True).strip()
parser=argparse.ArgumentParser()
parser.add_argument('mode',choices=['verify','build'])
a=parser.parse_args()
info=json.loads(gh('api','repos/'+repo))
assert info['private'] is False, 'Only public standard runners are authorized'
sha=gh('api','repos/'+repo+'/commits/main','--jq','.sha')
tag=f'{a.mode}-{sha[:12]}-{int(time.time())}'
gh('api','--method','POST','repos/'+repo+'/git/refs','-f','ref=refs/tags/'+tag,'-f','sha='+sha)
gh('release','create',tag,'-R',repo,'--verify-tag','--draft','--prerelease','--title',tag+' — pending cloud validation','--notes','Cloud development build. Not Developer ID signed or notarized. Incomplete and failed artifacts remain draft diagnostics.')
print('Prepared fixed release:',tag,flush=True)
print(gh('workflow','run','build.yml','-R',repo,'--ref',tag,'-f','release_tag='+tag,'-f','mode='+a.mode,'-f','generation=1'),flush=True)
