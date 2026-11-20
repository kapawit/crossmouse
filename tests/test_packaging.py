from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WindowsEntryPointTests(unittest.TestCase):
    def test_frozen_entry_point_starts_without_relative_import_error(self):
        scripts = []
        spec = ROOT / "packaging" / "CrossMouse.spec"

        class Analysis:
            def __init__(self, scripts_arg, **kwargs):
                scripts.extend(scripts_arg)
                self.scripts = scripts_arg
                self.pure = []
                self.binaries = []
                self.datas = []

        namespace = {
            "__file__": str(spec),
            "SPEC": str(spec),
            "Analysis": Analysis,
            "PYZ": lambda *args, **kwargs: None,
            "EXE": lambda *args, **kwargs: None,
        }
        exec(spec.read_text(encoding="utf-8"), namespace)

        self.assertEqual(len(scripts), 1)
        entry = Path(scripts[0])
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        result = subprocess.run(
            [sys.executable, str(entry), "--help"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertNotIn("attempted relative import", result.stderr)
        self.assertIn("CrossMouse - share one mouse and keyboard over LAN", result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
