# Install the chosen packages with the distro's package manager (lib/install/distro).

# brightness-udev lets the video group change the backlight, and Ubuntu Server's installer
# does not put the first user in that group.
brightness_group() {
  if installed brightness-udev && ! id -nG "$USER" | grep -qw video; then
    sudo usermod -aG video "$USER" && changed "added you to the video group, for the brightness keys (from your next login)"
  fi
}

step_packages() {
  heading "Packages"
  # A package install cut short (power loss, Ctrl+C) leaves the package manager half
  # done, and it refuses to install anything until that is finished. Finish it first.
  if pkg_interrupted; then
    mkdir -p "$STATE_DIR"
    pkg_finish_interrupted >"$STATE_DIR/dpkg-configure.log" 2>&1 \
      || { tail -n 20 "$STATE_DIR/dpkg-configure.log" >&2; die "could not finish an interrupted package install (log: $STATE_DIR/dpkg-configure.log)"; }
    changed "finished an interrupted package install ($PKG_FINISH_NOTE)"
  fi
  local missing=() p
  for p in "${PACKAGES[@]}"; do installed "$p" || missing+=("$p"); done
  if ((${#missing[@]} == 0)); then
    ok "all ${#PACKAGES[@]} packages installed"
    brightness_group
    return
  fi
  note "installing: ${missing[*]}"
  mkdir -p "$STATE_DIR"
  local log=$STATE_DIR/apt.log
  pkg_install "${missing[@]}" >"$log" 2>&1 \
    || { tail -n 20 "$log" >&2; die "package installation failed (full log: $log)"; }
  note "$(pkg_count_set_up "$log") packages set up, including dependencies (log: $log)"
  for p in "${missing[@]}"; do installed "$p" || die "$p did not install"; done
  changed "installed ${#missing[@]} package(s)"
  pkg_after_install "${missing[@]}"
  brightness_group
}
