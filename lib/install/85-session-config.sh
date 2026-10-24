# Session configuration. System defaults go to /etc/xdg/labwc (labwc merges your own
# ~/.config/labwc over them) and /usr/local/share/elachisto/autostart.d. Starting copies
# of the per-user files (launcher, file manager, locker, default apps) are put in your
# home only where you don't have one already; elachisto never overwrites yours.

step_session_config() {
  heading "Session configuration"
  local cfg=$ELACHISTO_ROOT/config n=0 f dest
  for f in rc.xml autostart environment; do
    if ! cmp -s "$cfg/labwc/$f" "/etc/xdg/labwc/$f"; then
      sudo install -D -m 644 "$cfg/labwc/$f" "/etc/xdg/labwc/$f"; n=$((n + 1))
    fi
  done
  local auto=/usr/local/share/elachisto/autostart.d
  if ! diff -rq "$cfg/autostart.d" "$auto" >/dev/null 2>&1; then
    sudo rm -rf "$auto"; sudo install -d "$auto"
    sudo install -m 644 "$cfg"/autostart.d/*.sh "$auto/"; n=$((n + 1))
  fi
  ((n)) && changed "installed labwc and autostart defaults" || ok "labwc and autostart defaults are up to date"

  local added=0 kept=0 rel
  while IFS= read -r rel; do
    dest=$HOME/$rel
    local want; want=$(sed "s|@HOME@|$HOME|g" "$cfg/home/$rel")
    if [[ ! -e $dest ]]; then
      mkdir -p "$(dirname "$dest")"; printf '%s\n' "$want" > "$dest"; added=$((added + 1))
    elif [[ $(cat "$dest") != "$want" ]]; then
      kept=$((kept + 1))
    fi
  done < <(cd "$cfg/home" && find . -type f | sed 's|^\./||' | sort)
  ((added)) && changed "added $added starting config file(s) to your home"
  ((kept)) && note "kept $kept config file(s) you already have (elachisto's versions are in $cfg/home)"
  ((added || kept)) || ok "your config files are in place"
}
