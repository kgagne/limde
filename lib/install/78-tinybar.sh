# Install Tinybar: the panel in /usr/local/share/elachisto/tinybar, its commands in
# /usr/local/bin. The window-list helper is compiled here from its C source.

TINYBAR_SHARE=/usr/local/share/elachisto/tinybar

step_tinybar() {
  heading "Tinybar (the panel)"
  local src=$ELACHISTO_ROOT/components/tinybar work log
  work=$(mktemp -d); log=$STATE_DIR/tinybar-build.log
  mkdir -p "$STATE_DIR"
  cp -r "$src/." "$work/"
  (cd "$work" && sh build.sh) >"$log" 2>&1 || { tail -n 20 "$log" >&2; die "Tinybar's helper did not build (log: $log)"; }

  local stage; stage=$(mktemp -d)
  install -D -m 755 "$work/tinybar.py" "$stage/share/tinybar.py"
  install -D -m 644 "$work/tinybar_icons.py" "$stage/share/tinybar_icons.py"
  install -D -m 755 "$work/build/toplevel-helper" "$stage/share/toplevel-helper"
  local cmd
  for cmd in tinybar tinybar-volume tinybar-brightness; do
    install -D -m 755 "$work/$cmd" "$stage/bin/$cmd"
  done

  local same=1
  diff -rq "$stage/share" "$TINYBAR_SHARE" >/dev/null 2>&1 || same=0
  for cmd in tinybar tinybar-volume tinybar-brightness; do
    cmp -s "$stage/bin/$cmd" "/usr/local/bin/$cmd" || same=0
  done
  if ((same)); then
    ok "Tinybar is up to date"
  else
    sudo rm -rf "$TINYBAR_SHARE"
    sudo install -d "$TINYBAR_SHARE"
    sudo cp -a "$stage/share/." "$TINYBAR_SHARE/"
    for cmd in tinybar tinybar-volume tinybar-brightness; do
      sudo install -m 755 "$stage/bin/$cmd" "/usr/local/bin/$cmd"
    done
    changed "installed Tinybar"
  fi
  rm -rf "$work" "$stage"
}
