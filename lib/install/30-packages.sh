# Install the chosen packages from Ubuntu's archive.

step_packages() {
  heading "Packages"
  # A package install cut short (power loss, Ctrl+C) leaves dpkg half done, and apt
  # refuses to install anything until it is finished. Finish it first.
  if dpkg_interrupted; then
    mkdir -p "$STATE_DIR"
    {
      sudo DEBIAN_FRONTEND=noninteractive dpkg --configure -a
      # A package that was only half unpacked needs apt to fetch and unpack it again.
      dpkg_interrupted && sudo DEBIAN_FRONTEND=noninteractive apt-get install -f -y -q
      ! dpkg_interrupted
    } >"$STATE_DIR/dpkg-configure.log" 2>&1 \
      || { tail -n 20 "$STATE_DIR/dpkg-configure.log" >&2; die "could not finish an interrupted package install (log: $STATE_DIR/dpkg-configure.log)"; }
    changed "finished an interrupted package install (dpkg --configure -a)"
  fi
  local missing=() p
  for p in "${PACKAGES[@]}"; do installed "$p" || missing+=("$p"); done
  if ((${#missing[@]} == 0)); then
    ok "all ${#PACKAGES[@]} packages installed"
    return
  fi
  note "installing: ${missing[*]}"
  mkdir -p "$STATE_DIR"
  local log=$STATE_DIR/apt.log
  {
    sudo apt-get update -q
    # No recommends: only what is listed, plus what those packages strictly need.
    sudo DEBIAN_FRONTEND=noninteractive NEEDRESTART_SUSPEND=1 \
      apt-get install -y -q --no-install-recommends "${missing[@]}"
  } >"$log" 2>&1 || { tail -n 20 "$log" >&2; die "package installation failed (full log: $log)"; }
  note "$(grep -c '^Setting up' "$log") packages set up, including dependencies (log: $log)"
  for p in "${missing[@]}"; do installed "$p" || die "$p did not install"; done
  changed "installed ${#missing[@]} package(s)"
}
