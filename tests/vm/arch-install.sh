#!/usr/bin/env bash
# Unattended Arch install for the TEST base image only (tests/vm/vm --distro arch base).
# The Arch ISO runs this from its `script=` boot parameter, as root on tty1. It copies
# its output to the serial console, runs archinstall with the answers served next to it
# (archinstall.json, archinstall-creds.json; @SEED_URL@ is filled in by the script) and
# powers off. The last serial line says whether it worked.
exec > >(tee /dev/ttyS0) 2>&1
seed=@SEED_URL@
echo "limde-arch-install: waiting for the live system (pacman keyring, network)"
systemctl is-system-running --wait >/dev/null 2>&1 || true
if archinstall --config-url "$seed/archinstall.json" --creds-url "$seed/archinstall-creds.json" \
    --silent --skip-version-check; then
  echo "limde-arch-install: done"
else
  echo "limde-arch-install: FAILED (exit $?)"
  tail -n 40 /var/log/archinstall/install.log 2>/dev/null || true
fi
sync
systemctl poweroff
