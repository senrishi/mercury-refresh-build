"""Mac-only synthetic DMG regression checks; no Firefox compilation or launch."""
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

assert os.environ.get('GITHUB_ACTIONS')=='true', 'Cloud only'
root=Path.cwd()
product=json.loads((root/'product.json').read_text())
dist=root/'source/obj-refresh/dist'
dist.mkdir(parents=True,exist_ok=True)
results=[]
with tempfile.TemporaryDirectory() as temporary:
    base=Path(temporary)
    for scenario in ('valid-nested-helpers','wrong-id','missing-executable','external-symlink','corrupt-dmg'):
        fixture=base/scenario
        app=fixture/'MercuryRefresh.app'
        binary=app/'Contents/MacOS'/product['executable']
        binary.parent.mkdir(parents=True)
        if scenario!='missing-executable':
            binary.write_text('synthetic fixture only; not executable browser code\n')
        info={'CFBundleIdentifier':product['bundle_id'] if scenario!='wrong-id' else 'incorrect.id',
              'CFBundleExecutable':product['executable']}
        (app/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
        for helper in ('crashreporter','gpu-helper','media-plugin-helper','plugin-container'):
            child=app/'Contents/MacOS'/(helper+'.app')/'Contents/MacOS'
            child.mkdir(parents=True)
            (child/helper).write_text('synthetic helper')
        (app/'Contents/internal-link').symlink_to('MacOS')
        if scenario=='external-symlink':
            (app/'Contents/external-link').symlink_to('/Applications')
        dmg=dist/'mercury-refresh-fixture.dmg'
        if scenario=='corrupt-dmg':dmg.write_bytes(b'not a disk image')
        else:subprocess.run(['hdiutil','create','-srcfolder',str(fixture),'-volname','MercuryRefreshFixture','-format','UDZO',str(dmg)],check=True,stdout=subprocess.DEVNULL,timeout=120)
        result=subprocess.run([sys.executable,'scripts/package.py'],capture_output=True,text=True,timeout=300)
        expected=scenario=='valid-nested-helpers'
        if (result.returncode==0)!=expected:
            raise RuntimeError(f'{scenario}: unexpected status {result.returncode}\n{result.stdout}\n{result.stderr}')
        expected_message={'wrong-id':'incorrect.id','missing-executable':'AssertionError','external-symlink':'External symlink','corrupt-dmg':'hdiutil'}
        if not expected and expected_message[scenario] not in result.stderr:
            raise RuntimeError(f'{scenario}: failed for wrong reason: {result.stderr}')
        if expected:
            assert (root/'output/MercuryRefresh-arm64-development.dmg').read_bytes()==dmg.read_bytes()
        results.append(dict(scenario=scenario,passed=True))
        print(f'{scenario}: passed',flush=True)
        dmg.unlink()
        (root/'output/MercuryRefresh-arm64-development.dmg').unlink(missing_ok=True)
        (root/'output/validation.json').unlink(missing_ok=True)
(root/'output/packaging-regressions.json').write_text(json.dumps({'synthetic_only':True,'results':results},indent=2)+'\n')
