from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from crossmouse.debuglog import DebugLogger, debug_log_path


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
