# Installing Arch Linux for limDE

> **Status: in progress, not tested on hardware.** The Arch path is new. Its package lists
> and installer branches are written, and the base system below is what limDE's Arch VM
> tests build (`tests/vm/vm --distro arch base`), but no Arch install of limDE has been
> tested yet, in a VM or on a laptop. Ubuntu Server 26.04 ([SERVER-INSTALL.md](SERVER-INSTALL.md))
> is the tested path.

limDE goes on top of a minimal Arch Linux system with NetworkManager. This page assumes you
have installed Arch before, or are happy to follow the
[Arch installation guide](https://wiki.archlinux.org/title/Installation_guide).
`archinstall`, the guided installer on the Arch ISO, is the shortest way.

## Before you start

- **Back up your files.** Installing Arch erases the disk you choose.
- **Use an up-to-date ISO** from archlinux.org, written to a USB stick.
- **labwc:** limDE's MacBook-like touchpad curves need labwc 0.20.3 or newer. On 2026-11-05
  Arch's stable `extra` had 0.20.2 (0.20.3 was in `extra-testing`). With an older labwc the
  installer says "labwc 0.20.2: standard touchpad feel until 0.20.3" and installs its
  settings with libinput's standard pointer motion and scrolling. Run `./install` again after
  `sudo pacman -Syu` brings 0.20.3, and it switches to the curves. limDE's VM tests stay
  pinned to the 2026-11-01 repositories (testing that fallback) until 0.20.3 reaches stable
  `extra`; they never use the testing repositories.

## archinstall's answers

Start `archinstall` from the ISO and set:

- **Disk configuration:** a layout of your choice; ext4 on one partition is what limDE's
  VM tests use, with systemd-boot.
- **Profile:** Minimal. limDE brings the desktop; do not choose a desktop profile.
- **Network configuration:** NetworkManager (`nm`). limDE uses it for the panel's Wi-Fi.
- **User account:** your user, as a **superuser** (archinstall puts it in `wheel` and
  allows `wheel` in sudo). limDE runs as this user and asks for sudo when needed.
- **Additional packages:** `git`, to download limDE.
- **Audio, desktop, greeter:** none. limDE installs PipeWire and starts its desktop when you
  log in on the first console (tty1); it uses no display manager.

Install, reboot, and log in on the text console as your user.

## Install limDE

```
git clone https://github.com/kgagne/limde.git
```

```
cd limde
```

```
./install
```

The installer shows what it will install from Arch's repositories, asks about the optional
parts, then installs them with a full upgrade (`pacman -Syu`; Arch supports no partial
upgrades). Everything comes from the official repositories; limDE never uses the AUR. Then it
continues as on Ubuntu ([INSTALL.md](INSTALL.md)).

What differs from Ubuntu:

- **labwc** is Arch's own package. limDE does not build it, but checks that it starts headless
  with limDE's settings without a configuration error (with the standard touchpad settings
  before 0.20.3). After a `pacman -Syu` that updates labwc, run `./install` again to repeat
  that check and, from 0.20.3, to switch to the touchpad curves.
- **PCManFM** with limDE's Space preview is built from the same pinned source and patches as
  on Ubuntu, as a local package called `limde-pcmanfm` (`pacman -Qi limde-pcmanfm`), so
  pacman knows its files. Arch's own `pcmanfm` package stays installed beside it.
- **Services:** Arch turns none on by itself. limDE turns on NetworkManager, and once each,
  BlueZ, CUPS and Avahi (when you chose those groups) and PipeWire's user units. One you turn
  off afterwards stays off.
- **Login keyring:** limDE adds the `pam_gnome_keyring` lines to `/etc/pam.d/login` and
  `/etc/pam.d/passwd` itself, with a copy of each file first in
  `~/.local/state/limde/backups`. When a pacman update ships a new version of either file,
  pacman keeps yours and leaves the new one beside it as `.pacnew`.
- **Firefox** needs no AppArmor profile on Arch.

## Printing

With the printing group, printers on your network are found by Avahi, but their names
(`printer.local`) resolve only once mDNS is on the `hosts:` line of `/etc/nsswitch.conf`,
which Ubuntu's package does by itself and Arch's does not. So limDE adds
`mdns_minimal [NOTFOUND=return]` right before `resolve` (or `dns`), as nss-mdns's README and
the [Arch wiki](https://wiki.archlinux.org/title/Avahi#Hostname_resolution) describe, once,
with a copy of the file first in `~/.local/state/limde/backups`. A line that already names
mdns is left alone, and so are your later edits.
