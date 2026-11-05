# Start labwc when you log in on the first console (tty1).
# `exec` matters: if labwc ever exits or crashes, the login ends and the console shows
# a login prompt again instead of leaving a logged-in shell behind a locked screen.

PROFILE_BEGIN='# >>> limde session >>>'
PROFILE_END='# <<< limde session <<<'

profile_block() {
  cat <<'EOF'
# >>> limde session >>>
# Start the desktop on tty1. Managed by limde's installer; edit outside this block.
if [ -z "${WAYLAND_DISPLAY:-}" ] && [ "$(tty)" = /dev/tty1 ] && command -v labwc >/dev/null; then
  mkdir -p "${XDG_STATE_HOME:-$HOME/.local/state}/limde"
  # Clear the console, so the login text doesn't flash up when tty1 shows at suspend and resume.
  printf '\033[H\033[2J\033[3J'
  exec labwc --merge-config >"${XDG_STATE_HOME:-$HOME/.local/state}/limde/labwc.log" 2>&1
fi
# <<< limde session <<<
EOF
}

# The file a bash login shell reads: the first of these that exists, as bash itself picks.
# Ubuntu's new homes have only ~/.profile; Arch's also have ~/.bash_profile, and then bash
# never reads ~/.profile.
login_file() {
  local name
  for name in .bash_profile .bash_login; do
    [[ -f $HOME/$name ]] && { echo "$HOME/$name"; return; }
  done
  echo "$HOME/.profile"
}

step_session() {
  heading "Session"
  local profile want current name
  profile=$(login_file); name=${profile#"$HOME"/}
  want=$(profile_block)
  if [[ -f $profile ]]; then
    current=$(sed -n "/^$PROFILE_BEGIN\$/,/^$PROFILE_END\$/p" "$profile")
  else
    current=
  fi
  if [[ $current == "$want" ]]; then
    ok "labwc starts on tty1 (~/$name)"
    return
  fi
  mkdir -p "$STATE_DIR/backups"
  [[ -f $profile ]] && cp -p "$profile" "$STATE_DIR/backups/${name#.}.$(date +%Y%m%dT%H%M%S)"
  local tmp block; tmp=$(mktemp); block=$(mktemp)
  if [[ -n $current ]]; then   # replace an older block in place
    echo "$want" > "$block"
    awk -v b="$PROFILE_BEGIN" -v e="$PROFILE_END" -v f="$block" '
      $0 == b { while ((getline line < f) > 0) print line; skip = 1; next }
      $0 == e { skip = 0; next }
      !skip' "$profile" > "$tmp"
    rm -f "$block"
  else
    { [[ -f $profile ]] && cat "$profile"; echo; echo "$want"; } > "$tmp"
  fi
  mv "$tmp" "$profile"
  changed "labwc starts on tty1 (~/$name; previous copy in $STATE_DIR/backups)"
}
