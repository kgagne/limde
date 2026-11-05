#!/usr/bin/env python3
"""agent-cli setup: a short walkthrough that picks the command-line agent for the agent
window, checks that it is installed, writes its user service and starts it.

Run by `limde-agent setup` (or `agent-cli setup`) in a terminal, and by the agent window
itself in CLI mode while nothing is set up (--in-window, after which the window attaches).
It installs nothing unless you type yes, and then only with the agent's own official
installer, downloaded to a file first. No dependencies beyond Python's standard library.
"""
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

UNIT = "limde-agent-cli.service"
SOCKET = "agent"
SESSION = "agent"


@dataclass(frozen=True)
class Agent:
    name: str
    maker: str
    command: str
    docs: str
    installer: str = ""  # an official install script's URL, run with bash after a yes
    npm: str = ""  # or an npm package


AGENTS = (
    Agent("Claude Code", "Anthropic", "claude", "https://code.claude.com/docs/en/setup",
          installer="https://claude.ai/install.sh"),
    Agent("Codex CLI", "OpenAI", "codex", "https://github.com/openai/codex",
          npm="@openai/codex"),
    Agent("Gemini CLI", "Google", "gemini", "https://github.com/google-gemini/gemini-cli",
          npm="@google/gemini-cli"),
)

INTRO = """\
Agent window setup

The agent window can run a command-line AI agent instead of a website.
tmux keeps the agent running while its window is closed.
Closing the window only hides it. It comes back by itself, as you left it.
"""


def config_home(home):
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path(home) / ".config")


def conf_path(home):
    """Always under ~/.config, where agent-cli and limde-agent read it."""
    return Path(home) / ".config" / "limde" / "agent-cli.conf"


def unit_path(home):
    """Where systemd looks for your user units, which honours XDG_CONFIG_HOME."""
    return config_home(home) / "systemd" / "user" / UNIT


def read_conf(path):
    """The conf file's settings ({"name": ..., "command": ...}); later lines win."""
    values = {}
    try:
        lines = Path(path).read_text().splitlines()
    except OSError:
        return values
    for line in lines:
        key, sep, value = line.partition("=")
        if sep and not key.startswith("#"):
            values[key.strip()] = value
    return values


def conf_text(name, command):
    if "\n" in command or "\n" in name:
        raise ValueError("one line each")
    return (
        "# The command-line agent in the agent window (written by limde-agent setup).\n"
        "# command= runs in your login shell; after a change:\n"
        f"#   systemctl --user restart {UNIT}\n"
        f"name={name}\ncommand={command}\n"
    )


def unit_text(tmux, agent_cli, tmux_conf):
    """The user service that keeps the agent's tmux session. The agent itself is
    `agent-cli --run`, which reads the command from the conf file at each start."""
    return f"""\
# Written by limde-agent setup: the agent window's command-line agent, in tmux.
# Attach in any terminal with: tmux -L {SOCKET} attach
[Unit]
Description=Command-line agent for the agent window, in tmux (tmux -L {SOCKET} attach)

[Service]
Type=forking
WorkingDirectory=%h
# The user manager's PATH lacks ~/.local/bin, where CLI agents often install themselves.
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart={tmux} -L {SOCKET} -f {tmux_conf} new-session -d -s {SESSION} {agent_cli} --run
ExecStop={tmux} -L {SOCKET} kill-server
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
"""


def program_of(command):
    """The program a command line starts: its first word that isn't VAR=value."""
    try:
        words = shlex.split(command)
    except ValueError:
        return ""
    for word in words:
        if "=" not in word.split("/")[0]:
            return word
    return ""


def yes(answer, default=False):
    answer = answer.strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


