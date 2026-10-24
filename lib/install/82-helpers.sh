# Small elachisto tools: Space preview, screenshots, and the app-aware close/quit helper.

step_helpers() {
  heading "Helpers (preview, screenshots, shortcuts)"
  local src=$ELACHISTO_ROOT/components work log stage
  work=$(mktemp -d); stage=$(mktemp -d); log=$STATE_DIR/helpers-build.log
  cp -r "$src/shortcuts/." "$work/"
  (cd "$work" && sh build.sh) >"$log" 2>&1 || { tail -n 20 "$log" >&2; die "app-shortcut did not build (log: $log)"; }
  install -m 755 "$work/build/app-shortcut" "$stage/app-shortcut"
  install -m 755 "$src/preview/elachisto-preview" "$stage/elachisto-preview"
  install -m 755 "$src/screenshot/elachisto-screenshot" "$stage/elachisto-screenshot"
  local f n=0
  for f in "$stage"/*; do
    cmp -s "$f" "/usr/local/bin/${f##*/}" && continue
    sudo install -m 755 "$f" "/usr/local/bin/${f##*/}"
    n=$((n + 1))
  done
  rm -rf "$work" "$stage"
  if ((n)); then changed "installed $n helper(s): elachisto-preview, elachisto-screenshot, app-shortcut"
  else ok "helpers are up to date"; fi
}
