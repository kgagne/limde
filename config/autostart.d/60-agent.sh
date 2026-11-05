# The agent window, kept open and leftmost in the panel: your web agent (agent-web) or a
# command-line agent in tmux (agent-cli), as `limde-agent mode` set it. Starts its
# reopening loop unless one already runs; a loop left from the last session is replaced.
# An empty ~/.config/limde/autostart.d/60-agent-web.sh, this piece's old name, still turns
# it off.
[ -e "$HOME/.config/limde/autostart.d/60-agent-web.sh" ] || limde-agent >/dev/null 2>&1
