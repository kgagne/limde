# VM test harness

Headless QEMU VMs for testing the installer on a clean Ubuntu Server 26.04.1. It needs
KVM access and `qemu-system-x86 qemu-utils ovmf`, and never needs root. Run
`tests/vm/vm` with no arguments for the commands.

- `vm base` downloads the Server ISO (checked against Ubuntu's sha256) and installs it
  unattended into `local/vm/base.qcow2`: about 4 minutes. It reads the installer kernel
  straight from the ISO (`iso-extract.py`) and serves the autoinstall answers
  (`autoinstall.yaml`) over HTTP on the host's loopback interface.
- `vm up NAME` boots a copy-on-write overlay of the base image, so every test starts
  clean. SSH is forwarded to a free loopback port.
- `vm shot NAME FILE.png` captures the guest screen through QMP (`qmp.py`). It works
  for the text console and for labwc.
- `vm click NAME X Y` clicks at a screen position through a virtual tablet, for
  pressing panel buttons; keys go through QMP `send-key`.

- `vm view NAME` opens the VM's screen in a window through QEMU's built-in VNC server,
  which listens on the loopback interface only (`127.0.0.1`, display 10 and up). Nothing
  is installed in the guest. The viewer is `gvncviewer` on the host.
- `vm du` shows the space used. `vm clean` deletes every VM and the base image but keeps
  the ISO; `vm clean --all` also deletes the ISO. Everything needed to rebuild (ISO URL and
  checksum, install answers, scripts) is in this folder, so `vm base` brings it all back
  in about 10 minutes.

The base image is for testing only: user `tester` (password `tester`, key login only
over SSH), passwordless sudo and autologin on tty1. limDE never sets these up.

Observed on the first build (2026-10-24):
- A fresh Server VM does not include NetworkManager; `systemd-networkd` manages the NIC.
- Ubuntu's labwc 0.9.3 runs on `virtio-vga` with software rendering (`kms_swrast`).
  The EGL device-query errors in its log are expected without GPU acceleration.
- The CD-ROM I/O errors during the installer's power-off are harmless: the media is
  ejected after the install has finished.

## Fast iteration: the installed image

A full install takes about 20 minutes, almost all of it apt and the labwc build, so
day-to-day work runs against a saved installed image instead:
- `test-install NAME --save` saves the VM as `local/vm/installed.qcow2` when every check
  passed (`vm save NAME` does it by hand; `vm list` shows what it holds). A save shuts
  the VM down first and refuses one that had to be forced off after 150 s, since its disk
  may miss writes. The image it writes holds the whole disk on top of the base image,
  also for a VM that was itself started with `--installed`.
- `vm up NAME --installed` starts a VM from it in about 10 seconds, with the session up
  about 30 seconds later.
- `vm sync NAME` copies the working tree in, runs `./install` (only what changed, about
  50 seconds) and reboots so the session restarts with it (about a minute); then
  `vm click` and `vm shot` for screenshots. `--no-restart` skips the reboot. When
  `./install` fails, `sync` shows its last lines and exits non-zero without rebooting;
  the full output is in `local/vm/NAME/sync.log`.

Run the full `test-install` (and `test-acceptance` for a release) as a separate pass:
before every push, and whenever the install flow itself changes (`install`,
`lib/install/`, `packages/`, `pins/`). Save its VM with `--save` so the bench starts from
the newest good install.

## Logging out

`test-logout NAME` runs on an installed VM (`vm up NAME --installed` is enough). It does what the
panel's Log out does, waits for the image's autologin to start the next session, and checks that
that session has its own Elephant, which answers a query.

## Wi-Fi

`test-wifi NAME` runs in a VM where limDE is installed (`test-install NAME --keep`). The
VM has no Wi-Fi hardware, so it loads the kernel's simulated radios (`mac80211_hwsim`),
installs `hostapd` (for the test only, after an `apt-get update`) and runs two access
points, `limde-psk` (WPA2) and `limde-open`. Before and after the check it deletes any
saved test networks and turns Wi-Fi on, so a run that stopped part way does not spoil
the next one. `wifi-check` then drives Tinybar's `WifiControl`, the same calls the
Wi-Fi menu makes: a wrong password fails as such and is never written to disk; the
right one connects and is saved; disconnect; a saved network reconnects; forget; an
open network; Wi-Fi off and on.

## Bluetooth

`test-bluetooth NAME` runs in a VM where limDE is installed (the installed image is
enough). The VM has no Bluetooth hardware, so it installs the optional `bluetooth` group
and, for the test only, `bluez-test-tools`, whose emulator `btvirt -l2` (with the kernel's
`hci_vhci`) makes two virtual controllers that see each other: the first is the
computer's adapter, the second plays a device. `bluetooth-check` then drives Tinybar's
`BluetoothControl`: on and off, the search lists the device by name, pairing asks to
compare a number and connects, disconnect, reconnect, forget. (PipeWire then lists the
device, but no sound output for it.)
BlueZ lets any local user call it, so unlike Wi-Fi this runs over SSH. `--keep` leaves
the controllers up with `bluetooth-check --device` answering the device's side of
pairing, for trying the menu by hand; start it after any Tinybar restart, because BlueZ
sends the device side's question to the newest default agent. The agent's refusals
(typed PINs) are tested on a private bus in `components/tinybar/tests`.

## Release acceptance

`test-install NAME` checks a clean install, a second run and a reboot. `test-acceptance
NAME` covers the rest of a release check, in one fresh VM (about 40 minutes):
- the power is cut while apt is unpacking, then Ctrl+C lands during the labwc build;
  each next run must finish, and the run after must report "No changes"
- the first login starts the whole session with no failed units or errors in its logs
- an idle-session resource baseline (`local/vm/results/NAME/baseline.txt`)
- an update installed over personal changes (appearance, labwc keys, autostart pieces,
  starting files, `~/.profile`, agent-web's page) leaves every one byte for byte
  unchanged and in effect after a reboot

Baseline from the first passing run (2026-10-25; 4 vCPUs, 3.4 GiB RAM, software
rendering, agent-web on its welcome page): 0.44% CPU busy at idle, 953 MiB memory in
use (the session's processes 811 MiB PSS, most of it agent-web's Firefox), 178
processes, 5.6 s boot, 8.9 GB on disk with 1181 packages (`/usr/local` 140 MB, Firefox
326 MB). A laptop's numbers differ; this is for spotting regressions between runs.
