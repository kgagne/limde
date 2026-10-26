# Check the system before changing anything.

step_preflight() {
  heading "Checking this system"
  [[ $EUID -ne 0 ]] || die "run as your normal user, not root; it asks for sudo when needed"
  # shellcheck source=/dev/null
  . /etc/os-release
  [[ ${ID:-} == ubuntu && ${VERSION_ID:-} == 26.04 ]] \
    || die "limde supports Ubuntu 26.04 only (this is ${PRETTY_NAME:-unknown})"
  [[ $(uname -m) == x86_64 ]] || die "limde supports x86_64 only (this is $(uname -m))"
  command -v sudo >/dev/null || die "sudo is missing"
  id -nG | tr ' ' '\n' | grep -qx sudo || die "$(id -un) is not in the sudo group"
  getent hosts archive.ubuntu.com >/dev/null \
    || die "no network: archive.ubuntu.com does not resolve"
  ok "$PRETTY_NAME, $(uname -m), user $(id -un)"
}
