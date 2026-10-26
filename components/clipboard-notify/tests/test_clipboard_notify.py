"""Check elachisto-clipboard-notify against a stand-in wl-paste. Never touches the real clipboard."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "elachisto-clipboard-notify"


class ClipboardNotifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.calls = self.root / "calls"

    def wl_paste(self, types, cut_marker=""):
        """A stand-in that offers `types` and logs every call, so a test can see what was read."""
        path = self.root / "wl-paste"
        listing = "\\n".join(types)
        path.write_text(
            "#!/bin/sh\n"
            f'echo "$@" >> "{self.calls}"\n'
            'case "$*" in\n'
            f'  *--list-types*) printf "{listing}" ;;\n'
            f'  *application/x-kde-cutselection*) printf "{cut_marker}" ;;\n'
            '  *) exit 1 ;;\n'
            'esac\n')
        path.chmod(0o755)
        return path

    def event(self, uri_list, types, cut_marker="", state="data"):
        env = dict(os.environ, ELACHISTO_CLIPBOARD_NO_NOTIFY="1", CLIPBOARD_STATE=state,
                   ELACHISTO_CLIPBOARD_WLPASTE=str(self.wl_paste(types, cut_marker)))
        r = subprocess.run(["python3", str(SCRIPT), "--event"], input=uri_list, env=env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.splitlines()

    FILES = ["text/uri-list", "x-special/gnome-copied-files", "application/x-kde-cutselection"]

    def test_cut_of_one_file_names_it(self):
        # libfm's format: CRLF between URIs and a trailing NUL.
        out = self.event("file:///srv/My%20Notes.txt\0", self.FILES, cut_marker="1\0")
        self.assertEqual(out, ["Cut “My Notes.txt”", "Paste with Ctrl+V to move", "edit-cut"])

    def test_copy_of_several_files_counts_them(self):
        out = self.event("file:///a/one\r\nfile:///a/two\r\nfile:///a/dir/\0", self.FILES)
        self.assertEqual(out, ["Copied 3 items", "Paste with Ctrl+V", "edit-copy"])

    def test_never_reads_the_type_that_cancels_a_cut(self):
        self.event("file:///a/one\0", self.FILES, cut_marker="1\0")
        for call in self.calls.read_text().splitlines():
            self.assertNotIn("x-special/gnome-copied-files", call)

    def test_links_from_other_apps_are_ignored(self):
        self.assertEqual(self.event("https://example.org/\n", ["text/uri-list", "text/plain"]), [])

    def test_cleared_clipboard_is_ignored(self):
        self.assertEqual(self.event("", self.FILES, state="nil"), [])
        self.assertFalse(self.calls.exists())

    def test_watch_mode_runs_wl_paste_on_the_uri_list(self):
        fake = self.root / "wl-paste-watch"
        fake.write_text(f'#!/bin/sh\necho "$@" > "{self.calls}"\n')
        fake.chmod(0o755)
        env = dict(os.environ, ELACHISTO_CLIPBOARD_WLPASTE=str(fake))
        subprocess.run(["python3", str(SCRIPT)], env=env, check=True)
        args = self.calls.read_text().split()
        self.assertEqual(args[:3], ["--type", "text/uri-list", "--watch"])
        self.assertEqual(args[-1], "--event")


if __name__ == "__main__":
    unittest.main()
