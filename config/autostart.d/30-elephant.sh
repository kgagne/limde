# The launcher's data service (apps, files, calculator).
if ! pgrep -x elephant >/dev/null; then
    elephant >"$HOME/.local/state/limde/elephant.log" 2>&1 &
fi
