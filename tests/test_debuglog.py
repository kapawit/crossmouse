from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from crossmouse.debuglog import DebugLogger, _default_preferred_path, debug_log_path


class DebugLoggerTests(unittest.TestCase):
    def test_appends_timestamped_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "debug.log"
            path.write_text("existing\n")
            logger = DebugLogger(path)
            try:
                logger.log("first")
                logger.log("second")
            finally:
                logger.close()

            lines = path.read_text().splitlines()
            self.assertEqual(len(lines), 3)
            self.assertEqual(lines[0], "existing")
            for line in lines[1:]:
                self.assertRegex(line, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} ")
            self.assertIn("first", lines[1])
            self.assertIn("second", lines[2])

    def test_close_stops_further_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "debug.log"
            logger = DebugLogger(path)
            logger.log("before")
            logger.close()
            logger.log("after")

            self.assertEqual(len(path.read_text().splitlines()), 1)


class DebugLogPathTests(unittest.TestCase):
    def test_falls_back_to_current_directory_when_preferred_is_unwritable(self):
        self.assertEqual(
            debug_log_path(Path("/proc/forbidden/debug.log")),
            Path.cwd() / "debug.log",
        )

    def test_falls_back_to_temp_when_current_directory_is_unwritable(self):
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory)
            blocked = cwd / "debug.log"
            blocked.mkdir()
            temp = cwd / "tmp"
            temp.mkdir()
            with (
                mock.patch("crossmouse.debuglog.Path.cwd", return_value=cwd),
                mock.patch("crossmouse.debuglog.tempfile.gettempdir", return_value=str(temp)),
            ):
                self.assertEqual(
                    debug_log_path(Path("/proc/forbidden/debug.log")),
                    temp / "debug.log",
                )

    def test_default_path_uses_deb_log_dir(self):
        with (
            mock.patch("crossmouse.debuglog.sys.platform", "linux"),
            mock.patch(
                "crossmouse.debuglog.__file__",
                "/usr/lib/crossmouse/crossmouse/debuglog.py",
            ),
        ):
            self.assertEqual(_default_preferred_path(), Path("/var/log/crossmouse/debug.log"))

    def test_default_path_uses_app_dir_for_source(self):
        expected = Path(__file__).resolve().parent.parent / "debug.log"
        self.assertEqual(_default_preferred_path(), expected)
