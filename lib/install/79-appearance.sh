# Install the appearance renderer and its defaults system-wide, then render your own
# copies of the program styles (GTK, labwc, Tinybar, Walker, Mako, PCManFM) into your home.

APPEARANCE_SHARE=/usr/local/share/limde/appearance
# The title-bar buttons of labwc's "limde" theme; its themerc is rendered into your home.
LABWC_BUTTONS=/usr/local/share/themes/limde/labwc

step_appearance() {
  heading "Appearance"
  local src=$LIMDE_ROOT/components/appearance stage
  stage=$(mktemp -d)
  install -D -m 644 "$src/appearance.toml" "$stage/appearance.toml"
  install -D -m 644 "$src/manifest.toml" "$stage/manifest.toml"
  mkdir -p "$stage/templates"; cp "$src"/templates/*.in "$stage/templates/"
  # Root's, as everything under /usr/local; older installs were the user's.
  if diff -rq "$stage" "$APPEARANCE_SHARE" >/dev/null 2>&1 \
     && [[ -z $(find "$APPEARANCE_SHARE" \( ! -user root -o ! -perm -o+r \) -print -quit 2>/dev/null) ]] \
     && cmp -s "$src/limde-appearance" /usr/local/bin/limde-appearance; then
    ok "appearance defaults are up to date"
  else
    sudo rm -rf "$APPEARANCE_SHARE"
    sudo install -d "$APPEARANCE_SHARE"
    sudo cp -a "$stage/." "$APPEARANCE_SHARE/"
    sudo chown -R root:root "$APPEARANCE_SHARE"
    sudo chmod -R u+rwX,go+rX,go-w "$APPEARANCE_SHARE"
    sudo install -m 755 "$src/limde-appearance" /usr/local/bin/limde-appearance
    changed "installed the appearance defaults and limde-appearance"
  fi
  rm -rf "$stage"

  # labwc looks for its title-bar buttons in every folder of the theme, your home first,
  # and fills these 1-bit masks with the button colours of the themerc rendered below,
  # so the shapes are shared and the colours follow the mode.
  if diff -rq "$src/labwc-buttons" "$LABWC_BUTTONS" >/dev/null 2>&1; then
    ok "title-bar buttons are up to date"
  else
    sudo rm -rf "$LABWC_BUTTONS"
    sudo install -d "$LABWC_BUTTONS"
    sudo install -m 644 "$src"/labwc-buttons/* "$LABWC_BUTTONS/"
    changed "installed the title-bar buttons"
  fi

  if /usr/local/bin/limde-appearance --check >/dev/null 2>&1; then
    ok "your program styles match the appearance"
  else
    /usr/local/bin/limde-appearance --apply >"$STATE_DIR/appearance.log" 2>&1 \
      || { cat "$STATE_DIR/appearance.log" >&2; die "could not render the appearance"; }
    changed "rendered your program styles ($(grep -c '^Updated' "$STATE_DIR/appearance.log") files)"
  fi
}
