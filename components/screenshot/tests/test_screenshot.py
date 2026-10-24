"""Check elachisto-screenshot against stand-in grim/slurp/wl-copy. Never touches the real screen or clipboard."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "elachisto-screenshot"


class ScreenshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / "pictures" / "Screenshots"
        self.clip = self.root / "clipboard"
        self.args = self.root / "grim-args"

    def tool(self, name, body):
        path = self.root / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o755)
        return path

    def run_mode(self, mode, slurp="echo '10,20 300x200'"):
        env = dict(
            os.environ,
            ELACHISTO_SCREENSHOT_NO_NOTIFY="1",
            ELACHISTO_SCREENSHOT_DIR=str(self.out),
            ELACHISTO_SCREENSHOT_SLURP=str(self.tool("slurp", slurp + "\n")),
            ELACHISTO_SCREENSHOT_GRIM=str(self.tool(
                "grim",
                f'echo "$@" > "{self.args}"\n'
                'last=""; for a; do last="$a"; done\n'
                'if [ "$last" = - ]; then printf PNGDATA; else printf PNGDATA > "$last"; fi\n')),
            ELACHISTO_SCREENSHOT_WLCOPY=str(self.tool("wl-copy", f'[ "$1" = --type ] && [ "$2" = image/png ] || exit 9\ncat > "{self.clip}"\n')),
        )
        return subprocess.run(["sh", str(SCRIPT), mode], env=env, capture_output=True, text=True)

    def test_region_saves_and_copies(self):
        r = self.run_mode("region")
        self.assertEqual(r.returncode, 0, r.stderr)
        files = list(self.out.glob("screenshot-*.png"))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].read_text(), "PNGDATA")
        self.assertEqual(self.clip.read_text(), "PNGDATA")
        self.assertTrue(self.args.read_text().startswith("-g 10,20 300x200 "))

    def test_screen_saves_and_copies(self):
        r = self.run_mode("screen")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(list(self.out.glob("screenshot-*.png"))), 1)
        self.assertEqual(self.clip.read_text(), "PNGDATA")
        self.assertNotIn("-g", self.args.read_text())

    def test_clip_writes_nothing_to_disk(self):
        r = self.run_mode("clip")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.out.exists())
        self.assertEqual(self.clip.read_text(), "PNGDATA")

    def test_cancelled_selection_is_quiet(self):
        for mode in ("region", "clip"):
            r = self.run_mode(mode, slurp="exit 1")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(self.out.exists())
            self.assertFalse(self.clip.exists())
            self.assertFalse(self.args.exists())

    def test_bad_argument(self):
        self.assertEqual(self.run_mode("bogus").returncode, 2)


if __name__ == "__main__":
    unittest.main()
