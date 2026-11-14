# Mercury Refresh cloud builds

Experimental personal ARM64 Firefox derivative; source pin in upstream.json, identity in product.json, ordered patches in patches/series. No memory or speed improvement has been measured. No Developer ID signing or notarization. Binary linker ad-hoc signatures are retained. Never reuse an everyday profile.

## Execution and zero spending

Only the public repository's standard `macos-26` runner is used. Jobs refuse private repositories. No larger runner, self-hosted Mac, Actions artifact uploads or cache charges. Never compile Firefox locally.

Prepare an immutable tag and draft release **before** dispatching:

```
python3 scripts/dispatch.py verify
python3 scripts/dispatch.py build
```

The dispatch script uses existing local gh credentials only to prepare the fixed tag/release and dispatch a cloud workflow. It does not compile or upload credentials. CI receives only the built-in GitHub token, verifies release upload access before compilation, and uploads into the existing release. This avoids GitHub restrictions on creating tags for historical workflow-changing commits when main moves during a long build.

`verify` runs synthetic DMG checks on a cloud Mac without compiling or launching Firefox. It verifies nested helper handling, identity rejection, missing executable rejection, external symlink rejection and damaged-image rejection. Test outputs remain in a draft release and are clearly labeled synthetic.

`build` checks patch application and runs the pinned Firefox bundle-ID calculation before fetching the full source. It compiles, uses `mach package` to create the standalone DMG, and copies an `UNVALIDATED-...dmg` into the draft release staging area **before** custom validation. Disk checksum, top-level app selection, bundle ID, executable and symlink containment are verified. On success the original DMG is published with validation metadata, provenance, source revision, logs, license and SHA256SUMS. On a downstream validation failure the raw package and diagnostics stay in the draft release so work is not discarded. It is not an approved browser artifact until validation passes.

## Checkpoints

After 210 minutes of bootstrap/compilation the worker group is stopped. Approximately 140 minutes remain under the 350-minute job limit to stream source, object directory and ~/.mozbuild into <=1 GiB gzip chunks. Checkpoints upload into the already-prepared draft release using a unique `checkpoint-RUN-ATTEMPT` key. Each part has a SHA-256 and size; the complete manifest uploads last. Incomplete checkpoints cannot be restored.

Resume requires exact source revision, build-input hash, image/OS, Xcode/SDK, Python, architecture and checkout/home paths. Archives preserve source/object timestamps and symlinks. Interrupted compile or link operations restart. A complete checkpoint automatically dispatches the next segment on the fixed tag with the same release, capped at four segments. Failures stop automation. Checkpoint code is covered by synthetic round-trip/corruption/mismatch tests; actual Firefox checkpoint restore still awaits a cloud checkpoint.

## Personal installation

The pipeline does not re-sign or launch the browser. macOS may require per-app approval because the app is not notarized. Copy MercuryRefresh.app from the DMG to Applications and use an isolated profile:

```sh
mkdir -p "$HOME/Library/Application Support/MercuryRefresh-Test"
open -na /Applications/MercuryRefresh.app --args --no-remote --profile "$HOME/Library/Application Support/MercuryRefresh-Test"
```

Available security features, extension behavior and performance still need validation. Auto-updating is disabled pending a signed update service. Install updates manually.
