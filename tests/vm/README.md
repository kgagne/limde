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

The base image is for testing only: user `tester` (password `tester`, key login only
over SSH), passwordless sudo and autologin on tty1. elachisto never sets these up.

Observed on the first build (2026-10-24):
- A fresh Server VM does not include NetworkManager; `systemd-networkd` manages the NIC.
- Ubuntu's labwc 0.9.3 runs on `virtio-vga` with software rendering (`kms_swrast`).
  The EGL device-query errors in its log are expected without GPU acceleration.
- The CD-ROM I/O errors during the installer's power-off are harmless: the media is
  ejected after the install has finished.
