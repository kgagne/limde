# Installing Arch Linux for limDE

> **Status: tested in a VM, not yet on hardware.** limDE's Arch VM tests build the base system
> below from the Arch ISO (`tests/vm/vm --distro arch base`), and the full install test passes
> on it (two runs, the second with no changes, a reboot to the desktop). No laptop install has
> been tested yet. Ubuntu Server 26.04 ([SERVER-INSTALL.md](SERVER-INSTALL.md)) is the main path.

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

## On a laptop

- **Wi-Fi in the live system:** the ISO uses iwd. Run `iwctl`, then `station wlan0 scan`,
  `station wlan0 get-networks` and `station wlan0 connect NAME` (the device may have another
  name: `device list`). Check with `ping -c 3 archlinux.org`.
- **Secure Boot** must be off for the Arch ISO and the installed systemd-boot, which are not
  signed.
- **Pick the disk by its model and size,** never by its `/dev/nvme0n1` name: with two NVMe
  drives, the names can swap between boots. `lsblk -o NAME,SIZE,MODEL` shows both.

### Another system on a second disk

limDE on Arch can go on a disk of its own beside another system. Choose only that disk in
archinstall, with its own EFI partition (archinstall's default layout does that), and the
other disk's partitions and boot loader stay untouched.

One thing changes outside that disk: installing systemd-boot adds a "Linux Boot Manager"
entry to the firmware and puts it first, so the laptop now starts Arch by default. To keep the
other system first, put the order back before you reboot, still in the live system:

```
efibootmgr
```

The `BootOrder` line lists the entry numbers; the new one is "Linux Boot Manager". Write the
order with your other system's number first, for example:

```
efibootmgr -o 0005,0006,0000
```

Then choose Arch from the firmware's boot menu (F12 on Dell laptops) when you want it.

### Laptops with an NVIDIA GPU

Arch loads the open `nouveau` driver for NVIDIA GPUs; limDE draws on the built-in Intel or
AMD GPU and installs `vulkan-nouveau` only so apps can use the NVIDIA one. After the install,
check that the NVIDIA GPU sleeps while unused (its `power/runtime_status` under
`/sys/bus/pci/devices/` should say `suspended`), since an awake one costs several watts on
battery.

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

Install, reboot, and log in on the text console as your user. On Wi-Fi, connect the installed
system once, since archinstall does not carry the live system's network over to
NetworkManager:

```
nmcli device wifi connect NAME --ask
```

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
