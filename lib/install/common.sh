# Shared helpers for the installer steps. Sourced, not run.

CHANGES=0
STATE_DIR=${XDG_STATE_HOME:-$HOME/.local/state}/elachisto

if [[ -t 1 ]]; then bold=$'\e[1m'; dim=$'\e[2m'; red=$'\e[31m'; reset=$'\e[0m'
else bold=; dim=; red=; reset=; fi

die() { echo "${red}elachisto: $*${reset}" >&2; exit 1; }
heading() { echo; echo "${bold}== $* ==${reset}"; }
ok() { echo "  ok       $*"; }
changed() { echo "  ${bold}changed${reset}  $*"; CHANGES=$((CHANGES + 1)); }
note() { echo "  ${dim}$*${reset}"; }

# Ask a yes/no question. $1: question, $2: default (y or n).
ask() {
  local answer hint=$([[ $2 == y ]] && echo "Y/n" || echo "y/N")
  read -r -p "  $1 [$hint] " answer </dev/tty || answer=
  answer=${answer:-$2}
  [[ ${answer,,} == y* ]]
}

# Package names from a list file: drop comments and blank lines.
list_packages() { sed -e 's/#.*//' -e '/^\s*$/d' "$1" | awk '{print $1}'; }

# Package lines with their reasons, for the plan.
show_list() {
  sed -n -e 's/^## \(.*\)/    \1:/p' \
         -e 's/^\([a-z0-9][a-z0-9.+-]*\)\s*#\s*\(.*\)/      \1 — \2/p' "$1"
}

# A package install was cut short (power loss, Ctrl+C) and dpkg is half done: what apt
# checks before refusing to install ("dpkg was interrupted"), or what dpkg --audit lists.
# dpkg --audit needs root to read its lock; without sudo, only the first check runs.
dpkg_interrupted() {
  compgen -G '/var/lib/dpkg/updates/[0-9]*' >/dev/null && return 0
  [[ -n $(sudo -n dpkg --audit 2>/dev/null) ]]
}

installed() { dpkg-query -W -f '${db:Status-Status}' "$1" 2>/dev/null | grep -qx installed; }

# Keep sudo's ticket fresh during long steps, so the user is asked once.
sudo_keepalive() {
  # `sudo -n true` succeeds without a prompt when a ticket is cached or the user has
  # passwordless sudo; only otherwise ask for the password once.
  sudo -n true 2>/dev/null || sudo -v || die "sudo is needed to install packages"
  ( while sleep 50; do sudo -n true 2>/dev/null || exit; done ) &
  KEEPALIVE=$!
  trap 'kill "$KEEPALIVE" 2>/dev/null || true' EXIT
}

summary() {
  heading "Done"
  if ((CHANGES == 0)); then
    echo "  No changes: everything was already in place."
  else
    echo "  $CHANGES change(s) made."
    [[ $(tty 2>/dev/null) == /dev/tty1 ]] || \
      echo "  Log in on the first console (tty1) to start the desktop."
  fi
}
