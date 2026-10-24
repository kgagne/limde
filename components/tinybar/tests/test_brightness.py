"""Check the tinybar-brightness step curve against a fake backlight. Never touches the real panel."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tinybar-brightness"
MAX = 96000


class BrightnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.dev = root / "fake_backlight"
        self.dev.mkdir()
        (self.dev / "max_brightness").write_text(f"{MAX}\n")
        # Stand-in for brightnessctl: writes the requested raw value to the fake device.
        self.ctl = root / "brightnessctl"
        self.ctl.write_text(
            '#!/bin/sh\n'
            '[ "$1" = -q ] && [ "$2" = -d ] && [ "$3" = fake_backlight ] && [ "$4" = set ] || exit 9\n'
            f'printf %s "$5" > "{self.dev}/brightness"\n'
        )
        self.ctl.chmod(0o755)

    def step(self, direction, raw):
        (self.dev / "brightness").write_text(str(raw))
        env = dict(os.environ, TINYBAR_BRIGHTNESSCTL=str(self.ctl), TINYBAR_BACKLIGHT_DIR=str(self.dev))
        subprocess.run(["sh", str(SCRIPT), direction], env=env, check=True)
        return int((self.dev / "brightness").read_text())

    def pct(self, p):
        return (MAX * p + 50) // 100

    def walk(self, direction, start):
        seen, raw = [start], self.pct(start)
        for _ in range(40):
            new = self.step(direction, raw)
            if new == raw:
                break
            raw = new
            seen.append(round(raw * 100 / MAX))
        return seen

    def test_down_from_full(self):
        self.assertEqual(
            self.walk("down", 100),
            [100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
        )

    def test_up_from_floor(self):
        self.assertEqual(
            self.walk("up", 1),
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        )

    def test_off_grid_values_snap_to_the_grid(self):
        self.assertEqual(round(self.step("down", self.pct(35)) * 100 / MAX), 30)
        self.assertEqual(round(self.step("up", self.pct(35)) * 100 / MAX), 40)
        self.assertEqual(round(self.step("down", self.pct(10) + 3) * 100 / MAX), 9)
        self.assertEqual(round(self.step("up", self.pct(9) + 400) * 100 / MAX), 10)

    def test_never_reaches_zero_or_exceeds_max(self):
        self.assertEqual(self.step("down", 1), self.pct(1))
        self.assertEqual(self.step("down", 0), self.pct(1))
        self.assertEqual(self.step("up", MAX), MAX)

    def test_bad_argument(self):
        (self.dev / "brightness").write_text("9600")
        env = dict(os.environ, TINYBAR_BRIGHTNESSCTL=str(self.ctl), TINYBAR_BACKLIGHT_DIR=str(self.dev))
        r = subprocess.run(["sh", str(SCRIPT), "sideways"], env=env, stderr=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 2)
        self.assertEqual((self.dev / "brightness").read_text(), "9600")


if __name__ == "__main__":
    unittest.main()
