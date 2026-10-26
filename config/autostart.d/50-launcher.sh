# The launcher (Super+Space), kept running so it opens instantly.
if ! pgrep -f 'walker --gapplication-service' >/dev/null; then
    GSK_RENDERER=cairo walker --gapplication-service >"$HOME/.local/state/limde/walker.log" 2>&1 &
fi
