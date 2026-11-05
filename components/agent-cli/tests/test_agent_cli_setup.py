"""The agent window's CLI setup walkthrough, with a stand-in for the machine: no
systemctl, no downloads, no installs, a temporary home."""
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent_cli_setup as setup  # noqa: E402


class FakeSystem(setup.System):
    def __init__(self, home, installed=(), active=False, mode="web", starts=True):
        super().__init__(home)
        self.installed = set(installed)
        self.is_active = active
        self.current_mode = mode
        self.starts = starts
        self.ran = []
        self.downloads = []

    def find(self, program):
        return f"/usr/bin/{program}" if program in self.installed else None

    def run(self, argv):
        self.ran.append(list(argv))
        if argv[0] == "bash":  # the downloaded installer
            self.installed.add("claude")
        return True

    def quiet(self, argv):
        self.ran.append(list(argv))
        return self.starts or argv[2] not in ("start", "restart")

    def download(self, url):
        self.downloads.append(url)
        return os.devnull

    def active(self):
        return self.is_active

    def mode(self):
        return self.current_mode


class Run:
    def __init__(self, test, answers, **system):
        self.home = Path(test.enterContext(tempfile.TemporaryDirectory()))
        test.enterContext(mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": ""}))
        self.system = FakeSystem(self.home, **system)
        self.answers = list(answers)
        self.prompts = []
        self.said = []
        self.in_window = False

    def ask(self, prompt):
        self.prompts.append(prompt)
        if not self.answers:
            raise AssertionError(f"unexpected question: {prompt}")
        return self.answers.pop(0)

    def __call__(self, in_window=False):
        walk = setup.Walkthrough(
            self.system, self.ask, lambda text="": self.said.append(text), home=self.home,
            tmux="/usr/bin/tmux", agent_cli="/usr/local/bin/agent-cli",
            tmux_conf="/usr/local/share/limde/agent-cli/tmux.conf", in_window=in_window)
        status = walk.run()
        self.text = "\n".join(self.said)
        return status

    def conf(self):
        return setup.read_conf(setup.conf_path(self.home))

    def unit(self):
        return setup.unit_path(self.home).read_text()


class WalkthroughTests(unittest.TestCase):
    def test_installed_claude_with_remote_control(self):
        run = Run(self, ["1", "y", "", "n"], installed={"claude"})
        self.assertEqual(run(), 0)
        self.assertEqual(run.conf(), {"name": "Claude Code", "command": "claude --remote-control"})
        self.assertIn("ExecStart=/usr/bin/tmux -L agent -f /usr/local/share/limde/agent-cli/"
                      "tmux.conf new-session -d -s agent /usr/local/bin/agent-cli --run",
                      run.unit())
        self.assertIn(["systemctl", "--user", "enable", setup.UNIT], run.system.ran)
        self.assertIn(["systemctl", "--user", "start", setup.UNIT], run.system.ran)
        self.assertNotIn(["limde-agent", "mode", "cli"], run.system.ran)  # answered n
        self.assertIn("loginctl enable-linger", run.text)

    def test_default_answers_pick_claude_and_switch_the_window(self):
        run = Run(self, ["", "", "", ""], installed={"claude"})
        self.assertEqual(run(), 0)
        self.assertEqual(run.conf()["command"], "claude")
        self.assertIn(["limde-agent", "mode", "cli"], run.system.ran)

    def test_in_window_asks_nothing_about_the_mode(self):
        run = Run(self, ["2", ""], installed={"codex"})
        self.assertEqual(run(in_window=True), 0)
        self.assertEqual(run.conf(), {"name": "Codex CLI", "command": "codex"})
        self.assertFalse(any(argv[0] == "limde-agent" for argv in run.system.ran))

    def test_nothing_is_installed_without_yes(self):
        # Claude Code missing: the installer is shown, the answer is no, then back to
        # the list and a command typed by hand.
        run = Run(self, ["1", "", "back", "4", "bash"], installed={"bash"})
        self.assertEqual(run(in_window=True), 0)
        self.assertEqual(run.system.downloads, [])
        self.assertFalse(any(argv[0] == "bash" for argv in run.system.ran))
        self.assertIn("curl -fsSL https://claude.ai/install.sh | bash", run.text)
        self.assertEqual(run.conf(), {"name": "bash", "command": "bash"})

    def test_yes_downloads_the_official_installer_then_runs_it(self):
        run = Run(self, ["1", "yes", "n", ""], installed=set())
        self.assertEqual(run(in_window=True), 0)
        self.assertEqual(run.system.downloads, ["https://claude.ai/install.sh"])
        self.assertIn(["bash", os.devnull], run.system.ran)
        self.assertEqual(run.conf()["command"], "claude")

    def test_npm_agents_install_into_local_only_after_yes(self):
        run = Run(self, ["3", "", "back", "4", "htop"], installed={"npm", "htop"})
        self.assertEqual(run(in_window=True), 0)
        self.assertIn("npm install -g @google/gemini-cli", run.text)
        self.assertFalse(any(argv[0] == "npm" for argv in run.system.ran))

        run = Run(self, ["3", "yes", "", "back", "4", "htop"], installed={"npm", "htop"})
        run(in_window=True)
        self.assertIn(["npm", "install", "-g", "--prefix", str(run.home / ".local"),
                       "@google/gemini-cli"], run.system.ran)

    def test_unknown_command_needs_a_yes(self):
        run = Run(self, ["4", "my-agent --flag", "n", "4", "my-agent --flag", "y"])
        self.assertEqual(run(in_window=True), 0)
        self.assertEqual(run.conf(), {"name": "my-agent", "command": "my-agent --flag"})

    def test_a_bad_number_asks_again(self):
        run = Run(self, ["9", "x", "4", "bash"], installed={"bash"})
        self.assertEqual(run(in_window=True), 0)
        self.assertEqual(run.prompts.count("Type a number [1]: "), 3)

    def test_running_agent_is_restarted_only_after_yes(self):
        run = Run(self, ["4", "bash", "n"], installed={"bash"}, active=True)
        self.assertEqual(run(in_window=True), 0)
        self.assertNotIn(["systemctl", "--user", "restart", setup.UNIT], run.system.ran)
        self.assertIn("systemctl --user restart", run.text)

        run = Run(self, ["4", "bash", "y"], installed={"bash"}, active=True)
        run(in_window=True)
        self.assertIn(["systemctl", "--user", "restart", setup.UNIT], run.system.ran)

    def test_rerun_with_the_same_command_does_not_ask_to_restart(self):
        run = Run(self, ["4", "bash"], installed={"bash"})
        run(in_window=True)
        run.system.is_active = True
        run.answers = ["4", "bash"]
        self.assertEqual(run(in_window=True), 0)
        self.assertIn("Set up already: bash (bash).", run.text)

    def test_a_unit_of_your_own_is_replaced_and_left_running(self):
        run = Run(self, ["4", "bash"], installed={"bash"})
        conf = setup.conf_path(run.home)
        conf.parent.mkdir(parents=True)
        conf.write_text("name=Claude Code\nsocket=claude\nsession=claude\nunit=claude-remote.service\n")
        self.assertEqual(run(in_window=True), 0)
        self.assertIn("claude-remote.service itself is left running", run.text)
        self.assertEqual(run.conf(), {"name": "bash", "command": "bash"})
        self.assertFalse(any("claude-remote.service" in argv for argv in run.system.ran))

    def test_failed_start_is_reported(self):
        run = Run(self, ["4", "bash"], installed={"bash"}, starts=False)
        self.assertEqual(run(in_window=True), 1)
        self.assertIn("systemctl --user status limde-agent-cli.service", run.text)


class FileTests(unittest.TestCase):
    def test_conf_round_trip(self):
        with tempfile.TemporaryDirectory() as home:
            path = Path(home) / "agent-cli.conf"
            path.write_text(setup.conf_text("Name", "a='b c' --x=1"))
            self.assertEqual(setup.read_conf(path), {"name": "Name", "command": "a='b c' --x=1"})

    def test_conf_refuses_two_lines(self):
        with self.assertRaises(ValueError):
            setup.conf_text("x", "a\nb")

    def test_missing_conf_is_empty(self):
        self.assertEqual(setup.read_conf("/nonexistent/agent-cli.conf"), {})

    def test_program_of(self):
        self.assertEqual(setup.program_of("claude --remote-control"), "claude")
        self.assertEqual(setup.program_of("FOO=1 BAR=2 codex"), "codex")
        self.assertEqual(setup.program_of("/opt/x/bin/agent run"), "/opt/x/bin/agent")
        self.assertEqual(setup.program_of("'unclosed"), "")

    def test_unit_restarts_and_starts_at_login(self):
        text = setup.unit_text("/usr/bin/tmux", "/usr/local/bin/agent-cli", "/t.conf")
        self.assertIn("Restart=always", text)
        self.assertIn("WantedBy=default.target", text)
        self.assertIn("ExecStop=/usr/bin/tmux -L agent kill-server", text)

    def test_mode_reads_agent_conf(self):
        with tempfile.TemporaryDirectory() as home, \
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": ""}):
            system = setup.System(home)
            self.assertEqual(system.mode(), "web")
            (Path(home) / ".config/limde").mkdir(parents=True)
            (Path(home) / ".config/limde/agent.conf").write_text("mode=cli\n")
            self.assertEqual(system.mode(), "cli")

    def test_conf_stays_where_the_shell_scripts_read_it(self):
        # agent-cli and limde-agent read ~/.config/limde; only the unit follows systemd's
        # XDG_CONFIG_HOME.
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": "/elsewhere"}):
            self.assertEqual(setup.conf_path("/h"), Path("/h/.config/limde/agent-cli.conf"))
            self.assertEqual(setup.unit_path("/h"),
                             Path("/elsewhere/systemd/user/limde-agent-cli.service"))


if __name__ == "__main__":
    unittest.main()
