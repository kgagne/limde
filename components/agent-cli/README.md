# agent-cli

The agent window's CLI mode: a command-line AI agent (Claude Code, Codex CLI, Gemini CLI,
or any other command) in a terminal at the left of the panel, in place of agent-web's
website. The agent runs in tmux, so closing the window only hides it; the agent carries
on, and the window reopens by itself.

- **Switching:** `limde-agent mode cli` shows it now and at every login;
  `limde-agent mode web` goes back to agent-web. Switching never stops the CLI agent.
  `limde-agent status` says which mode is set and what runs.
- **First start:** with nothing set up, the window walks you through it. It asks which
  agent to use and checks that it is installed. If it is not, it shows the agent's
  official install command and page, and runs that installer only if you type yes (Claude
  Code's script is downloaded to a file first, then run; Codex CLI and Gemini CLI install
  with npm, into `~/.local`). Then it writes the user service and starts it, and the
  window attaches. `limde-agent setup` runs the walkthrough again, in any terminal, to
  pick another agent.
- **The session:** tmux on its own socket, `agent` (session `agent`), started by
  `limde-agent-cli.service`, which starts at login. `tmux -L agent attach` reaches it
  from any terminal or over SSH. With `loginctl enable-linger`, it starts at boot.
- **When the agent exits:** it starts again after 30 s, or at once when you press Enter.
  The session, and its scrollback, stay.
- **Keys:** Super+W, Super+Q and Alt+F4 don't close the window. In tmux, the keys for a
  new window (Ctrl+B c) and for killing a pane or window (Ctrl+B x, Ctrl+B &) do nothing,
  nor do Ctrl+B ! (pane to a new window), $ (rename the session), s and w (the trees) and
  the menus (Ctrl+B < and >, right click): the status line shows no window list, so a new
  window would hide the agent. A right click goes to the agent. Shift+Enter
  reaches the agent (tmux extended keys). The mouse wheel scrolls; a drag selects and
  copies.
- **Turning it off:** `limde-agent mode web`, then, to stop the agent itself,
  `systemctl --user disable --now limde-agent-cli`.

Files:

- `~/.config/limde/agent-cli.conf`: `name=` and `command=` (run by your login shell, so
  it finds what your terminals find). Edit it, then run
  `systemctl --user restart limde-agent-cli` (this ends the agent's current session).
- `~/.config/systemd/user/limde-agent-cli.service`: written by the setup.
- An agent you already keep in tmux with a user service of your own: put `socket=`,
  `session=` and `unit=` (that service's name) in `agent-cli.conf` instead of
  `command=`. The window attaches to that session and starts that unit when the session
  is down; it never restarts it. Running the setup again replaces these lines.
- `~/.config/limde/agent-cli/tmux.conf`: your tmux additions, read after limDE's
  (`/usr/local/share/limde/agent-cli/tmux.conf`: mouse on, extended keys, 50 000 lines
  of history, clipboard, focus events, a 10 ms Esc, one quiet status line).
- `~/.config/limde/agent-cli/foot.ini`: used instead of limDE's window settings
  (`/usr/local/share/limde/agent-cli/foot.ini`: JetBrains Mono 11 pt, padding, no foot
  scrollback since tmux keeps it).

How it works: `limde-agent` reads the mode from `~/.config/limde/agent.conf` and runs
`agent-web` or `agent-cli`. `agent-cli` starts one loop that reopens the window about 2 s
after it closes, and that ends with its labwc session, as agent-web's does. The window is
foot with the app ID `limde.AgentCLI`, which Tinybar puts first and labwc guards from the
close keys, running `agent-cli --attach`: it attaches to the session, starts the service
if it is down, or runs the setup (`agent_cli_setup.py`) if nothing is set up. Inside tmux,
`agent-cli --run` runs the agent and starts it again when it stops. Run over SSH or from
inside tmux, where there is no desktop session, `limde-agent mode` opens the new window
in the session whose agent window is open, with that window's environment.
