# Trying limDE in a VM

You can try limDE in a virtual machine before you install it on hardware. Read this first:
the repository has no VM setup made for users. What it has is a test harness for
developers, in `tests/vm/`. It works for a trial too, and this page shows how, but it was
written for testing the installer, and it shows.

## What the harness is

`tests/vm/vm` runs headless QEMU VMs with KVM. `tests/vm/README.md` describes it in full.
The parts that matter for a trial:

- `vm base` downloads the Ubuntu Server 26.04.1 ISO, checks it against Ubuntu's sha256,
  and installs it unattended into a base image (about 4 minutes once the ISO is there).
- `test-install NAME` starts a fresh VM from that base image, copies your clone into it,
  runs `./install --yes` twice, reboots, and runs its checks.
- `vm view NAME` opens the VM's screen in a window, through a VNC server that listens
  only on your own machine (`127.0.0.1`).

The base image is for testing only, and it is not what a real install looks like:

- It has a user `tester` with the password `tester`, passwordless sudo, and autologin on
  tty1. limDE never sets up any of these on a real machine.
- The VM has software rendering (QEMU's `virtio-vga`), no backlight, no battery, no
  Wi-Fi and no Bluetooth hardware. Graphics are slower than on hardware, and the battery,
  brightness, Wi-Fi and Bluetooth parts of the panel have nothing to show.
- `test-install` also runs a `limde-update` check against a throwaway local release tag,
  then puts the clone's origin back.

## What you need on your own machine

- Linux on x86_64 with KVM access (`/dev/kvm` usable by your user). No root is needed to
  run the VMs.
- The packages `qemu-system-x86`, `qemu-utils` and `ovmf`, plus `curl`, `openssl`, `ssh`
  and `python3`. On Ubuntu or Debian:

  ```
  sudo apt install qemu-system-x86 qemu-utils ovmf
  ```

- `gvncviewer` to see the screen:

  ```
  sudo apt install --no-install-recommends gvncviewer
  ```

- Free disk for the ISO, the base image and each VM's disk. A VM's disk can grow to
  20 GB; `tests/vm/vm du` shows what they use. The files live in `local/vm/` inside your
  clone. A VM gets 4 GiB of memory and 4 CPUs by default.

## Try it

From your clone of limDE:

```
tests/vm/vm base
```

```
tests/vm/test-install trial --keep
```

`test-install` takes about 20 minutes. It installs whatever your clone has checked out,
including uncommitted changes. At the end it prints how many checks passed, and keeps the
VM running because of `--keep`. Its logs and a screenshot are in
`local/vm/results/trial/`.

The VM logs in on tty1 by itself, so the desktop is already up. Open its screen:

```
tests/vm/vm view trial
```

You can use the desktop in that window with your keyboard and mouse.

For a bigger screen, set `LIMDE_VM_RES` when the VM starts. `test-install` starts its own
VM, so set it for that command:

```
LIMDE_VM_RES=1920x1200 tests/vm/test-install trial --keep
```

`LIMDE_VM_MEM` (in MiB) and `LIMDE_VM_CPUS` change the memory and CPU count the same way.

To try the optional groups, pass installer options after `--`:

```
tests/vm/test-install trial --keep -- --with=papers
```

## A shell in the VM

```
tests/vm/vm ssh trial
```

This logs in as `tester` over SSH. The clone is in `~/limde`. An SSH login is outside the
desktop session, so the system refuses NetworkManager changes, such as joining a Wi-Fi
network, made from it; do those from the desktop.

## Stopping and cleaning up

```
tests/vm/vm down trial
```

```
tests/vm/vm rm trial
```

`vm rm` deletes the VM's disk. `vm list` shows the VMs and whether they run, and `vm du`
shows the space they use. To delete every VM and the base image but keep the ISO:

```
tests/vm/vm clean
```

`vm clean --all` deletes the ISO too.

## Other VM software

The repository does not set up or test any other route: not virt-manager, GNOME Boxes,
VirtualBox or a hand-written QEMU command. If you already use one of these, you can make
a VM with Ubuntu Server 26.04 (x86_64) in it and follow [INSTALL.md](INSTALL.md) as on
hardware. Whether limDE's desktop starts with that software's virtual graphics is
untested. The harness's VMs use UEFI firmware and `virtio-vga`.