class System:
    """What the walkthrough does to the machine; the tests replace it."""

    def __init__(self, home):
        self.home = Path(home)

    def find(self, program):
        """Where the program is, as a login shell (which runs the agent) finds it."""
        if not program:
            return None
        shell = os.environ.get("SHELL") or "/bin/sh"
        try:
            found = subprocess.run(
                [shell, "-lc", f"command -v {shlex.quote(program)}"],
                capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL,
            ).stdout.strip().splitlines()
        except (OSError, subprocess.SubprocessError):
            found = []
        if found:
            return found[-1]
        path = f"{self.home}/.local/bin:{os.environ.get('PATH', '/usr/bin:/bin')}"
        return shutil.which(program, path=path)

    def run(self, argv):
        """Runs a command in this terminal; True when it succeeded."""
        try:
            return subprocess.run(argv).returncode == 0
        except OSError:
            return False

    def quiet(self, argv):
        try:
            return subprocess.run(argv, capture_output=True, stdin=subprocess.DEVNULL,
                                  timeout=60).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def download(self, url):
        """The file at url, saved to a temporary file; its path, or None."""
        handle, path = tempfile.mkstemp(prefix="agent-install-", suffix=".sh")
        os.close(handle)
        if self.run(["curl", "-fsSL", "--proto", "=https", "-o", path, url]):
            return path
        os.unlink(path)
        return None

    def write(self, path, text):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".new")
        temporary.write_text(text)
        temporary.replace(path)

    def active(self):
        return self.quiet(["systemctl", "--user", "-q", "is-active", UNIT])

    def mode(self):
        try:
            for line in (self.home / ".config" / "limde" / "agent.conf").read_text().splitlines():
                if line.startswith("mode="):
                    return line[5:].strip()
        except OSError:
            pass
        return "web"


