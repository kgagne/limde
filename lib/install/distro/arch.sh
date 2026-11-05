# Arch Linux: how the installer checks the system and installs packages.
# Sourced by `install` (lib/install/common.sh::load_distro) when /etc/os-release says
# ID=arch. It sets the same names as lib/install/distro/ubuntu.sh; the steps use only these,
# plus DISTRO for the few steps that differ (network, keyring, labwc, PCManFM, launcher,
# Firefox). Packages come from the official repositories only, never the AUR.

DISTRO=arch
DISTRO_LABEL="Ubuntu 26.04 or Arch Linux"
# The group whose members may use sudo (archinstall's sudo user is in wheel).
ADMIN_GROUP=wheel
# Resolved before anything changes, and again after the network switch.
MIRROR_HOST=archlinux.org
PACKAGE_DIR=$LIMDE_ROOT/packages/arch
# limDE's rc.xml uses labwc's custom acceleration and scroll curves, new in 0.20.3; an older
# labwc gets libinput's standard motion instead (lib/install/60-labwc.sh::labwc_rcxml).
LABWC_MIN_VERSION=0.20.3

# Arch is a rolling release: any up-to-date x86_64 install.
distro_supported() { [[ ${ID:-} == arch ]]; }

installed() { pacman -Q "$1" >/dev/null 2>&1; }

PACMAN_LOCK=/var/lib/pacman/db.lck

# A package install was cut short (power loss, Ctrl+C): pacman's lock is left behind,
# and pacman refuses to run until it is gone. Only a lock with no pacman running counts.
pkg_interrupted() { [[ -e $PACMAN_LOCK ]] && ! pgrep -x pacman >/dev/null; }

# Remove the stale lock; the next install (a full upgrade) reinstalls what was cut short.
# Output goes to the caller's log; fails if the lock is still there.
pkg_finish_interrupted() {
  pgrep -x pacman >/dev/null && { echo "pacman is running"; return 1; }
  sudo rm -f "$PACMAN_LOCK"
  [[ ! -e $PACMAN_LOCK ]]
}
PKG_FINISH_NOTE="removed pacman's stale lock"

# Install the named packages. Arch supports no partial upgrades, so this is a full
# upgrade too (-Syu). Output goes to the caller's log.
pkg_install() { sudo pacman -Syu --needed --noconfirm "$@"; }

# How many packages pkg_install installed or upgraded, from its log.
# pacman prints "(3/56) installing NAME" on a terminal and "installing NAME..." without one.
pkg_count_set_up() { grep -cE '^(\([0-9]+/[0-9]+\) )?(installing|upgrading|reinstalling) ' "$1" || true; }

# How many packages are new, dependencies included, for the plan: what pacman would
# fetch, read from the local sync database (no root; it may be a few days old).
pkg_count_new() {
  pacman -Sp --needed --print-format '%n' "$@" 2>/dev/null | grep -c . || true
}

# After a successful install of the named (until then missing) packages.
pkg_after_install() { :; }

# Printing on Arch: nss-mdns resolves printers' .local names only once its module is on the
# hosts: line of /etc/nsswitch.conf (Ubuntu's package does that itself). Add
# "mdns_minimal [NOTFOUND=return]" right before the first of resolve or dns, where nss-mdns's
# README puts it: .local names are answered (or stopped) before unicast DNS, and Arch's
# "resolve [!UNAVAIL=return]" would otherwise end the lookup first. Once, with a backup;
# a line that already names mdns is left alone, and so is the file if you edit it later.
NSSWITCH=/etc/nsswitch.conf
NSSWITCH_DONE=$STATE_DIR/arch-nsswitch-mdns

# Print the file with mdns_minimal added to its hosts: line; fail if that line has no
# resolve or dns to put it before. $1: file.
nsswitch_add_mdns() {
  awk '
    /^hosts:/ && !done {
      if ($0 ~ /mdns/) { done = 1; print; next }
      if (match($0, /[ \t](resolve|dns)([ \t[]|$)/)) {
        $0 = substr($0, 1, RSTART) "mdns_minimal [NOTFOUND=return] " substr($0, RSTART + 1)
        done = 1
      }
    }
    { print }
    END { exit !done }' "$1"
}

arch_printing_names() {
  [[ " ${CHOSEN_GROUPS[*]:-} " == *" printing "* ]] || return 0
  [[ -e $NSSWITCH_DONE ]] && return 0
  local work
  work=$(mktemp) || die "could not prepare the nsswitch edit"
  if grep -q '^hosts:.*mdns' "$NSSWITCH"; then
    ok "printer names resolve (mdns is in $NSSWITCH)"
  elif nsswitch_add_mdns "$NSSWITCH" > "$work"; then
    mkdir -p "$STATE_DIR/backups"
    cp "$NSSWITCH" "$STATE_DIR/backups/nsswitch.conf.$(date +%Y%m%dT%H%M%S)"
    sudo install -m 644 "$work" "$NSSWITCH.limde-new" && sudo mv "$NSSWITCH.limde-new" "$NSSWITCH" \
      || { rm -f "$work"; die "could not update $NSSWITCH"; }
    changed "printer names resolve: mdns_minimal in $NSSWITCH (previous copy in $STATE_DIR/backups)"
  else
    note "$NSSWITCH has no resolve or dns on its hosts: line; add mdns_minimal [NOTFOUND=return] yourself"
  fi
  rm -f "$work"
  mkdir -p "$STATE_DIR"; : > "$NSSWITCH_DONE"
}

# Arch enables no services when a package is installed. Turn on the ones limDE's lists
# need, once each: a unit is recorded in SERVICES_DONE when limDE enables it (or finds it
# on), so one you turn off later stays off.
SERVICES_DONE=$STATE_DIR/arch-services-enabled

distro_services() {
  local unit pkg pair scope enable said
  mkdir -p "$STATE_DIR"; touch "$SERVICES_DONE"
  # System services for the optional groups, then PipeWire's user units for every user.
  for pair in bluez:bluetooth.service cups:cups.socket avahi:avahi-daemon.service \
              pipewire:pipewire.socket pipewire-pulse:pipewire-pulse.socket \
              wireplumber:wireplumber.service; do
    pkg=${pair%%:*} unit=${pair#*:}
    installed "$pkg" || continue
    # A service belongs to the package lists only when its package is on them: avahi also
    # comes in as a dependency (pipewire-pulse, libcups) without the printing group.
    printf '%s\n' "${PACKAGES[@]}" | grep -qx "$pkg" || continue
    grep -qx "$unit" "$SERVICES_DONE" && continue
    # PipeWire's units are user units: enabled for every user, started at the next login.
    if [[ $pkg == pipewire* || $pkg == wireplumber ]]; then
      scope=(--global) enable=(enable) said="turned on $unit for every user (from the next login)"
    else
      scope=() enable=(enable --now) said="turned on $unit"
    fi
    if systemctl "${scope[@]}" -q is-enabled "$unit" 2>/dev/null; then
      echo "$unit" >> "$SERVICES_DONE"
    elif sudo systemctl "${scope[@]}" "${enable[@]}" "$unit" >/dev/null 2>&1; then
      echo "$unit" >> "$SERVICES_DONE"
      changed "$said"
    else
      note "could not turn on $unit"
    fi
  done
  arch_printing_names
}
