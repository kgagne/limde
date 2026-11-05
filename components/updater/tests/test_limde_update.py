"""Check limde-update against throwaway Git repositories and a stand-in ./install. No network."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "limde-update"

# Stand-in installer: notes the commit it ran at and its arguments.
FAKE_INSTALL = """#!/bin/sh
echo "$(git rev-parse HEAD) $*" >> "$INSTALL_LOG"
exit "${FAKE_INSTALL_EXIT:-0}"
"""


class UpdateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        self.origin, self.clone = base / "origin", base / "clone"
        self.record, self.log = base / "installed", base / "install.log"
        # No GIT_* from the caller: a pre-commit hook runs with GIT_DIR and GIT_INDEX_FILE
        # set, and they would turn every git call here on the repository being committed.
        caller = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.env = dict(caller, LIMDE_INSTALL_RECORD=str(self.record), INSTALL_LOG=str(self.log),
                        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                        GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL="/dev/null",
                        GIT_CONFIG_NOSYSTEM="1")
        self.git(base, "init", "-q", "-b", "main", self.origin)
        (self.origin / "install").write_text(FAKE_INSTALL)
        (self.origin / "install").chmod(0o755)
        (self.origin / "pins").mkdir()
        (self.origin / "pins/labwc").write_text("LABWC_COMMIT=a\n")
        self.commit("first")
        self.tag("v1.0.0-beta.1", "limDE v1.0.0-beta.1\n\nFirst beta.")
        self.git(base, "clone", "-q", self.origin, self.clone)

    def git(self, where, *args):
        return subprocess.run(["git", "-C", str(where), *map(str, args)], env=self.env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, message, path="notes.txt"):
        f = self.origin / path
        f.write_text((f.read_text() if f.exists() else "") + message + "\n")
        self.git(self.origin, "add", ".")
        self.git(self.origin, "commit", "-qm", message)
        return self.git(self.origin, "rev-parse", "HEAD")

    def tag(self, name, message=None):
        self.git(self.origin, "tag", "-a", name, "-m", message or f"limDE {name}")
        return self.git(self.origin, "rev-parse", name + "^{commit}")

    def installed_at(self, ref, groups=""):
        commit = self.git(self.clone, "rev-parse", ref + "^{commit}")
        self.git(self.clone, "-c", "advice.detachedHead=false", "checkout", "-q", "--detach", commit)
        self.record.write_text(f"commit={commit}\nsource={self.clone}\ngroups={groups}\nmodified=no\n")
        return commit

    def run_update(self, *args, **env):
        return subprocess.run([sys.executable, SCRIPT, *args], env=dict(self.env, **env),
                              capture_output=True, text=True, input="")

    def install_calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_up_to_date(self):
        self.installed_at("v1.0.0-beta.1")
        done = self.run_update("--check")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("Up to date.", done.stdout)

    def test_check_shows_newer_release_and_changes_nothing(self):
        old = self.installed_at("v1.0.0-beta.1")
        self.commit("pin bump", "pins/labwc")
        self.tag("v1.0.0-beta.2", "limDE v1.0.0-beta.2\n\nNewer labwc.")
        done = self.run_update("--check")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("Available: v1.0.0-beta.2", done.stdout)
        self.assertIn("| Newer labwc.", done.stdout)
        self.assertIn("Built or downloaded again: labwc", done.stdout)
        self.assertEqual(self.git(self.clone, "rev-parse", "HEAD"), old)
        self.assertEqual(self.install_calls(), [])

    def test_update_checks_out_the_release_and_installs_with_saved_groups(self):
        self.installed_at("v1.0.0-beta.1", groups="laptop,bluetooth")
        new = self.commit("second")
        self.tag("v1.0.0-beta.2")
        done = self.run_update("--yes")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertEqual(self.install_calls(), [f"{new} --yes --with=laptop,bluetooth"])

    def test_release_sorts_after_its_candidates(self):
        self.installed_at("v1.0.0-beta.1")
        self.commit("rc")
        self.tag("v1.0.0-rc.1")
        final = self.commit("final")
        self.tag("v1.0.0")
        done = self.run_update("--yes")
        self.assertIn("Available: v1.0.0\n", done.stdout)
        self.assertEqual(self.install_calls(), [f"{final} --yes"])

    def test_stable_install_is_not_offered_a_test_release(self):
        self.commit("final")
        self.tag("v1.0.0")
        self.git(self.clone, "fetch", "-q", "--tags")
        self.installed_at("v1.0.0")
        self.commit("next beta")
        self.tag("v1.1.0-beta.1")
        done = self.run_update("--check")
        self.assertIn("Up to date.", done.stdout)

    def test_install_from_main_is_not_offered_an_older_tag(self):
        self.commit("after the beta")
        self.git(self.clone, "pull", "-q")
        self.installed_at("HEAD")
        done = self.run_update("--check")
        self.assertIn("Up to date.", done.stdout)
        newer = self.commit("more on main")
        done = self.run_update("--main", "--yes")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertEqual(self.install_calls(), [f"{newer} --yes"])

    def test_to_goes_back(self):
        first = self.git(self.origin, "rev-parse", "v1.0.0-beta.1^{commit}")
        self.commit("second")
        self.tag("v1.0.0-beta.2")
        self.git(self.clone, "fetch", "-q", "--tags")
        self.installed_at("v1.0.0-beta.2")
        done = self.run_update("--to", "v1.0.0-beta.1", "--yes")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("goes back", done.stdout)
        self.assertEqual(self.install_calls(), [f"{first} --yes"])

    def test_uncommitted_changes_stop_the_update(self):
        self.installed_at("v1.0.0-beta.1")
        self.commit("second")
        self.tag("v1.0.0-beta.2")
        (self.clone / "pins/labwc").write_text("mine\n")
        done = self.run_update("--yes")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("not committed", done.stdout)
        self.assertEqual(self.install_calls(), [])

    def test_declining_changes_nothing(self):
        old = self.installed_at("v1.0.0-beta.1")
        self.commit("second")
        self.tag("v1.0.0-beta.2")
        done = subprocess.run([sys.executable, SCRIPT], env=self.env, capture_output=True,
                              text=True, input="n\n")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertEqual(self.git(self.clone, "rev-parse", "HEAD"), old)
        self.assertEqual(self.install_calls(), [])

    def test_failed_install_says_how_to_go_back(self):
        old = self.installed_at("v1.0.0-beta.1")
        self.commit("second")
        self.tag("v1.0.0-beta.2")
        done = self.run_update("--yes", FAKE_INSTALL_EXIT="3")
        self.assertEqual(done.returncode, 3, done.stdout)
        self.assertIn(f"limde-update --to {old[:12]}", done.stdout)

    def test_missing_record(self):
        done = self.run_update("--check")
        self.assertEqual(done.returncode, 1)
        self.assertIn("run ./install", done.stdout)

    def test_unreachable_origin(self):
        self.installed_at("v1.0.0-beta.1")
        self.git(self.clone, "remote", "set-url", "origin", self.origin.parent / "gone")
        done = self.run_update("--check")
        self.assertEqual(done.returncode, 1)
        self.assertIn("could not fetch", done.stdout)


if __name__ == "__main__":
    unittest.main()
