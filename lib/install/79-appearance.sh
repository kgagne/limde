# Install the appearance renderer and its defaults system-wide, then render your own
# copies of the program styles (GTK, labwc, Tinybar, Walker, Mako, PCManFM) into your home.

APPEARANCE_SHARE=/usr/local/share/elachisto/appearance

step_appearance() {
  heading "Appearance"
  local src=$ELACHISTO_ROOT/components/appearance stage
  stage=$(mktemp -d)
  install -D -m 644 "$src/appearance.toml" "$stage/appearance.toml"
  install -D -m 644 "$src/manifest.toml" "$stage/manifest.toml"
  mkdir -p "$stage/templates"; cp "$src"/templates/*.in "$stage/templates/"
  if diff -rq "$stage" "$APPEARANCE_SHARE" >/dev/null 2>&1 \
     && cmp -s "$src/elachisto-appearance" /usr/local/bin/elachisto-appearance; then
    ok "appearance defaults are up to date"
  else
    sudo rm -rf "$APPEARANCE_SHARE"
    sudo install -d "$APPEARANCE_SHARE"
    sudo cp -a "$stage/." "$APPEARANCE_SHARE/"
    sudo install -m 755 "$src/elachisto-appearance" /usr/local/bin/elachisto-appearance
    changed "installed the appearance defaults and elachisto-appearance"
  fi
  rm -rf "$stage"

  if /usr/local/bin/elachisto-appearance --check >/dev/null 2>&1; then
    ok "your program styles match the appearance"
  else
    /usr/local/bin/elachisto-appearance --apply >"$STATE_DIR/appearance.log" 2>&1 \
      || { cat "$STATE_DIR/appearance.log" >&2; die "could not render the appearance"; }
    changed "rendered your program styles ($(grep -c '^Updated' "$STATE_DIR/appearance.log") files)"
  fi
}
