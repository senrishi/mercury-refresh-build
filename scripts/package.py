import os, pathlib, plistlib, subprocess, tempfile
assert os.environ.get("GITHUB_ACTIONS") == "true", "Cloud execution only"
root=pathlib.Path.cwd()
dist=root/"source/obj-refresh/dist"
archives=list(dist.glob("*.tar.*"))+list(dist.glob("*.tar"))
assert len(archives)==1, f"Expected one mach package tar archive: {archives}"
with tempfile.TemporaryDirectory() as d:
 subprocess.run(["tar","-xf",str(archives[0]),"-C",d],check=True)
 apps=list(pathlib.Path(d).rglob("*.app"))
 app=next(a for a in apps if (a/"Contents/MacOS").is_dir())
 for p in app.rglob("*"):
  if p.is_symlink():
   assert p.resolve().is_relative_to(app.resolve()), f"External symlink: {p}"
 info=plistlib.loads((app/"Contents/Info.plist").read_bytes())
 assert info["CFBundleIdentifier"]=="io.github.senrishi.mercuryrefresh"
 # Sign nested Mach-O leaves before the outer bundle. Development identity only.
 for p in sorted(app.rglob("*"), key=lambda p:len(p.parts), reverse=True):
  if p.is_file() and not p.is_symlink():
   kind=subprocess.check_output(["file","-b",str(p)],text=True)
   if "Mach-O" in kind: subprocess.run(["codesign","--force","--sign","-",str(p)],check=True)
 subprocess.run(["codesign","--force","--deep","--sign","-",str(app)],check=True)
 subprocess.run(["codesign","--verify","--deep","--strict",str(app)],check=True)
 with tempfile.TemporaryDirectory() as profile:
  exe=app/"Contents/MacOS"/info["CFBundleExecutable"]
  subprocess.run([str(exe),"--headless","--no-remote","--profile",profile,"--screenshot",str(root/"output/smoke.png"),"about:blank"],check=True,timeout=120)
 subprocess.run(["ditto","-c","-k","--sequesterRsrc","--keepParent",str(app),str(root/"output/MercuryRefresh-arm64-development.zip")],check=True)