class Walkthrough:
    def __init__(self, system, ask=input, say=print, *, home, tmux, agent_cli, tmux_conf,
                 in_window=False):
        self.system = system
        self.ask = ask
        self.say = say
        self.home = Path(home)
        self.tmux = tmux
        self.agent_cli = agent_cli
        self.tmux_conf = tmux_conf
        self.in_window = in_window

    def choose(self):
        """The agent picked: an Agent, or a command line typed by hand (a str)."""
        self.say("Which agent should the window run?")
        for number, agent in enumerate(AGENTS, 1):
            self.say(f"  {number}  {agent.name} ({agent.maker})")
        other = len(AGENTS) + 1
        self.say(f"  {other}  Another command")
        while True:
            answer = self.ask("Type a number [1]: ").strip() or "1"
            if answer.isdigit() and 1 <= int(answer) <= len(AGENTS):
                return AGENTS[int(answer) - 1]
            if answer == str(other):
                while True:
                    command = self.ask("Type the command that starts your agent: ").strip()
                    if command:
                        return command
            self.say(f"Type a number from 1 to {other}.")

    def install(self, agent):
        """Offers the agent's official install; True once it is found."""
        while not self.system.find(agent.command):
            self.say(f"\n{agent.name} is not installed (no '{agent.command}' command found).")
            if agent.installer:
                self.say(f"Its official installer is:  curl -fsSL {agent.installer} | bash")
                self.say(f"About it: {agent.docs}")
                if yes(self.ask("Type yes to download and run that installer now: ")):
                    script = self.system.download(agent.installer)
                    if script is None:
                        self.say("The download failed. Check the network and try again.")
                    else:
                        self.system.run(["bash", script])
                        try:
                            os.unlink(script)
                        except OSError:
                            pass
                    continue
            else:
                self.say(f"Install it with npm (Node.js), as its makers describe:  npm install -g {agent.npm}")
                self.say(f"About it: {agent.docs}")
                if self.system.find("npm"):
                    prefix = self.home / ".local"
                    argv = ["npm", "install", "-g", "--prefix", str(prefix), agent.npm]
                    self.say(f"Without root, into ~/.local:  {shlex.join(argv)}")
                    if yes(self.ask("Type yes to run that now: ")):
                        self.system.run(argv)
                        continue
                else:
                    self.say("npm is not installed. Node.js's own site has it: https://nodejs.org")
            answer = self.ask("Install it in another terminal, then press Enter to check again, "
                              "or type 'back' to choose another agent: ")
            if answer.strip().lower() == "back":
                return False
        return True

    def command_for(self, agent):
        command = agent.command
        if agent.command == "claude":
            self.say("\nClaude Code can also be steered from claude.ai and the Claude app "
                     "(Remote Control).")
            if yes(self.ask("Turn that on? [y/N]: ")):
                command = "claude --remote-control"
        return command

    def confirm(self, command):
        self.say(f"\nThe agent window will run:  {command}")
        while True:
            typed = self.ask("Press Enter to use it, or type a different command: ").strip()
            if not typed:
                return command
            program = program_of(typed)
            if self.system.find(program) or yes(self.ask(
                    f"There is no '{program}' command. Use it anyway? [y/N]: ")):
                return typed

    def pick(self):
        """(name, command) for the agent to run."""
        while True:
            choice = self.choose()
            if isinstance(choice, str):
                program = program_of(choice)
                if self.system.find(program) or yes(self.ask(
                        f"There is no '{program}' command. Use it anyway? [y/N]: ")):
                    return program.rsplit("/", 1)[-1] or "Agent", choice
                continue
            if self.install(choice):
                return choice.name, self.confirm(self.command_for(choice))

    def run(self):
        self.say(INTRO)
        conf, unit = conf_path(self.home), unit_path(self.home)
        old = read_conf(conf)
        if old.get("unit"):
            self.say(f"The window shows tmux session '{old.get('session', 'agent')}' of "
                     f"{old['unit']} now. Setup replaces that with limDE's own service; "
                     f"{old['unit']} itself is left running.\n")
        if old.get("command"):
            self.say(f"Set up already: {old.get('name') or 'Agent'} ({old['command']}).\n")
        name, command = self.pick()

        was_running = self.system.active()
        changed = command != old.get("command")
        restart = False
        if was_running and changed:
            restart = yes(self.ask(
                "\nAn agent is running now. Restart it with the new command? "
                "This ends what it is doing. [y/N]: "))
        self.system.write(conf, conf_text(name, command))
        self.system.write(unit, unit_text(self.tmux, self.agent_cli, self.tmux_conf))
        self.system.quiet(["systemctl", "--user", "daemon-reload"])
        self.system.quiet(["systemctl", "--user", "enable", UNIT])
        if restart:
            started = self.system.quiet(["systemctl", "--user", "restart", UNIT])
        else:
            started = self.system.quiet(["systemctl", "--user", "start", UNIT])
        if not started:
            self.say(f"\nThe service did not start. See: systemctl --user status {UNIT}")
            return 1

        self.say(f"\nDone. {name} runs in tmux from now on, and starts at every login.")
        if was_running and changed and not restart:
            self.say(f"The running agent keeps going; the new command starts with "
                     f"systemctl --user restart {UNIT}")
        if command.startswith("claude --remote-control"):
            self.say("To keep it running before anyone logs in too: loginctl enable-linger")
        if self.in_window:
            return 0
        if self.system.mode() == "cli":
            self.say("The agent window shows it.")
        elif yes(self.ask("Show it in the agent window now, instead of the website? [Y/n]: "),
                 default=True):
            self.system.run(["limde-agent", "mode", "cli"])
        else:
            self.say("Switch any time with: limde-agent mode cli")
        self.say(f"In any terminal, attach with: tmux -L {SOCKET} attach")
        return 0


def main(argv):
    in_window = "--in-window" in argv[1:]
    if any(a not in ("--in-window",) for a in argv[1:]):
        print("usage: agent-cli setup", file=sys.stderr)
        return 2
    share = Path(__file__).resolve().parent
    home = Path.home()
    walk = Walkthrough(
        System(home), home=home,
        tmux=shutil.which("tmux") or "/usr/bin/tmux",
        agent_cli=shutil.which("agent-cli") or str(share.parents[2] / "bin" / "agent-cli"),
        tmux_conf=str(share / "tmux.conf"),
        in_window=in_window,
    )
    try:
        return walk.run()
    except (KeyboardInterrupt, EOFError):
        print("\nSetup stopped.")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
