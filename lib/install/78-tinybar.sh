# Install Tinybar: the panel in /usr/local/share/limde/tinybar, its commands in
# /usr/local/bin. The window-list helper is compiled here from its C source.

TINYBAR_SHARE=/usr/local/share/limde/tinybar

step_tinybar() {
  heading "Tinybar (the panel)"
  local src=$LIMDE_ROOT/components/tinybar work log
  work=$(mktemp -d); log=$STATE_DIR/tinybar-build.log
  mkdir -p "$STATE_DIR"
  cp -r "$src/." "$work/"
  (cd "$work" && sh build.sh) >"$log" 2>&1 || { tail -n 20 "$log" >&2; die "Tinybar's helper did not build (log: $log)"; }

  local stage; stage=$(mktemp -d)
  install -D -m 755 "$work/tinybar.py" "$stage/share/tinybar.py"
  install -D -m 644 "$work/tinybar_icons.py" "$stage/share/tinybar_icons.py"
  install -D -m 755 "$work/build/toplevel-helper" "$stage/share/toplevel-helper"
  local cmd
  for cmd in tinybar tinybar-volume tinybar-brightness tinybar-idle; do
    install -D -m 755 "$work/$cmd" "$stage/bin/$cmd"
  done

  local same=1
  diff -rq "$stage/share" "$TINYBAR_SHARE" >/dev/null 2>&1 || same=0
  # Root's, so the session cannot change the panel's code (or leave a __pycache__
  # that reads as a change on every update); older installs were the user's.
  [[ -z $(find "$TINYBAR_SHARE" \( ! -user root -o ! -perm -o+r \) -print -quit 2>/dev/null) ]] || same=0
  for cmd in tinybar tinybar-volume tinybar-brightness tinybar-idle; do
    cmp -s "$stage/bin/$cmd" "/usr/local/bin/$cmd" || same=0
  done
  if ((same)); then
    ok "Tinybar is up to date"
  else
    sudo rm -rf "$TINYBAR_SHARE"
    sudo install -d "$TINYBAR_SHARE"
    sudo cp -a "$stage/share/." "$TINYBAR_SHARE/"
    sudo chown -R root:root "$TINYBAR_SHARE"
    sudo chmod -R u+rwX,go+rX,go-w "$TINYBAR_SHARE"
    for cmd in tinybar tinybar-volume tinybar-brightness tinybar-idle; do
      sudo install -m 755 "$stage/bin/$cmd" "/usr/local/bin/$cmd"
    done
    changed "installed Tinybar"
  fi
  rm -rf "$work" "$stage"
}
