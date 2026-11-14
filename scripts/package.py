"""Verify mach's packaged DMG and stage the original DMG for personal use."""
import os
import pathlib
import plistlib
import subprocess
import tempfile

assert os.environ.get("GITHUB_ACTIONS") == "true", "Cloud execution only"
root=pathlib.Path.cwd()
dist=root/"source/obj-refresh/dist"
dmgs=list(dist.glob("mercury-refresh-*.dmg"))
assert len(dmgs)==1, f"Expected one MercuryRefresh DMG from mach package: {dmgs}"
dmg=dmgs[0]
subprocess.run(["hdiutil","verify",str(dmg)],check=True,timeout=180)
with tempfile.TemporaryDirectory(prefix="mercury-refresh-package-") as temporary:
    mount=pathlib.Path(temporary)/"mounted"
    mount.mkdir()
    subprocess.run(["hdiutil","attach","-readonly","-nobrowse","-mountpoint",str(mount),str(dmg)],check=True,timeout=120)
    try:
        apps=[p for p in mount.glob("*.app") if (p/"Contents/MacOS").is_dir()]
        assert len(apps)==1, f"Expected one top-level packaged browser app in DMG: {apps}"
        app=apps[0]
        for item in app.rglob("*"):
            if item.is_symlink():
                assert item.resolve().is_relative_to(app.resolve()), f"External symlink: {item}"
        info=plistlib.loads((app/"Contents/Info.plist").read_bytes())
        assert info["CFBundleIdentifier"]=="io.github.senrishi.mercuryrefresh", info["CFBundleIdentifier"]
        assert info["CFBundleExecutable"] and (app/"Contents/MacOS"/info["CFBundleExecutable"]).is_file()
        target=root/"output/MercuryRefresh-arm64-development.dmg"
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(dmg.read_bytes())
    finally:
        subprocess.run(["hdiutil","detach",str(mount),"-force"],check=True,timeout=60)
