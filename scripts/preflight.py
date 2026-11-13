import json, os, platform, shutil, subprocess, sys
from pathlib import Path
assert os.environ.get("GITHUB_ACTIONS") == "true", "Cloud execution only"
assert platform.machine() == "arm64", "ARM Mac required"
p = subprocess.run(["xcrun", "--sdk", "macosx", "--show-sdk-version"], capture_output=True, text=True)
free = shutil.disk_usage(".").free / 1024**3
memory = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"])) / 1024**3
result = dict(free_disk_gib=round(free,2), memory_gib=memory, sdk=p.stdout.strip(), runner_image=os.getenv("ImageVersion"), architecture=platform.machine())
Path("output").mkdir(exist_ok=True)
Path("output/preflight.json").write_text(json.dumps(result, indent=2)+"\n")
print(json.dumps(result, indent=2), flush=True)
errors=[]
if free < 30: errors.append(f"Disk shortfall: {30-free:.2f} GiB below Mozilla's 30 GB minimum (conservative GiB gate)")
if p.returncode or tuple(map(int,p.stdout.strip().split('.'))) < (26,5): errors.append("Pinned Firefox requires macOS SDK >=26.5; select a matching Xcode image")
if memory < 4: errors.append("Below Mozilla minimum RAM")
Path("output/preflight-errors.txt").write_text("\n".join(errors)+"\n")
if errors: sys.exit("; ".join(errors))
