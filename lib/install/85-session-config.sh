# Session configuration. System defaults go to /etc/xdg/labwc (labwc merges your own
# ~/.config/labwc over them) and /usr/local/share/limde/autostart.d. Starting copies
# of the per-user files (launcher, file manager, locker, default apps) are put in your
# home only where you don't have one already; limde never overwrites yours.

step_session_config() {
  heading "Session configuration"
  local cfg=$LIMDE_ROOT/config n=0 f dest
  for f in rc.xml autostart environment; do
    if ! cmp -s "$cfg/labwc/$f" "/etc/xdg/labwc/$f"; then
      sudo install -D -m 644 "$cfg/labwc/$f" "/etc/xdg/labwc/$f"; n=$((n + 1))
    fi
  done
  local auto=/usr/local/share/limde/autostart.d
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
  ((kept)) && note "kept $kept config file(s) you already have (limde's versions are in $cfg/home)"
  ((added || kept)) || ok "your config files are in place"

  # Hide redundant launcher entries: a full copy of each, marked NoDisplay, in
  # /usr/local/share/applications, which takes precedence over /usr/share/applications.
  local hidden=0 name orig want_file
  while read -r name _; do
    [[ $name && $name != \#* ]] || continue
    orig=/usr/share/applications/$name
    [[ -f $orig ]] || continue
    want_file=$(sed '0,/^\[Desktop Entry\]/s//[Desktop Entry]\nNoDisplay=true/' "$orig")
    if [[ $(cat "/usr/local/share/applications/$name" 2>/dev/null) != "$want_file" ]]; then
      printf '%s\n' "$want_file" | sudo install -D -m 644 /dev/stdin "/usr/local/share/applications/$name"
      hidden=$((hidden + 1))
    fi
  done < "$cfg/hidden-apps.list"
  ((hidden)) && changed "hid $hidden redundant launcher entr$( ((hidden == 1)) && echo y || echo ies)"
  return 0
}
