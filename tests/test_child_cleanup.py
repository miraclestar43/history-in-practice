"""A stopped job must not leave a model process running (found 2026-10-30: a SIGTERM'd final-edit left `claude -p`
orphaned under systemd). SIGTERM -> SystemExit in the CLI; the adapters kill their child's process group in `finally`."""
import os, signal, subprocess, sys, tempfile, time, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


class ChildCleanup(unittest.TestCase):
    def test_sigterm_to_caller_kills_the_model_process_group(self):
        mark = f"sleep {500 + os.getpid() % 400}.{time.time_ns() % 10**6:06d}"   # unique: appears in no other command line
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "claude"; fake.write_text(f"#!/bin/sh\nexec {mark}\n"); fake.chmod(0o755)
            code = ("import signal,sys; sys.path.insert(0,'src'); signal.signal(signal.SIGTERM, lambda *_: sys.exit(143)); "
                    "from history_in_practice import claude_cli as c; c.call('x', timeout_s=600)")
            p = subprocess.Popen([sys.executable, "-c", code], cwd=ROOT, env=dict(os.environ, HIP_CLAUDE_BIN=str(fake)))
            for _ in range(50):
                if subprocess.run(["pgrep", "-fx", mark], capture_output=True).returncode == 0:
                    break
                time.sleep(0.1)
            p.send_signal(signal.SIGTERM); p.wait(30)
            time.sleep(0.5)
            self.assertNotEqual(subprocess.run(["pgrep", "-fx", mark], capture_output=True).returncode, 0, "model child survived")


if __name__ == "__main__":
    unittest.main()
