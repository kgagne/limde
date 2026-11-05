# Ubuntu Server 26.04: how the installer checks the system and installs packages.
# Sourced by `install` (lib/install/common.sh::load_distro) when /etc/os-release says
# ID=ubuntu. Every distro file sets the same names; the steps use only these.

DISTRO_LABEL="Ubuntu 26.04"
# The group whose members may use sudo.
ADMIN_GROUP=sudo
# Resolved before anything changes, and again after the network switch, to tell that
# the package archive can be reached.
MIRROR_HOST=archive.ubuntu.com
PACKAGE_DIR=$LIMDE_ROOT/packages/ubuntu

# Is this a release limDE supports? Reads the variables of /etc/os-release.
distro_supported() { [[ ${ID:-} == ubuntu && ${VERSION_ID:-} == 26.04 ]]; }

installed() { dpkg-query -W -f '${db:Status-Status}' "$1" 2>/dev/null | grep -qx installed; }

# A package install was cut short (power loss, Ctrl+C) and dpkg is half done: what apt
# checks before refusing to install ("dpkg was interrupted"), or what dpkg --audit lists.
# dpkg --audit needs root to read its lock; without sudo, only the first check runs.
pkg_interrupted() {
  compgen -G '/var/lib/dpkg/updates/[0-9]*' >/dev/null && return 0
  [[ -n $(sudo -n dpkg --audit 2>/dev/null) ]]
}

# Finish an interrupted install. Output goes to the caller's log; fails if dpkg is
# still half done afterwards.
pkg_finish_interrupted() {
  sudo DEBIAN_FRONTEND=noninteractive dpkg --configure -a
  # A package that was only half unpacked needs apt to fetch and unpack it again.
  pkg_interrupted && sudo DEBIAN_FRONTEND=noninteractive apt-get install -f -y -q
  ! pkg_interrupted
}
PKG_FINISH_NOTE="dpkg --configure -a"

# Install the named packages. Output goes to the caller's log.
pkg_install() {
  sudo apt-get update -q
  # No recommends: only what is listed, plus what those packages strictly need.
  sudo DEBIAN_FRONTEND=noninteractive NEEDRESTART_SUSPEND=1 \
    apt-get install -y -q --no-install-recommends "$@"
}

# How many packages pkg_install would set up, from its log.
pkg_count_set_up() { grep -c '^Setting up' "$1"; }

# How many packages are new, dependencies included, for the plan (a simulation; no root).
pkg_count_new() {
  apt-get -s install --no-install-recommends "$@" 2>/dev/null | grep -c '^Inst ' || true
}

# After a successful install of the named (until then missing) packages.
pkg_after_install() {
  # Ubuntu's smartmontools turns on smartd, a disk-check service; limDE adds no services, so
  # switch it off once, when the laptop group first installs it (smartctl still works).
  if [[ " $* " == *" smartmontools "* ]] && systemctl -q is-enabled smartmontools.service 2>/dev/null; then
    sudo systemctl disable --now smartmontools.service >/dev/null 2>&1 && changed "switched smartd off (sudo systemctl enable --now smartmontools to turn it on)"
  fi
}
