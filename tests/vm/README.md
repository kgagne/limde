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
