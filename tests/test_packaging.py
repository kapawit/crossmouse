from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NativeUIPackagingTests(unittest.TestCase):
    def test_windows_spec_bundles_native_ui(self):
        spec = (ROOT / "packaging" / "CrossMouse.spec").read_text()
        self.assertIn("crossmouse.native_ui", spec)
        self.assertNotIn("crossmouse.webui", spec)

    def test_deb_bundles_pyside6(self):
        script = (ROOT / "packaging" / "build-deb.sh").read_text()
        self.assertIn("PySide6", script)

    def test_deb_declares_qt_xcb_cursor_dependency(self):
        script = (ROOT / "packaging" / "build-deb.sh").read_text()
        self.assertIn("libxcb-cursor0", script)

    def test_deb_ships_license_notices(self):
        script = (ROOT / "packaging" / "build-deb.sh").read_text()
        self.assertIn("LICENSE", script)

    def test_build_artifacts_are_not_tracked(self):
        result = subprocess.run(
            ["git", "ls-files", "dist"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout.strip(), "")

    def test_windows_spec_ships_license_notices(self):
        spec = (ROOT / "packaging" / "CrossMouse.spec").read_text()
        self.assertIn("LICENSE", spec)


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
