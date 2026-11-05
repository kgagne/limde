# Small limde tools: Space preview, screenshots, the app-aware close/quit helper, the
# notification for cut and copied files, limde-update, and limde-agent (the agent
# window's web or CLI mode).

step_helpers() {
  heading "Helpers (preview, screenshots, shortcuts, clipboard)"
  local src=$LIMDE_ROOT/components work log stage
  work=$(mktemp -d); stage=$(mktemp -d); log=$STATE_DIR/helpers-build.log
  cp -r "$src/shortcuts/." "$work/"
  (cd "$work" && sh build.sh) >"$log" 2>&1 || { tail -n 20 "$log" >&2; die "app-shortcut did not build (log: $log)"; }
  install -m 755 "$work/build/app-shortcut" "$stage/app-shortcut"
  install -m 755 "$src/preview/limde-preview" "$stage/limde-preview"
  install -m 755 "$src/screenshot/limde-screenshot" "$stage/limde-screenshot"
  install -m 755 "$src/clipboard-notify/limde-clipboard-notify" "$stage/limde-clipboard-notify"
  install -m 755 "$src/updater/limde-update" "$stage/limde-update"
  install -m 755 "$src/agent-cli/limde-agent" "$stage/limde-agent"
  local f n=0
  for f in "$stage"/*; do
    cmp -s "$f" "/usr/local/bin/${f##*/}" && continue
    sudo install -m 755 "$f" "/usr/local/bin/${f##*/}"
    n=$((n + 1))
  done
  rm -rf "$work" "$stage"
  if ((n)); then changed "installed $n helper(s): limde-preview, limde-screenshot, limde-clipboard-notify, limde-update, limde-agent, app-shortcut"
  else ok "helpers are up to date"; fi
}
