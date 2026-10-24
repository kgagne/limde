# The launcher's data service (apps, files, calculator).
if ! pgrep -x elephant >/dev/null; then
    elephant >"$HOME/.local/state/elachisto/elephant.log" 2>&1 &
fi
