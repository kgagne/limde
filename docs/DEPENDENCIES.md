# Dependencies

Everything limDE installs, and why. The package lists are the files in `packages/`; each
line there is a package name and a comment with its reason, and `./install --plan` prints
the same reasons. The reasons below come from those comments, with a note on where limDE
uses the package when that adds something.

apt installs these without recommended packages, so you get what is listed plus what
those packages strictly need, and nothing else.

## Runtime packages

From `packages/runtime.list`: what the desktop needs to run.

### Session

- `foot`: the default terminal (Super+Return).
- `tmux`: keeps terminal programs, such as a CLI agent, running with no terminal open.
- `swayidle`: runs the screen locker after inactivity (`config/autostart.d/20-idle.sh`).
- `swaylock`: the screen locker.
- `wlopm`: turns the screen off when idle on mains power.
- `mako-notifier`: desktop notifications.
- `network-manager`: network connections (Wi-Fi, Ethernet); replaces Server's networkd.
  See the network switch in [INSTALL.md](INSTALL.md#the-network-switch).
- `wpasupplicant`: joins Wi-Fi networks; NetworkManager only recommends it, so it is
  listed.
- `network-manager-config-connectivity-ubuntu`: one NetworkManager setting
  (`/usr/lib/NetworkManager/conf.d/20-connectivity-ubuntu.conf`) that turns on its
  connectivity check, as Ubuntu Desktop does. NetworkManager then fetches
  `http://connectivity-check.ubuntu.com/` now and then (every 5 minutes, and after each
  connection), which tells Canonical's server that an Ubuntu machine with NetworkManager
  is online; it sends no user data. With the check, NetworkManager notices a hotel or
  airport sign-in page (a captive portal) and Tinybar's Wi-Fi menu offers to open it.
  To turn the check off, remove the package or write `[connectivity]` and `enabled=false`
  in a file in `/etc/NetworkManager/conf.d/`; the Wi-Fi menu then never mentions sign-in.

### Panel and launcher

- `python3-gi`: Tinybar is written in Python with GTK.
- `gir1.2-gtk-4.0`: GTK 4 for Tinybar.
- `gir1.2-gtk4layershell-1.0`: lets Tinybar sit at the screen edge.
- `qalc`: the calculator in the launcher.
- `libgtk-4-1`: GTK 4 for the Walker launcher.
- `libgtk4-layer-shell0`: lets Walker open above other windows.
- `libpoppler-glib8t64`: PDF previews in Walker.
- `xdg-utils`: `xdg-open`, which opens the files you pick in the launcher: Elephant's
  file search hands each result to it. It is only a recommended package of
  `wl-clipboard`, so it is listed.

### Files and preview

- `pcmanfm`: the file manager. limDE later builds its own PCManFM with Space preview,
  which takes precedence; Ubuntu's package stays installed for its supporting files and
  dependencies.
- `gvfs`: trash, mounting and other file-manager features.
- `gvfs-backends`: network shares and phones in the file manager.
- `desktop-file-utils`: keeps the application menu up to date.
- `fd-find`: fast file search in the launcher. Ubuntu names the command `fdfind`, so the
  installer links `/usr/local/bin/fd` to it.
- `zenity`: simple file-open and question dialogs.
- `poppler-utils`: PDF pages in the Space preview (`pdftoppm`, used by `limde-preview`).

### Firefox (Mozilla's build; needed by agent-web)

- `libgtk-3-0t64`: GTK 3, which Firefox uses.
- `libasound2t64`: sound in Firefox.
- `libx11-xcb1`: Firefox's X11 compatibility.
- `libnotify4`: Firefox loads it to send system notifications, which Mako then shows.
  limDE has no desktop portal, so without it Firefox and the agent window draw their own
  popups instead.

### Screenshots and clipboard

- `grim`: screenshots (`limde-screenshot`).
- `slurp`: choosing a region for a screenshot.
- `wl-clipboard`: copy and paste from the command line. `limde-screenshot` copies with
  `wl-copy`, and the cut-and-copy notice watches with `wl-paste`.
- `libglib2.0-bin`: `gdbus`, which sends notifications for screenshots and cut or copied
  files.
- `wtype`: sends keystrokes for some keyboard shortcuts (`app-shortcut`, behind Super+W
  and Super+Q), and presses Alt+Super+H at login to put the pointer in the middle of the
  screen (`80-pointer.sh`).

### Sound

- `pipewire`: the sound server.
- `pipewire-pulse`: sound for apps that expect PulseAudio.
- `pipewire-alsa`: sound for apps that use ALSA directly.
- `wireplumber`: chooses and connects sound devices.
- `rtkit`: glitch-free sound scheduling.
- `alsa-ucm-conf`: the device profiles (UCM) that name and route the inputs and outputs
  of many laptops' sound hardware, Intel's SOF among them; without them such a laptop
  has no usable sound.
- `alsa-topology-conf`: the audio DSP topology some Intel laptops need.
  `libasound2-data` only recommends this and `alsa-ucm-conf`, so both are listed.

### Login keyring and fonts

- `gnome-keyring`: stores passwords and keys for apps.
- `libpam-gnome-keyring`: the login module that unlocks the keyring with your password
  when you log in on tty1, and starts it for the session. The package itself adds only
  the line that changes the keyring's password when you change yours with `passwd`; the
  installer's Login keyring step adds the other two to `/etc/pam.d/login` (see
  [INSTALL.md](INSTALL.md#4-install)). An automatic login, with no password typed, cannot
  unlock it.
- `fonts-open-sans`: the interface font.

## Build packages

From `packages/build.list`: compilers and headers for the parts limDE builds from source.
They stay installed so updates and rebuilds work without asking again.

### Build tools

- `build-essential`: the C compiler and make.
- `git`: downloads the pinned source code.
- `meson`: the build system labwc and wlroots use.
- `ninja-build`: runs the builds meson prepares.
- `pkg-config`: finds the libraries a build needs.
- `scdoc`: builds labwc's manual pages.

### labwc and wlroots

- `libwayland-dev`: Wayland protocol library.
- `libwayland-bin`: generates Wayland protocol code.
- `wayland-protocols`: Wayland protocol definitions.
- `libxkbcommon-dev`: keyboard layouts.
- `libinput-dev`: mice, touchpads and keyboards.
- `libudev-dev`: finding input and display devices.
- `libseat-dev`: access to displays and input without root.
- `libdrm-dev`: talking to the graphics driver.
- `libgbm-dev`: graphics buffers.
- `libegl-dev`: OpenGL ES setup.
- `libgles-dev`: OpenGL ES rendering.
- `libpixman-1-dev`: software rendering.
- `libdisplay-info-dev`: reading monitor capabilities.
- `libliftoff-dev`: efficient use of display planes.
- `liblcms2-dev`: colour management.
- `hwdata`: monitor vendor names.
- `libcairo2-dev`: drawing window decorations.
- `libpango1.0-dev`: text in window titles and menus.
- `librsvg2-dev`: SVG icons and theme buttons.
- `libpng-dev`: PNG icons.
- `libxml2-dev`: reading labwc's XML configuration.
- `libsfdo-dev`: finding application icons and menu entries.
- `libgio-2.0-dev`: GLib, used by labwc.
- `libxcb1-dev`, `libxcb-composite0-dev`, `libxcb-ewmh-dev`, `libxcb-icccm4-dev`,
  `libxcb-render0-dev`, `libxcb-res0-dev`, `libxcb-xfixes0-dev`: X11 apps through
  Xwayland.
- `xwayland`: runs older X11 apps inside the Wayland desktop.

### PCManFM with Space preview

- `autoconf`, `automake`, `libtool`: prepare PCManFM's build scripts.
- `intltool`: PCManFM's translations.
- `libx11-dev`: PCManFM's desktop-icons mode.
- `libgtk-3-dev`: GTK 3, which PCManFM uses.
- `libfm-dev`: the file-manager library PCManFM is built on.
- `libfm-gtk3-dev`: its GTK 3 widgets.

## Optional groups

From `packages/optional/`. Each file is one group; its first comment line is the group's
description. [INSTALL.md](INSTALL.md#3-choose-the-optional-parts) explains how to choose
them.

### bluetooth

Bluetooth: headphones, speakers, keyboards and mice, from the panel.

- `bluez`: the Bluetooth service, and `bluetoothctl` for "Other device…" in Tinybar's
  Bluetooth menu.
- `libspa-0.2-bluetooth`: sound through Bluetooth headphones and speakers (PipeWire).

### laptop

Laptop extras: screen brightness keys, power use and disk health tools.

- `brightnessctl`: changes screen brightness. `tinybar-brightness`, which the brightness
  keys and Tinybar's brightness slider run, uses it.
- `brightness-udev`: a udev rule that gives the `video` group write access to the
  backlight, so `brightnessctl` works without root for a user in that group. Ubuntu's
  `brightnessctl` only recommends it, and without it the keys and the slider fail.
- `powertop`: shows what uses power on battery, process by process and device by device
  (`sudo powertop`). Its service that changes power settings at boot stays off.
- `smartmontools`: reads the disks' health (`sudo smartctl -a` and a disk, such as
  `/dev/nvme0`; `sudo smartctl --scan` lists them). The package also starts `smartd`,
  which checks the disks every 30 minutes and logs problems to the journal; turn it off
  with `sudo systemctl disable --now smartmontools`.

### papers

A PDF and document viewer (GNOME Papers).

- `papers`: the document viewer. The starting `~/.config/mimeapps.list` names it for PDF,
  DjVu and TIFF files.

### printing

Printing, including finding network printers automatically.

- `cups`: the print system.
- `avahi-daemon`: finds printers on the local network.
- `libnss-mdns`: lets the system resolve those printers' names.

## From outside apt

These come from upstream projects at versions pinned in `pins/`. Moving a pin is a commit
to that file; `./install` rebuilds or downloads again only when a pin changes (for
PCManFM, also when one of limDE's patches changes).

### labwc, with wlroots built in (`pins/labwc`)

- labwc 0.20.3, from `https://github.com/labwc/labwc.git`, pinned by tag and commit.
- wlroots 0.20.2, from `https://gitlab.freedesktop.org/wlroots/wlroots.git`, pinned by
  commit and built into labwc as a static subproject.

Why from source: Ubuntu 26.04's labwc is older than the custom pointer acceleration and
scroll curves limDE's touchpad settings need. The build is installed to `/usr/local`
only after it starts and stops cleanly in a headless test session.

### Walker and Elephant (`pins/launcher`)

Walker (the launcher) and Elephant (its data service) come from their upstream GitHub
release files, not built from source:

- Walker 2.17.2: `walker-v2.17.2-x86_64-unknown-linux-gnu.tar.gz`.
- Elephant 2.22.1: `elephant-linux-amd64.tar.gz`.
- Elephant's providers at 2.22.1: `calc`, `desktopapplications`, `files` and
  `providerlist`, one release file each.

`pins/launcher` lists each file's URL and sha256. The installer checks every download
against its sha256 before using it, and installs the programs to `/usr/local/bin` and the
providers to `/usr/local/lib/elephant`.

### PCManFM with limDE's patches (`pins/pcmanfm`)

- PCManFM 1.4.0, from `https://github.com/lxde/pcmanfm.git`, pinned by tag and commit.
- `components/preview/pcmanfm-space-preview.patch`: Space preview. It is proposed
  upstream as `https://github.com/lxde/pcmanfm/pull/64`.
- `components/pcmanfm/pcmanfm-focus-file-shortcuts.patch`: Cut, Copy and Paste keys that
  work after you pick a place in the side pane.
- `components/pcmanfm/pcmanfm-icon-spacing.patch`: as much space after a list's icons as
  before them.
- `components/pcmanfm/pcmanfm-own-gtk-theme.patch`: `PCMANFM_GTK_THEME`, a GTK theme for
  PCManFM alone. `GTK_THEME` would also reach every app PCManFM opens.

The patches are GPL-2.0-or-later, like PCManFM. The build is installed to `/usr/local`,
with the program itself in `/usr/local/libexec/limde/`. `/usr/local/bin/pcmanfm`
(`components/pcmanfm/pcmanfm`) starts it in the panel's GTK theme and takes precedence
over Ubuntu's `pcmanfm`.

### Firefox (`pins/firefox`)

Firefox comes from Mozilla, not Ubuntu, because Ubuntu's is a snap. `pins/firefox` pins
no version. It holds:

- the fingerprint of Mozilla's release signing key,
- where to look up the current Firefox version,
- where Mozilla's release files are.

The installer fetches the current release once, in your system's language when Mozilla
builds it (otherwise `en-US`). It installs it only if Mozilla's key matches the pinned
fingerprint, the key's signature on the release's `SHA256SUMS` verifies, and the
download matches its checksum there. Firefox goes to `~/.local/opt/firefox`; after that,
Firefox's own updater keeps it current and limDE never changes its version.

### Built from limDE's own source

These are in the repository and built or copied at install time, with nothing
downloaded: Tinybar's window-list helper (C), `app-shortcut` (C), and the icon themes
(Python standard library only).
