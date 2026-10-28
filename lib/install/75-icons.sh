# Install limde's icon themes to /usr/local/share/icons: "limde" for the dark mode and
# "limde-light" for the light mode. They are built from the repository
# (components/icons) with the standard library only; GTK recolours the "-symbolic"
# icons, and the plain copies carry the mode's muted grey, or an app's own colour
# shaded to read on that mode's backgrounds (brand-colours.toml).

ICON_THEMES_DIR=/usr/local/share/icons

step_icons() {
  heading "Icons"
  local tmp mode name changed_any=0
  tmp=$(mktemp -d)
  for mode in dark light; do
    python3 "$LIMDE_ROOT/components/icons/build_theme.py" "$tmp" --mode "$mode" \
      --appearance "$LIMDE_ROOT/components/appearance/appearance.toml" \
      --user "$HOME/.config/limde/appearance.toml" >/dev/null \
      || die "the $mode icon theme did not build"
  done
  for name in limde limde-light; do
    local dir=$ICON_THEMES_DIR/$name
    if [[ -d $dir ]] && diff -rq --no-dereference -x icon-theme.cache "$tmp/$name" "$dir" >/dev/null 2>&1; then
      continue
    fi
    sudo rm -rf "$dir"
    sudo mkdir -p "$ICON_THEMES_DIR"
    sudo cp -a "$tmp/$name" "$dir"
    sudo chown -R root:root "$dir"
    if command -v gtk-update-icon-cache >/dev/null; then
      sudo gtk-update-icon-cache -q -f "$dir" || true
    fi
    changed "installed the $name icon theme ($(find "$dir" -name '*.svg' | wc -l) files)"
    changed_any=1
  done
  rm -rf "$tmp"
  ((changed_any)) || ok "limde icon themes are up to date"
}
