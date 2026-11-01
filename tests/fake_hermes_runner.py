"""Stands in for hermes_isolated.py in tests. Behaviour chosen by the prompt text."""
import os, subprocess, sys, time
wd = sys.argv[1]; prompt = sys.stdin.read()
if "MODE=ok" in prompt:
    print('{"title": "ok", "n": 1}')
elif "MODE=err" in prompt:
    sys.stderr.write("hermes_isolated: RuntimeError\n"); sys.exit(4)
elif "MODE=empty" in prompt:
    sys.stderr.write("hermes_isolated: empty response\n"); sys.exit(3)
elif "MODE=hang" in prompt:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
    open(os.path.join(os.environ["HIP_TEST_PIDFILE"]), "w").write(str(child.pid))
    time.sleep(300)
elif "MODE=flood" in prompt:
    sys.stdout.write("x" * 5_000_000); sys.stdout.flush(); time.sleep(30)
