# Install elachisto's icon theme to /usr/local/share/icons/elachisto. It is built from the
# repository (components/icons) with the standard library only; GTK recolours the
# "-symbolic" icons, and the plain copies carry the theme's text colour.

ICON_THEME_DIR=/usr/local/share/icons/elachisto
ICON_THEME_COLOR=#eeeeee

step_icons() {
  heading "Icons"
  local tmp; tmp=$(mktemp -d)
  python3 "$ELACHISTO_ROOT/components/icons/build_theme.py" "$tmp" --color "$ICON_THEME_COLOR" >/dev/null \
    || die "the icon theme did not build"
  if [[ -d $ICON_THEME_DIR ]] && diff -rq --no-dereference -x icon-theme.cache "$tmp/elachisto" "$ICON_THEME_DIR" >/dev/null 2>&1; then
    rm -rf "$tmp"
    ok "elachisto icon theme is up to date"
    return
  fi
  sudo rm -rf "$ICON_THEME_DIR"
  sudo mkdir -p "$(dirname "$ICON_THEME_DIR")"
  sudo cp -a "$tmp/elachisto" "$ICON_THEME_DIR"
  sudo chown -R root:root "$ICON_THEME_DIR"
  rm -rf "$tmp"
  if command -v gtk-update-icon-cache >/dev/null; then
    sudo gtk-update-icon-cache -q -f "$ICON_THEME_DIR" || true
  fi
  changed "installed the elachisto icon theme ($(find "$ICON_THEME_DIR" -name '*.svg' | wc -l) files)"
}
