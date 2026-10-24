# agent-web: the web agent's window (a separate Firefox profile), its welcome page and its
# menu entry. Started by the session autostart; see components/agent-web.

AGENT_WEB_SHARE=/usr/local/share/elachisto/agent-web

step_agent_web() {
  heading "agent-web (your web agent's window)"
  local src=$ELACHISTO_ROOT/components/agent-web stage f same=1
  stage=$(mktemp -d)
  for f in user.js userChrome.css autoconfig.js agent-web.cfg welcome.html; do
    install -m 644 "$src/$f" "$stage/$f"
  done
  diff -rq "$stage" "$AGENT_WEB_SHARE" >/dev/null 2>&1 || same=0
  cmp -s "$src/agent-web" /usr/local/bin/agent-web || same=0
  local entry=/usr/local/share/applications/elachisto.AgentWeb.desktop want
  want='[Desktop Entry]
Type=Application
Name=Agent
GenericName=Web agent
Comment=Your web AI agent in its own window
Exec=agent-web
Icon=elachisto.AgentWeb
StartupWMClass=elachisto.AgentWeb
Terminal=false
Categories=Network;'
  [[ $(cat "$entry" 2>/dev/null) == "$want" ]] || same=0
  if ((same)); then
    ok "agent-web is up to date"
  else
    sudo rm -rf "$AGENT_WEB_SHARE"; sudo install -d "$AGENT_WEB_SHARE"
    sudo cp "$stage"/* "$AGENT_WEB_SHARE/"
    sudo install -m 755 "$src/agent-web" /usr/local/bin/agent-web
    printf '%s\n' "$want" | sudo install -D -m 644 /dev/stdin "$entry"
    changed "installed agent-web"
  fi
  rm -rf "$stage"
}
