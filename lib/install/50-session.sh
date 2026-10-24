# Start labwc when you log in on the first console (tty1).
# `exec` matters: if labwc ever exits or crashes, the login ends and the console shows
# a login prompt again instead of leaving a logged-in shell behind a locked screen.

PROFILE_BEGIN='# >>> elachisto session >>>'
PROFILE_END='# <<< elachisto session <<<'

profile_block() {
  cat <<'EOF'
# >>> elachisto session >>>
# Start the desktop on tty1. Managed by elachisto's installer; edit outside this block.
if [ -z "${WAYLAND_DISPLAY:-}" ] && [ "$(tty)" = /dev/tty1 ] && command -v labwc >/dev/null; then
  mkdir -p "${XDG_STATE_HOME:-$HOME/.local/state}/elachisto"
  exec labwc >"${XDG_STATE_HOME:-$HOME/.local/state}/elachisto/labwc.log" 2>&1
fi
# <<< elachisto session <<<
EOF
}

step_session() {
  heading "Session"
  local profile=$HOME/.profile want current
  want=$(profile_block)
  if [[ -f $profile ]]; then
    current=$(sed -n "/^$PROFILE_BEGIN\$/,/^$PROFILE_END\$/p" "$profile")
  else
    current=
  fi
  if [[ $current == "$want" ]]; then
    ok "labwc starts on tty1 (~/.profile)"
    return
  fi
  mkdir -p "$STATE_DIR/backups"
  [[ -f $profile ]] && cp -p "$profile" "$STATE_DIR/backups/profile.$(date +%Y%m%dT%H%M%S)"
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
  changed "labwc starts on tty1 (~/.profile; previous copy in $STATE_DIR/backups)"
}
