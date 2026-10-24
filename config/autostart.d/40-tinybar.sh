# The panel.
if ! pgrep -f share/elachisto/tinybar/tinybar.py >/dev/null; then
    tinybar >"$HOME/.local/state/elachisto/tinybar.log" 2>&1 &
fi
