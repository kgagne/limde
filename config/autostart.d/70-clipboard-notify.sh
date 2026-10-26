# A short notification when files are cut or copied, since PCManFM doesn't mark cut files.
if ! pgrep -f 'wl-paste --type text/uri-list --watch' >/dev/null; then
    elachisto-clipboard-notify >"$HOME/.local/state/elachisto/clipboard-notify.log" 2>&1 &
fi
