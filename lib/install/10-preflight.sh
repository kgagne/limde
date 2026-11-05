# Check the system before changing anything.

step_preflight() {
  heading "Checking this system"
  [[ $EUID -ne 0 ]] || die "run as your normal user, not root; it asks for sudo when needed"
  load_distro
  [[ $(uname -m) == x86_64 ]] || die "limde supports x86_64 only (this is $(uname -m))"
  command -v sudo >/dev/null || die "sudo is missing"
  id -nG | tr ' ' '\n' | grep -qx "$ADMIN_GROUP" || die "$(id -un) is not in the $ADMIN_GROUP group"
  getent hosts "$MIRROR_HOST" >/dev/null \
    || die "no network: $MIRROR_HOST does not resolve"
  ok "$PRETTY_NAME, $(uname -m), user $(id -un)"
}
