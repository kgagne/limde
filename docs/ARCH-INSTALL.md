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
- **labwc 0.20.3 or newer must be in Arch's repositories.** limDE's touchpad settings need
  it. On 2026-11-05 it was still in `extra-testing` (stable `extra` had 0.20.2), and the
  installer stops with a message until `sudo pacman -Syu` brings it.

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

- **labwc** is Arch's own package. limDE does not build it, but checks it is 0.20.3 or newer
  and that it starts headless with limDE's settings without a configuration error. After a
  `pacman -Syu` that updates labwc, run `./install` again to repeat that check.
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

## Printing: one manual step

With the printing group, printers on your network are found, but their names (`printer.local`)
resolve only once mDNS is in `/etc/nsswitch.conf`. limDE does not edit that file yet. Add
`mdns_minimal [NOTFOUND=return]` to its `hosts:` line, before `resolve`, as the
[Arch wiki](https://wiki.archlinux.org/title/Avahi#Hostname_resolution) describes.
