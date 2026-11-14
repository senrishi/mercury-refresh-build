#!/bin/bash
set -euo pipefail
[[ "${GITHUB_ACTIONS:-}" == true ]] || { echo 'Cloud execution only'; exit 1; }
ROOT="$PWD"
# Upstream build notifications can hang on a headless hosted Mac.
export MOZ_NOSPAM=1
mkdir -p output
exec > >(tee -a "$ROOT/output/build.log") 2>&1
python3 scripts/preflight.py
REV=$(python3 -c 'import json; print(json.load(open("upstream.json"))["revision"])')
if [[ -n "${RESUME_TAG:-}" ]]; then
  python3 scripts/checkpoint.py restore "$RESUME_TAG"
else
  git init source
  git -C source remote add origin https://github.com/mozilla-firefox/firefox.git
  git -C source fetch --depth=1 origin "$REV"
  git -C source checkout --detach FETCH_HEAD
  [[ "$(git -C source rev-parse HEAD)" == "$REV" ]]
  while read -r patch; do
    [[ -z "$patch" || "$patch" == \#* ]] && continue
    git -C source apply --check "$ROOT/patches/$patch"
    git -C source apply "$ROOT/patches/$patch"
  done < patches/series
  cp config/mozconfig source/mozconfig
fi
export MOZCONFIG="$ROOT/source/mozconfig"
export MOZBUILD_STATE_PATH="$HOME/.mozbuild"
cd source
if [[ ! -f .bootstrap-complete ]]; then
  python3 "$ROOT/scripts/bounded.py" ./mach --no-interactive bootstrap --application-choice=browser
  touch .bootstrap-complete
fi
python3 "$ROOT/scripts/bounded.py" ./mach build
./mach package
cd "$ROOT"
python3 scripts/package.py
cp upstream.json config/mozconfig output/
python3 - <<'PROVENANCE'
import json, os, pathlib, subprocess
p=dict(project_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(), upstream=json.load(open('upstream.json')),run_url=f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}", signing="ad-hoc development; not notarized", xcode=subprocess.check_output(['xcodebuild','-version'],text=True),sdk=subprocess.check_output(['xcrun','--show-sdk-version'],text=True).strip())
pathlib.Path('output/provenance.json').write_text(json.dumps(p,indent=2)+'\n')
PROVENANCE
cp -R patches output/patches
cp LICENSE output/LICENSE
shasum -a 256 output/*.zip > output/SHA256SUMS
