# Installing limDE

This takes you from a fresh Ubuntu Server 26.04 install to the limDE desktop. The README's
[Install](../README.md#install) section is the short version; this is the long one.

## What you need

- **Ubuntu Server 26.04 on x86_64.** The installer checks `/etc/os-release` and the
  machine type first and stops on anything else. In Ubuntu's installer, choose no extra
  snaps or server roles.
- **A normal user in the `sudo` group.** Run the installer as that user, not as root. It
  asks for your password once, when it starts changing things, and keeps sudo's ticket
  fresh until it finishes.
- **A working network connection.** The installer stops at once if `archive.ubuntu.com`
  does not resolve. It downloads Ubuntu packages, the pinned source code for labwc and
  PCManFM, the Walker and Elephant release files, and Firefox.
- **Time and disk space.** labwc and PCManFM are built on your machine. A full install
  takes about 20 to 40 minutes, most of it apt and the labwc build. In the test VM a
  finished install used about 8.9 GB of disk, Ubuntu included.

If you want to try limDE first without touching a real machine, see
[VM-TRIAL.md](VM-TRIAL.md).

## 1. Get the clone

Log in on the text console and clone the repository:

```
git clone https://github.com/kgagne/limde.git
```

```
cd limde
```

If `git` is missing, install it first:

```
sudo apt install git
```

Keep the clone where it is. The installer records its path, and `limde-update` works in
that clone later (see [UPDATE.md](UPDATE.md)). If you move it, run `./install` again from
the new place.

## 2. See the plan

```
./install --plan
```

This checks the system, lists every package limDE wants with the reason for it, lists the
optional groups, and counts how many new packages apt would add, dependencies included.
It changes nothing and asks nothing. [DEPENDENCIES.md](DEPENDENCIES.md) has the same lists
with more detail.

## 3. Choose the optional parts

The optional groups are the files in `packages/optional/`:

- `bluetooth`: BlueZ and PipeWire's Bluetooth audio. Tinybar then shows a Bluetooth menu.
- `laptop`: `brightnessctl` and its udev rule, for the brightness keys and Tinybar's
  brightness slider (without them both do nothing), plus `powertop` for power use and
  `smartmontools` for disk health.
- `papers`: GNOME Papers, a PDF and document viewer.
- `printing`: CUPS and Avahi, for printing, including to network printers.

When you run `./install` without options, it asks about each group in turn. The
suggested answer (the capital letter in `[Y/n]` or `[y/N]`) is yes in two cases:

- `laptop`, when the machine has a screen backlight (anything in `/sys/class/backlight`).
- `bluetooth`, when the machine has a Bluetooth adapter (anything in
  `/sys/class/bluetooth`).

Every other group is suggested as no. Press Return to take the suggestion.

You can also name groups on the command line with `--with=`. Groups named there are
included without a question; the installer still asks about the others:

```
./install --with=papers
```

For an install with no questions at all, add `--yes`. Then only the groups you name are
included, and none are suggested for you:

```
./install --yes --with=laptop,papers
```

A VM has no backlight, so if you install from a VM onto a disk meant for a laptop, add
`--with=laptop` yourself. An unknown group name stops the installer before it changes
anything.

## 4. Install

```
./install
```

After the questions, it asks once more before it changes anything:
"Install N packages and set up the desktop?" Answer no and nothing is changed.

The steps run in the order of the call list at the end of `install`, not in the order of
the file numbers in `lib/install/`. Each step prints a heading, then `ok` for what was
already in place or `changed` for what it did.

1. **Checking this system:** Ubuntu 26.04, x86_64, not root, in the sudo group, network.
2. **What limde installs and Optional parts:** the plan and the questions above.
3. **Packages:** installs the listed packages with apt, without recommended packages, so
   only what is listed and what those packages strictly need. If an earlier package
   install was cut short, it finishes that first (`dpkg --configure -a`).
4. **Network:** hands the network to NetworkManager (see [The network
   switch](#the-network-switch) below).
5. **labwc:** downloads the pinned labwc and wlroots commits and builds them. The new
   build must start and stop cleanly in a headless test session before it is installed
   to `/usr/local`, so a broken build never replaces a working one. This is the longest
   step.
6. **PCManFM:** downloads the pinned PCManFM release, applies limDE's two patches (Space
   preview, and Cut, Copy and Paste keys after you pick a place in the side pane), builds
   it and installs it to `/usr/local`.
7. **Launcher:** downloads the pinned Walker and Elephant release files, checks each
   against its pinned sha256, and installs them to `/usr/local`.
8. **Firefox:** downloads Mozilla's current Firefox, checks it against Mozilla's signed
   checksums, and unpacks it to `~/.local/opt/firefox`, a folder you own, so Firefox's own
   updater can keep it current. It also installs an AppArmor profile so Firefox may use
   its sandbox. Firefox is installed once; limDE never changes its version after that.
9. **Icons:** builds the `limde` (dark) and `limde-light` icon themes and installs them to
   `/usr/local/share/icons`.
10. **Tinybar:** builds the panel's small window-list helper and installs the panel.
11. **Appearance:** installs the appearance defaults, `limde-appearance` and the window
    title-bar buttons, then renders your own copies of the program styles into your home.
12. **Helpers:** installs `limde-preview`, `limde-screenshot`, `limde-clipboard-notify`,
    `limde-update` and `app-shortcut` to `/usr/local/bin`.
13. **Session configuration:** installs labwc's defaults to `/etc/xdg/labwc` and the
    autostart pieces to `/usr/local/share/limde/autostart.d`, adds the starting config
    files to your home where you don't have them yet, and hides a few redundant launcher
    entries.
14. **agent-web:** installs the agent window's command, welcome page and menu entry.
15. **Login keyring:** adds two optional lines to `/etc/pam.d/login`, after its
    `common-auth` and `common-session` lines, so your tty1 login password unlocks the
    keyring and the keyring starts with your session. Ubuntu's keyring package adds only
    the line for password changes; a display manager would carry these two. Before it
    changes the file it saves a copy in `~/.local/state/limde/backups/`.
16. **Session:** adds the block to `~/.profile` that clears the console and starts labwc
    on tty1.
17. **Install record:** writes the commit, the clone's path and your optional groups to
    `/usr/local/share/limde/installed`, for `limde-update`.

At the end it prints how many changes it made, or "No changes" when everything was
already in place.

## 5. Log in on tty1

There is no display manager. The installer adds a marked block to your `~/.profile`:

```
# >>> limde session >>>
...
# <<< limde session <<<
```

When you log in on the first console (tty1), that block starts labwc, and the desktop
comes up. On any other console you get a normal shell. If you ran the installer on tty1,
log out and back in; otherwise switch to tty1 (Ctrl+Alt+F1) and log in there.

The block uses `exec`, so if labwc ever exits, the login ends and tty1 shows a login
prompt again instead of leaving a logged-in shell behind. Before the installer changes
`~/.profile` it saves a copy in `~/.local/state/limde/backups/`.

The block clears the console before it starts labwc: tty1 shows for a moment at suspend
and resume, and without it your login text would flash up. The password you type at this
login also unlocks the login keyring, where apps keep the passwords they save.

## The network switch

Ubuntu Server manages the network with systemd-networkd through netplan. Tinybar's Wi-Fi
menu needs NetworkManager, so the Network step switches over:

1. It writes `/etc/netplan/90-limde-networkmanager.yaml`, which tells netplan to hand
   every interface to NetworkManager, and runs `netplan apply`.
2. It waits up to 30 seconds for NetworkManager to report a connection and for
   `archive.ubuntu.com` to resolve.
3. Only then does it turn off `systemd-networkd` and its socket, wait-online service and
   `networkd-dispatcher`.

If `netplan apply` fails, or no working connection comes up within 30 seconds, it removes
its netplan file, runs `netplan apply` again to put the previous setup back, and stops
with a message. Your other netplan files are never changed. See
[RECOVERY.md](RECOVERY.md#the-network) for what to do then.

After the switch, join Wi-Fi networks from the Wi-Fi icon in the panel. NetworkManager
remembers them.

## When a step fails

The installer stops at the first problem, prints a message in red, and for the longer
steps shows the last lines of the step's log. The logs are in `~/.local/state/limde/`:

- `apt.log`: package installation.
- `dpkg-configure.log`: finishing a package install that was cut short.
- `labwc-build.log`: downloading, building and testing labwc.
- `pcmanfm-build.log`: downloading, patching and building PCManFM.
- `tinybar-build.log`: building Tinybar's helper.
- `helpers-build.log`: building `app-shortcut`.
- `appearance.log`: rendering the program styles.

The launcher and Firefox steps have no log of their own; their messages are in the
installer's output.

Running `./install` again is safe. Every step checks first and changes only what is
missing or out of date, so fix the cause (often the network) and run it again:

```
./install
```

It picks up where things stand. A run that has nothing to do prints "No changes". If an
install was cut short by a power cut or Ctrl+C during package installation, the next run
finishes the half-done package install before anything else.

For problems after the install, such as a desktop that does not start, see
[RECOVERY.md](RECOVERY.md).
