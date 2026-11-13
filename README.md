# Mercury Refresh cloud build

Public build inputs for a personal experimental ARM64 Firefox derivative. Development artifacts are ad-hoc signed, not notarized. No memory improvement has been measured. Source revision: upstream.json; downstream changes: patches/series.

Only standard GitHub-hosted macos-26 runners are permitted. Do not switch to larger or self-hosted runners. No private repository credentials, profiles, or signing keys are used.

## Checkpointed compilation

Compilation/bootstrap are given 210 minutes from the job setup. At that deadline, the compiler process group is interrupted and remaining workers killed before archiving. The 350-minute job cap leaves roughly 140 minutes for snapshot transfer and diagnostics. A source checkout, object directory and ~/.mozbuild state are streamed into gzip level 1 and <=1 GiB Release chunks, with SHA-256 per chunk. The complete manifest is uploaded last. Only completed bootstrap state is resumable. No caches or Actions artifact storage are used.

Resume requires matching input hashes, pinned upstream revision, source modifications, Xcode, SDK, Python executable/version, OS/image, architecture, home and checkout paths. Mismatches fail visibly rather than silently reusing incompatible objects. Source/object timestamps and symlinks are retained by tar. Restoring a checkpoint is incremental compilation, not a saved running process: interrupted compilation units or linking restart. Build-system decisions may recompile additional work. This needs validation on a real Firefox checkpoint; synthetic archive/restore tests pass.

After a verified checkpoint upload, another standard free Mac job starts automatically, up to four segments. Continuation uses the checkpoint tag's exact project commit. A failed upload, ordinary compiler error, identity mismatch, hard job timeout, or fourth segment stops automation for review. Bootstrap that exceeds the deadline cannot yet be checkpointed. Compression/upload can still overrun the reserved time, so checkpointing cannot guarantee completion.

The initial non-checkpointed run 43481496635 is left untouched. A separate workflow starts the new pipeline only if that initial job reports timed_out; success and ordinary failures do not cause an automatic retry. That first timeout loses the initial run's intermediate work because its original workflow has no save hook. Later segments can retain completed work.

Manual recovery: dispatch build.yml with resume_tag=checkpoint-RUN_ID-ATTEMPT and generation=1 after reviewing a completed manifest. Keep the same project tag and runner image. Never run checkpoint data from an untrusted repository.

Tests (synthetic files and short-lived Python processes only): python3 -m unittest discover -s tests -v. No local Firefox compilation or browser launch is involved.
