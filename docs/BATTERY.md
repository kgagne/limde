# Battery life

limDE is made for laptops first. This page says what it already does for the battery,
how to see what uses power, and what you can change yourself. It makes no promise of
hours: that depends on your laptop.

## What limDE already does

- **Starts little.** No display manager, no extra services, and apt installs no
  recommended packages, so only what is listed and what those packages strictly need
  ([DEPENDENCIES.md](DEPENDENCIES.md)).
- **Hides windows when you are away.** After 90 seconds without input, on battery,
  Tinybar minimises every window, which stops apps drawing while nobody is looking. The
  next touch of the keyboard, mouse or touchpad brings them back. Settings:
  `idle_hide`, `idle_hide_battery_only` and `idle_hide_keep`
  ([CUSTOMIZE.md](CUSTOMIZE.md#the-panel)).
- **Locks, then sleeps.** After 5 idle minutes the screen locks. After 8, a laptop on
  battery suspends; on mains power only the screen turns off. These times are in
  `20-idle.sh` ([CUSTOMIZE.md](CUSTOMIZE.md#session-start)).
- **Turns off what it installs but does not need.** The optional `laptop` group adds
  `brightnessctl` (the brightness keys and slider), `powertop` and `smartmontools`.
  powertop's service that changes power settings at every start stays off, as Ubuntu
  ships it. smartmontools' `smartd`, which checks the disks every 30 minutes, is turned
  off by the installer.
- **Keeps its own numbers light.** Tinybar reads the battery every 5 seconds and writes
  its history to disk once every 5 minutes.

On a fresh Ubuntu Server install there are also server services you can switch off.
See [What to keep and what to remove](SERVER-INSTALL.md#what-to-keep-and-what-to-remove).

## See what uses power

**Tinybar.** The panel shows the time left. The battery icon changes colour as the
draw climbs, so a jump is easy to notice. Hover over it for the level and time left.
Click it for the battery's state, the live draw in watts, CPU and memory use, and a
graph of the draw over the last 3 hours, 24 hours or 7 days. Gaps in the graph are time on mains power. Tinybar keeps 90 days of
this history in `~/.local/state/tinybar/history.sqlite`.

Use it to compare: note the draw with the laptop idle, then open an app and watch the
number change.

**powertop** (with the `laptop` group). Run it on battery:

```
sudo powertop
```

The first page lists what wakes the processor most and an estimate of each item's
power use. Tab moves between pages. Press `q` to quit. Its numbers settle after a minute
or so on battery.

## Optional: powertop's auto-tune

powertop's "Tunables" page lists power-saving settings marked "Bad" (off) or "Good"
(on). `--auto-tune` turns all of them on, until the next restart:

```
sudo powertop --auto-tune
```

Ubuntu's powertop package warns that some devices stop working with these settings;
some USB devices, for example, do not handle being put to sleep. Try it first for a
while without making it permanent. If a mouse, keyboard or other device starts to
lag or stop, restart the laptop and everything is back as before.

To run it at every start, turn on powertop's own service:

```
sudo systemctl enable powertop
```

Undo:

```
sudo systemctl disable powertop
```

## Charge limit

Some laptops can stop charging below 100 %, which is easier on the battery when the
laptop is mostly plugged in. limDE does not set the limit. You set it in the laptop's
firmware (the setup screen at start) or with the maker's tools. To see if the battery
reports a limit:

```
cat /sys/class/power_supply/BAT*/charge_control_end_threshold
```

No such file means the battery driver has no limit to show. When there is one below
100, Tinybar's battery popover and tooltip say what it does: "Held at 80%" while
plugged in at the limit, "Charging to 80%" while charging.

## Other things that help

- Lower the screen brightness: the brightness keys or the slider in the panel (with the
  `laptop` group).
- Close apps you are not using. The window buttons in the panel show what is open.
- Switch Bluetooth off in its menu when you do not use it (with the `bluetooth` group).
- On laptops with an NVIDIA card, the desktop runs on the built-in graphics; limDE does
  not set up NVIDIA's driver.
