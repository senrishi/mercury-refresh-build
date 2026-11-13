"""Run a process group until the build deadline; stop workers before snapshotting."""
import os
import signal
import subprocess
import sys
import time


def run(command, deadline):
    remaining = deadline - time.time()
    if remaining <= 0:
        return 75
    environment = dict(os.environ)
    # Build-system state is public in checkpoints; do not pass CI credentials to compilers.
    for key in ('GH_TOKEN', 'GITHUB_TOKEN', 'ACTIONS_RUNTIME_TOKEN', 'ACTIONS_ID_TOKEN_REQUEST_TOKEN'):
        environment.pop(key, None)
    process = subprocess.Popen(command, start_new_session=True, env=environment)
    try:
        return process.wait(timeout=remaining)
    except subprocess.TimeoutExpired:
        print('Checkpoint deadline reached; interrupting compiler process group.', flush=True)
        try:
            os.killpg(process.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            pass
        # Kill remaining descendants even if the parent exited first.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        return 75


if __name__ == '__main__':
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Cloud only'
    sys.exit(run(sys.argv[1:], float(os.environ['BUILD_DEADLINE'])))
