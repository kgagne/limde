# Installing Ubuntu Server for limDE

limDE goes on top of a fresh **Ubuntu Server 26.04** install. This page walks through
Ubuntu's Server installer, screen by screen, with the answers limDE expects. Then it
lists what you can switch off afterwards for a lighter laptop. When Ubuntu is installed,
go on with [INSTALL.md](INSTALL.md).

No programming is needed. You type a few commands, each shown on its own.

## Why 26.04 only

Ubuntu 26.04 is a long-term support (LTS) release, with updates for years. It is the only
release limDE is tested on, so the installer refuses every other version, 26.10
included. A newer release can change package names or versions that limDE depends on.

## Before you start

- **Back up your files.** The steps below erase the whole disk, including any system on
  it now.
- **Download the installer image.** Get "Ubuntu Server 26.04" for x86_64 (amd64) from
  ubuntu.com. limDE's tests use `ubuntu-26.04.1-live-server-amd64.iso`.
- **Write it to a USB stick** with a USB image writer, then start the laptop from the
  stick (your laptop's boot menu key picks the stick).
- **Plug in a network cable if you can.** The Server installer can join Wi-Fi, but
  limDE's tests use a wired connection. A USB network adapter works as a cable too.
  Once limDE is installed, you join Wi-Fi from the panel.

## The installer, screen by screen

Move with the arrow keys and Tab, choose with Space, and confirm with Return. Most
screens end with a **Done** button.

### Language and keyboard

1. **Language:** pick yours. limDE's own texts are in English.
2. **Installer update available:** this screen shows only when a newer installer exists.
   Either answer works. limDE's tests continue without the update.
3. **Keyboard configuration:** pick your layout. This sets the text console. The
   desktop uses the US layout until you set yours in labwc (see
   [After the install](#after-the-install)).

### Type of install

4. **Choose the type of installation:** choose **Ubuntu Server**, the default. Do not
   choose "Ubuntu Server (minimized)". limDE is tested only on the standard one, and the
   minimized one leaves out things meant for a person who logs in.

   Leave "Search for third-party drivers" off, as the tests do, unless you know your
   Wi-Fi or graphics needs one.

### Network, proxy and mirror

5. **Network configuration:** with a cable plugged in, the wired connection gets an
   address by itself. Check that it shows one, then choose Done. limDE's installer
   later hands the network to NetworkManager, so there is nothing else to set here.
6. **Proxy configuration:** leave it empty, unless your network needs a proxy.
7. **Ubuntu archive mirror:** keep the suggested mirror. The installer tests it; wait
   until the test passes.

### Storage

8. **Guided storage configuration:** choose **Use an entire disk** and pick the
   laptop's internal disk.

   - **"Set up this disk as an LVM group"** is ticked by default. limDE's tests install
     without LVM (plain partitions). Both work with limDE; untick it to match the
     tests, unless you want encryption.
   - **"Encrypt the LVM group with LUKS"** encrypts the disk. Then you type a passphrase
     each time the laptop starts, before the login prompt. limDE does not change the
     boot, so this works the same with or without limDE, but limDE's tests do not use
     it. Encryption needs the LVM box ticked.

9. **Storage configuration:** a summary of the partitions. Choose Done.
10. **Confirm destructive action:** this is the point where the disk is erased. Choose
    Continue only if you have your backups.

### Your account

11. **Profile configuration:** your name, a name for the computer, your username and a
    password. This user can use `sudo`, which limDE needs. You log in with this
    username and password on the text console, and the same password unlocks the
    keyring where apps keep saved passwords.
12. **Upgrade to Ubuntu Pro:** choose **Skip for now**. limDE does not need it. You can
    attach Pro later with `sudo pro attach` if you want it.

### SSH and snaps

13. **SSH configuration:** "Install OpenSSH server" is optional. Tick it if you want to
    log in to this laptop from another computer, for example to copy commands into it or
    to fix it when the desktop does not start ([RECOVERY.md](RECOVERY.md)). Leave it off
    if you will only use the laptop itself. limDE's tests tick it.
14. **Featured server snaps:** select none. limDE needs no snaps. Firefox comes from
    Mozilla, not as a snap.

### Finish

15. **Installing system:** wait until it says the install is complete, then choose
    **Reboot now**. Take out the USB stick when it asks.

The laptop starts into a text login prompt. Log in with the username and password from
step 11, then follow [INSTALL.md](INSTALL.md) from "Get the clone".

## After the install

### Keyboard layout on the desktop

labwc does not read the console's keyboard setting. If you do not use the US layout,
add a line with your layout code to `~/.config/labwc/environment` (make the file if
it is not there). For example, for a French layout:

```
XKB_DEFAULT_LAYOUT=fr
```

Log out and in again for it to take effect.

### What to keep and what to remove

This part is **optional**. Everything works without it.

A standard Server install includes services meant for servers, data centres and
cloud machines. Some of them run all the time, and a laptop has no use for them.
Do this after limDE is installed and working: that is the order it was tested in.

What limDE already changes on its own:

- The network: netplan hands every interface to NetworkManager, and
  `systemd-networkd`, its wait-online service and `networkd-dispatcher` are turned off
  ([INSTALL.md](INSTALL.md#the-network-switch)).
- `smartd` (disk checks every 30 minutes) is turned off when the `laptop` group
  installs it.

Each item below was tested on an installed limDE in a VM: after the change and a
restart the desktop came up, the network was connected, `systemctl --failed` listed
nothing, and `./install` said "No changes". Each undo was tested too: after it and a
restart, the desktop and the network came up with nothing failed.

Most of these are switched off rather than removed. Ubuntu's `ubuntu-server` package
group depends on them, and removing one would remove that group too, so a later
`sudo apt autoremove` could take more with it. Switching off avoids that and is easy
to undo.

#### Safe to switch off on a laptop

**cloud-init** sets up cloud machines on their first start. On a laptop it has nothing
to do after the install.

```
sudo touch /etc/cloud/cloud-init.disabled
```

Undo:

```
sudo rm /etc/cloud/cloud-init.disabled
```

**multipathd** manages disks reached over several cables in a data centre.

```
sudo systemctl disable --now multipathd
```

Undo:

```
sudo systemctl enable --now multipathd
```

**ModemManager** runs mobile-broadband modems (a SIM card in the laptop). Keep it if
your laptop has one.

```
sudo systemctl disable --now ModemManager
```

Undo:

```
sudo systemctl enable --now ModemManager
```

**open-iscsi** connects to network disks (iSCSI).

```
sudo systemctl disable --now open-iscsi iscsid.socket
```

Undo:

```
sudo systemctl enable --now open-iscsi iscsid.socket
```

**lxd-installer** waits to install LXD, a container manager, the first time you run
`lxc`.

```
sudo systemctl disable --now lxd-installer.socket
```

Undo:

```
sudo systemctl enable --now lxd-installer.socket
```

**sysstat** records system statistics every 10 minutes, for server reports. Tinybar
keeps its own battery history.

```
sudo systemctl disable --now sysstat
```

Undo:

```
sudo systemctl enable --now sysstat
```

#### Safe to remove

**snapd** runs snap packages. Even with no snaps chosen, Ubuntu's installer puts in
snapd with two snaps: `core24` and `hwctl` (a hardware-certification tool). limDE
uses no snaps. Remove it only if you will not install snaps yourself. This removes
every snap and its data.

```
sudo apt purge snapd
```

This also removes the `ubuntu-server-minimal` package group, which only lists
packages. Undo:

```
sudo apt install snapd ubuntu-server-minimal
```

Some Ubuntu packages, Firefox's among them, are only a wrapper that installs a snap.
limDE's Firefox comes from Mozilla and does not need snapd.

**kdump-tools** saves a copy of memory when the kernel crashes, for a developer to
study. To be ready, it keeps a block of memory aside at all times: the kernel line
reserves 512 MB on a machine with 4 to 32 GB. In the 3 GB test VM, removing it gave
the system 320 MB more memory.

```
sudo apt purge kdump-tools
```

```
sudo update-grub
```

Restart for the memory to come back. Undo (also takes effect after a restart):

```
sudo apt install kdump-tools
```

```
sudo update-grub
```

#### Keep these

- **unattended-upgrades:** installs Ubuntu's security updates by itself
  ([UPDATE.md](UPDATE.md#ubuntus-packages)).
- **AppArmor:** limDE's Firefox profile depends on it.
- **NetworkManager, wpa_supplicant, systemd-resolved:** the network, Wi-Fi and name
  lookups.
- **udisks2:** PCManFM mounts USB sticks through it.
- **polkit, rtkit:** let the panel change the network and power, and keep sound
  smooth.
- **chrony:** keeps the clock right.
- **thermald:** keeps Intel processors from overheating.
- **fwupd:** firmware updates (`fwupdmgr get-updates`); it only checks now and then.
- **OpenSSH server**, if you ticked it: it waits for a connection and does nothing
  until then.

To see what runs on your system:

```
systemctl list-units --type=service --state=running
```

For battery life, see [BATTERY.md](BATTERY.md).
