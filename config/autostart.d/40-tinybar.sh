# The panel.
if ! pgrep -f share/limde/tinybar/tinybar.py >/dev/null; then
    tinybar >"$HOME/.local/state/limde/tinybar.log" 2>&1 &
fi
