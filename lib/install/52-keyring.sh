# Unlock the login keyring with the password typed at the tty1 login, and start it for
# the session. libpam-gnome-keyring's pam-auth-update profile adds only its password line
# (so `passwd` changes the keyring's password too); the other two belong in a display
# manager's PAM file, and limde has no display manager, so they go in /etc/pam.d/login,
# in the places GDM's file has them: auth after common-auth, which reads the password,
# and session after common-session. Both are optional: a keyring problem never blocks a
# login.

PAM_LOGIN=/etc/pam.d/login

# gcr4, which gnome-keyring brings, turns on GNOME's SSH agent for every user. Its socket
# sets SSH_AUTH_SOCK in the user manager's environment to itself, over OpenSSH's agent
# (ssh-agent.socket, from openssh-client), and never sets it back. limDE keeps OpenSSH's
# agent as the one SSH agent: it masks both units for you, as `systemctl --user mask`
# would (links to /dev/null in ~/.config/systemd/user), whether or not the user manager
# runs. It does this once, so units you unmask later stay on.
GCR_SSH_UNITS=(gcr-ssh-agent.socket gcr-ssh-agent.service)
GCR_SSH_DONE=$STATE_DIR/gcr-ssh-agent-masked

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

# Is this unit masked for the user? $1: unit file path.
unit_masked() { [[ -L $1 && $(readlink "$1") == /dev/null ]]; }

mask_gcr_ssh_agent() {
  local dir=${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user unit made=0 kept=()
  if [[ -e $GCR_SSH_DONE ]]; then
    for unit in "${GCR_SSH_UNITS[@]}"; do
      unit_masked "$dir/$unit" || { ok "gcr-ssh-agent left on, as you set it"; return; }
    done
    ok "OpenSSH's agent is the SSH agent (gcr-ssh-agent masked)"
    return
  fi
  for unit in "${GCR_SSH_UNITS[@]}"; do
    unit_masked "$dir/$unit" && continue
    # A file of yours with that name replaces gcr's unit; leave it.
    if [[ -e $dir/$unit || -L $dir/$unit ]]; then kept+=("$unit"); continue; fi
    mkdir -p "$dir"
    ln -s /dev/null "$dir/$unit"
    made=1
  done
  mkdir -p "$STATE_DIR"; : > "$GCR_SSH_DONE"
  ((${#kept[@]})) && note "kept your own ${kept[*]} in $dir"
  if ((!made)); then
    ok "OpenSSH's agent is the SSH agent (gcr-ssh-agent masked)"
    return
  fi
  # A running user manager (a login or an SSH session) reads the links after a reload.
  # Stop gcr's agent and hand SSH_AUTH_SOCK back to OpenSSH's, which gcr's socket took.
  if systemctl --user show-environment >/dev/null 2>&1; then
    local run=${XDG_RUNTIME_DIR:-/run/user/$(id -u)} sock
    systemctl --user daemon-reload || true
    systemctl --user stop "${GCR_SSH_UNITS[@]}" 2>/dev/null || true
    sock=$(systemctl --user show-environment | sed -n 's/^SSH_AUTH_SOCK=//p')
    if [[ $sock == "$run/gcr/ssh" ]]; then
      if systemctl --user -q is-active ssh-agent.socket; then
        systemctl --user set-environment "SSH_AUTH_SOCK=$run/openssh_agent" || true
      else
        systemctl --user unset-environment SSH_AUTH_SOCK || true
      fi
    fi
  fi
  changed "masked gcr-ssh-agent, so OpenSSH's agent stays the SSH agent ($dir)"
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
  mask_gcr_ssh_agent
}
