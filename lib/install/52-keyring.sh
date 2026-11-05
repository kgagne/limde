# Unlock the login keyring with the password typed at the tty1 login, and start it for
# the session. libpam-gnome-keyring's pam-auth-update profile adds only its password line
# (so `passwd` changes the keyring's password too); the other two belong in a display
# manager's PAM file, and limde has no display manager, so they go in /etc/pam.d/login,
# in the places GDM's file has them: auth after common-auth, which reads the password,
# and session after common-session. Both are optional: a keyring problem never blocks a
# login.

PAM_LOGIN=/etc/pam.d/login

# Has the PAM file a line of this type (auth, session) for pam_gnome_keyring, in any form?
# $1: type, $2: file.
pam_keyring_line() {
  awk -v t="$1" '($1 == t || $1 == "-" t) && /pam_gnome_keyring\.so/ { found = 1 }
    END { exit !found }' "$2"
}

# Print the file with a line added right after its first "@include NAME"; fail if it has
# none. $1: file, $2: include name, $3: line.
pam_insert_after() {
  awk -v inc="$2" -v add="$3" '
    { print }
    !done && $1 == "@include" && $2 == inc { print add; done = 1 }
    END { exit !done }' "$1"
}

step_keyring() {
  heading "Login keyring"
  local work type include line added=() missing=0
  work=$(mktemp -d)
  cp "$PAM_LOGIN" "$work/new" || die "could not read $PAM_LOGIN"
  for type in auth session; do
    pam_keyring_line "$type" "$work/new" && continue
    if [[ $type == auth ]]; then
      include=common-auth line='auth       optional   pam_gnome_keyring.so'
    else
      include=common-session line='session    optional   pam_gnome_keyring.so auto_start'
    fi
    if pam_insert_after "$work/new" "$include" "$line" > "$work/next"; then
      mv "$work/next" "$work/new"; added+=("$type")
    else
      note "$PAM_LOGIN has no '@include $include' line; add '$line' to it yourself"
      missing=1
    fi
  done

  if ((${#added[@]})); then
    mkdir -p "$STATE_DIR/backups"
    cp "$PAM_LOGIN" "$STATE_DIR/backups/pam.d-login.$(date +%Y%m%dT%H%M%S)"
    # Written beside it and renamed over it, so a login at that moment never reads a
    # half-written file.
    sudo install -m 644 "$work/new" "$PAM_LOGIN.limde-new" \
      && sudo mv "$PAM_LOGIN.limde-new" "$PAM_LOGIN" \
      || { rm -rf "$work"; die "could not update $PAM_LOGIN"; }
    local what="the tty1 login unlocks the keyring"
    ((missing)) && what="added the keyring's ${added[*]} line"
    changed "$what ($PAM_LOGIN; previous copy in $STATE_DIR/backups)"
  elif ((!missing)); then
    ok "the tty1 login unlocks the keyring ($PAM_LOGIN)"
  fi
  rm -rf "$work"
}
