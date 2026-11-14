"""Validate, ad-hoc sign, smoke-test and archive Firefox mach's DMG output."""
import os
import pathlib
import plistlib
import shutil
import subprocess
import tempfile

assert os.environ.get("GITHUB_ACTIONS") == "true", "Cloud execution only"
root=pathlib.Path.cwd()
dist=root/"source/obj-refresh/dist"
dmgs=list(dist.glob("mercury-refresh-*.dmg"))
assert len(dmgs)==1, f"Expected one MercuryRefresh DMG from mach package: {dmgs}"
with tempfile.TemporaryDirectory(prefix="mercury-refresh-package-") as temporary:
    base=pathlib.Path(temporary)
    mount=base/"mounted"
    mount.mkdir()
    subprocess.run(["hdiutil","attach","-readonly","-nobrowse","-mountpoint",str(mount),str(dmgs[0])],check=True,timeout=120)
    try:
        apps=[p for p in mount.rglob("*.app") if (p/"Contents/MacOS").is_dir()]
        assert len(apps)==1, f"Expected one packaged browser app in DMG: {apps}"
        source=apps[0]
        for p in source.rglob("*"):
            if p.is_symlink():
                assert p.resolve().is_relative_to(source.resolve()), f"External symlink: {p}"
        info=plistlib.loads((source/"Contents/Info.plist").read_bytes())
        assert info["CFBundleIdentifier"]=="io.github.senrishi.mercuryrefresh", info["CFBundleIdentifier"]
        app=base/"MercuryRefresh.app"
        shutil.copytree(source,app,symlinks=True)
        # Ad-hoc signatures make nested code runnable for development; they are not notarization.
        for item in sorted(app.rglob("*"),key=lambda p:len(p.parts),reverse=True):
            if item.is_file() and not item.is_symlink():
                kind=subprocess.check_output(["file","-b",str(item)],text=True)
                if "Mach-O" in kind:
                    subprocess.run(["codesign","--force","--sign","-",str(item)],check=True,timeout=60)
        subprocess.run(["codesign","--force","--deep","--sign","-",str(app)],check=True,timeout=120)
        subprocess.run(["codesign","--verify","--deep","--strict",str(app)],check=True,timeout=120)
        exe=app/"Contents/MacOS"/info["CFBundleExecutable"]
        with tempfile.TemporaryDirectory(prefix="mercury-refresh-profile-") as profile:
            subprocess.run([str(exe),"--headless","--no-remote","--profile",profile,"--screenshot",str(root/"output/smoke.png"),"about:blank"],check=True,timeout=120)
        subprocess.run(["ditto","-c","-k","--sequesterRsrc","--keepParent",str(app),str(root/"output/MercuryRefresh-arm64-development.zip")],check=True)
    finally:
        subprocess.run(["hdiutil","detach",str(mount),"-force"],check=True,timeout=60)
