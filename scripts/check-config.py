"""Check identity using the actual pinned Firefox configure function before compiling."""
import ast
import json
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.request

root=Path(__file__).resolve().parents[1]
lock=json.loads((root/'upstream.json').read_text())
product=json.loads((root/'product.json').read_text())
def upstream(path):
    return urllib.request.urlopen(f"https://raw.githubusercontent.com/mozilla-firefox/firefox/{lock['revision']}/{path}",timeout=60).read().decode()
with tempfile.TemporaryDirectory() as d:
    path=Path(d)/'browser/branding/unofficial/configure.sh'
    path.parent.mkdir(parents=True)
    path.write_text(upstream('browser/branding/unofficial/configure.sh'))
    for name in (root/'patches/series').read_text().splitlines():
        if name and not name.startswith('#'):
            subprocess.run(['git','apply','--check',str(root/'patches'/name)],cwd=d,check=True)
            subprocess.run(['git','apply',str(root/'patches'/name)],cwd=d,check=True)
    branding=path.read_text()
    suffix=re.search(r'^MOZ_MACBUNDLE_ID=(.+)$',branding,re.M).group(1)
    display=re.search(r'^MOZ_APP_DISPLAYNAME=(.+)$',branding,re.M).group(1)
config=(root/'config/mozconfig').read_text()
prefix=re.search(r'--with-distribution-id=(\S+)',config).group(1)
executable=re.search(r'--with-app-name=(\S+)',config).group(1)
tree=ast.parse(upstream('toolkit/moz.configure'))
function=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='moz_mac_bundle_id')
function.decorator_list=[]
namespace={'re':re}
exec(compile(ast.Module(body=[function],type_ignores=[]),'pinned-firefox-bundle-id','exec'),namespace)
actual=namespace['moz_mac_bundle_id']([suffix],display,[prefix],False)
if (actual,display,executable)!=(product['bundle_id'],product['app_name'],product['executable']):
    raise SystemExit(f'Identity mismatch before compilation: {actual}, {display}, {executable}')
print(f'Pinned Firefox identity rule verified: {actual}; executable={executable}')
