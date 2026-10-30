# The launcher's data service (apps, files, calculator). It has no display connection, so it
# outlives a logout; replace that copy so this session's runs with this session's environment.
if pkill -x -u "$(id -u)" elephant; then
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        pgrep -x -u "$(id -u)" elephant >/dev/null || break
        sleep 0.2
    done
fi
elephant >"$HOME/.local/state/limde/elephant.log" 2>&1 &
