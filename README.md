# elachisto

*elachisto* (ελάχιστο) is Greek for "minimum".

A small Wayland desktop for Ubuntu Server: labwc, a compact panel (Tinybar), the Walker
launcher, a consistent dark theme, Space-bar file preview in PCManFM, and a persistent
window for a web-based AI agent. Install Ubuntu Server 26.04, clone this repository,
run `./install`, and log in.

> **Status: beta (`v1.0.0-beta.1`).** It installs and runs, but it has been tested on one
> laptop and in QEMU only. Expect rough edges, and see [Known gaps](#known-gaps).

## Philosophy

- **Minimal, but not dogmatic.** The installer lists every package it wants, with the
  reason for it, before installing anything. Optional pieces are optional, and you choose
  them.
- **Built from source where it matters.** labwc is built from a pinned upstream commit,
  because the newest pointer-acceleration and scrolling work is often not in a release
  or in Ubuntu's package yet. Everything else comes from Ubuntu or from pinned upstream
  releases.
- **Yours to change.** Shipped defaults sit apart from your own changes, so updates
  don't overwrite them.

## Install

You need a fresh **Ubuntu Server 26.04** (x86_64) install, a normal user with `sudo`, and a
network connection. Choose no extra snaps or server roles in Ubuntu's installer.

1. Log in on the text console and clone this repository:

   ```
   git clone <this repository's URL> elachisto
   cd elachisto
   ```

2. See the plan without changing anything:

   ```
   ./install --plan
   ```

3. Install. The installer shows each package and its reason, asks about the optional
   parts, then installs. labwc, PCManFM and the launcher are built from source, which takes
   a while (about 20–40 minutes on a slow disk).

   ```
   ./install
   ```

4. Log out and back in on tty1. labwc starts by itself; there is no display manager.

Wi-Fi: if Ubuntu's installer didn't join a network, run `nmtui` in a terminal once.
NetworkManager remembers it after that.

### Optional parts

| Group | Adds | Pick it when |
| --- | --- | --- |
| `laptop` | `brightnessctl` | the machine has a screen backlight; without it the brightness keys do nothing |
| `papers` | GNOME Papers | you want a PDF and document viewer |
| `printing` | CUPS, Avahi | you print, including to network printers |

The interactive installer suggests `laptop` when it finds a backlight. For unattended
installs, name the groups yourself:

```
./install --yes --with=laptop,papers
```

If you install from a VM onto a USB stick or another disk for a laptop, add
`--with=laptop`: the VM has no backlight, so it won't be suggested.

## Using it

| Keys | Does |
| --- | --- |
| Super+Return | terminal (foot) |
| Super+Space | launcher (Walker): apps, files, calculator |
| Super+L | lock the screen |
| Super+W / Super+Q | close the tab or window / quit the app |
| Super+Escape | pass every key to the focused window (VMs, remote desktops); press again to undo |
| Print / Shift+Print | screenshot a region / the whole screen, saved and copied |
| Ctrl+Print | copy a region to the clipboard only |
| Volume and brightness keys | change them, with a short readout in the panel |

In PCManFM, select a file and press Space to preview it.

**agent-web** is the window at the left of the panel. On first start it shows a page of
common web agents. Open yours and sign in; after that the window keeps to that site and
opens other links in your main Firefox. See `components/agent-web/README.md`.

## Customizing

Your own files override elachisto's, and the installer never overwrites them:

- **labwc:** put only the settings you change in `~/.config/labwc/rc.xml`. labwc merges it
  over elachisto's defaults in `/etc/xdg/labwc/`.
- **Session start:** add scripts to `~/.config/elachisto/autostart.d/`. A file with the
  same name as one of elachisto's replaces it, and an empty one turns that piece off.
- **Theme:** colours, fonts and icons live in `~/.config/elachisto/appearance.toml`, which
  needs only the keys you change. `elachisto-appearance` shows what would change, and
  `elachisto-appearance --apply` writes it, backing up what it replaces.
- **Panel:** `~/.config/tinybar/settings.toml` (see `components/tinybar/README.md`).

## Updating

```
git pull
./install
```

Running `./install` again is safe. Each step checks first and only changes what is missing
or out of date, including the pinned source builds in `pins/`.

## Known gaps

- Tested on one Dell laptop with Intel graphics, booted from a USB stick, and in QEMU. Not
  yet installed to a laptop's internal drive. Sound, suspend and resume, the lid and the
  battery readout haven't been checked on real hardware yet.
- Tinybar's Wi-Fi list is display-only. Join networks with `nmtui`.
- On NVIDIA laptops, the desktop runs on the integrated GPU. The NVIDIA card is left to
  Ubuntu's open nouveau driver; elachisto doesn't set up NVIDIA's driver.
- There is no uninstaller yet.
- Ubuntu 26.04 only.

Bug reports are welcome. Please include your hardware and the output of
`journalctl -b -p warning`.

## How this was made

elachisto grew out of one person's daily-driver laptop setup. It was designed, tested
and directed by its author over many iterations, and much of the implementation, review
and documentation was done with AI coding tools working from that guidance. Without that
tooling, a project of this scope would not have been practical for one person. Every
change was steered and accepted by a human, and tested on real hardware and in VMs.

## Licence

MIT for elachisto's own code (see `LICENSE`). Some files come from or patch other
projects and keep their own licences; `REUSE.toml` lists them.
