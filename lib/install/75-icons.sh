# Install elachisto's icon theme to /usr/local/share/icons/elachisto. It is built from the
# repository (components/icons) with the standard library only; GTK recolours the
# "-symbolic" icons, and the plain copies carry the theme's text colour.

ICON_THEME_DIR=/usr/local/share/icons/elachisto

# Programs that ask for plain (not "-symbolic") icon names get a fixed colour. The
# appearance's "muted" grey reads on both the dark background and the light selection.
icon_theme_color() {
  python3 - "$ELACHISTO_ROOT/components/appearance/appearance.toml" \
            "$HOME/.config/elachisto/appearance.toml" <<'PY'
import sys, tomllib
color = tomllib.load(open(sys.argv[1], 'rb'))['colors']['muted']
try:
    color = tomllib.load(open(sys.argv[2], 'rb')).get('colors', {}).get('muted', color)
except OSError:
    pass
print(color[:7])
PY
}

step_icons() {
  heading "Icons"
  local tmp; tmp=$(mktemp -d)
  python3 "$ELACHISTO_ROOT/components/icons/build_theme.py" "$tmp" --color "$(icon_theme_color)" >/dev/null \
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
