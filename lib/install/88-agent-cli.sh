# agent-cli: the agent window in CLI mode (a foot window on a command-line agent in tmux),
# its tmux and foot settings, its setup walkthrough and its menu entry. limde-agent (a
# helper, step_helpers) picks web or CLI mode; the CLI agent's user service is written by
# its setup, not here. See components/agent-cli.

AGENT_CLI_SHARE=/usr/local/share/limde/agent-cli

step_agent_cli() {
  heading "agent-cli (the agent window's CLI mode)"
  local src=$LIMDE_ROOT/components/agent-cli stage f same=1
  stage=$(mktemp -d)
  for f in tmux.conf foot.ini agent_cli_setup.py; do
    install -m 644 "$src/$f" "$stage/$f"
  done
  diff -rq "$stage" "$AGENT_CLI_SHARE" >/dev/null 2>&1 || same=0
  cmp -s "$src/agent-cli" /usr/local/bin/agent-cli || same=0
  local entry=/usr/local/share/applications/limde.AgentCLI.desktop want
  want='[Desktop Entry]
Type=Application
Name=Agent CLI
GenericName=Command-line agent
Comment=Your command-line AI agent in its own window
Exec=agent-cli
Icon=limde.AgentCLI
StartupWMClass=limde.AgentCLI
Terminal=false
Categories=Development;'
  [[ $(cat "$entry" 2>/dev/null) == "$want" ]] || same=0
  if ((same)); then
    ok "agent-cli is up to date"
  else
    sudo rm -rf "$AGENT_CLI_SHARE"; sudo install -d "$AGENT_CLI_SHARE"
    sudo cp "$stage"/* "$AGENT_CLI_SHARE/"
    sudo install -m 755 "$src/agent-cli" /usr/local/bin/agent-cli
    printf '%s\n' "$want" | sudo install -D -m 644 /dev/stdin "$entry"
    changed "installed agent-cli"
  fi
  rm -rf "$stage"
}
