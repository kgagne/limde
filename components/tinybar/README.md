# Tinybar

limDE's panel: open windows (with the agent-web window always leftmost), Wi-Fi,
Bluetooth, volume, brightness, battery, a power menu, notifications and the clock.
Python with GTK 4 and gtk4-layer-shell, plus a small C helper (`toplevel-helper`) that
lists windows through the wlr foreign-toplevel protocol.

- Icons come from the icon theme (limDE's), as SVG; no icon fonts.
- Settings: `~/.config/tinybar/settings.toml`, optional. `first_app_id` picks the app
  that always sits leftmost (default `limde.AgentWeb`). `tailscale` controls the
  Tailscale button: `"auto"` (default) shows it when the `tailscale` command is
  installed, `false` hides it, `true` shows it even when it is missing.
  `bluetooth` works the same way for the Bluetooth menu: `"auto"` shows it while BlueZ
  runs with an adapter.
- Wi-Fi: click the icon for the current and nearby networks. Click a network to join
  it: a saved or open one connects at once, one with a password opens a field under its
  row (a wrong password is said so, and never saved). Disconnect and Forget act on the
  current network; the switch turns Wi-Fi off. Hidden networks and work (802.1X)
  logins go through "Other network…", which opens `nmtui` in foot. Saved passwords are
  kept the way NetworkManager keeps them by default: readable only by root, with the
  connection. NetworkManager's calls are in `WifiControl`; `tests/vm/test-wifi` runs
  them against simulated access points in a VM.
- Bluetooth (with the optional `bluetooth` install group): click the Bluetooth icon
  for paired devices, connected ones first; click one for Connect or Disconnect and
  Forget. "Pair new device" searches while the menu stays open and lists nearby devices
  by name; click one to pair, trust and connect it. When the device shows a number,
  the menu asks "Does <device> show 123456?" under its row; for a keyboard it shows the
  number to type on it. Devices that want a PIN typed on the computer are refused and
  go through "Other device…", which opens `bluetoothctl` in foot. The switch powers the
  adapter. Tinybar is BlueZ's pairing agent and follows BlueZ's D-Bus signals, so
  nothing polls; the calls are in `BluetoothControl`, and `tests/vm/test-bluetooth`
  runs them against BlueZ's virtual controllers in a VM. Only the first adapter is
  shown.
- Volume: click the speaker for a mute toggle, a slider (up to 100 %, like the keys)
  and the list of outputs; click an output to make it the default. Only the volume keys
  show the level overlay. Changes made elsewhere, such as another app or a new default
  output, show at once: Tinybar follows PipeWire through `pw-dump --monitor`.
- Tailscale (optional, not installed by limDE): a button left of Wi-Fi turns Tailscale
  on and off with `tailscale up` and `tailscale down`. Tailscale's logo means connected;
  all nine dots greyed with a slash means off or not ready (Tailscale's own tray greys
  the dots); the tooltip says which, and why a click failed. Your user must be Tailscale's operator, set once with
  `sudo tailscale set --operator=$USER`. The state is read every 10 seconds; a click
  that has not connected after 15 seconds stops waiting and Tailscale keeps trying.
  The icons and their licensing are in `components/icons/brands/NOTICE.md`.
- Idle hide: after 90 seconds without input (on battery, by default) every window is
  minimised, which stops apps drawing while nobody is looking; the next touch of the
  keyboard, mouse or touchpad brings them back in their stacking order and gives focus
  back to the window that had it. Only the windows it hid come back. `swayidle`
  (`config/autostart.d/20-idle.sh`) runs `tinybar-idle hide` and `tinybar-idle restore`;
  settings in `settings.toml`: `idle_hide` (default `true`), `idle_hide_battery_only`
  (`true`), and `idle_hide_keep`, app IDs never hidden, for windows you watch without
  touching anything, e.g. `["com.freerdp.client.sdl3"]` for a remote desktop.
  If Tinybar restarts while windows are hidden, it forgets them; bring them back from
  the panel.
- Windows: each one's desktop entry is found by its app ID, or, as Labwc's window
  switcher does, by the entry's `StartupWMClass` (FreeRDP's SDL client, for one).
- Battery: the panel shows the time left; hover for the percentage and time left in
  words, the live draw, a 3-hour average, and CPU and memory use (sampled with the
  battery every 5 seconds, not recorded). Click it for a graph of the draw over the
  last 3 hours, 24 hours or 7 days (arrows or Left/Right cycle through them). The data
  is the history Tinybar keeps in `~/.local/state/tinybar/history.jsonl`: 5-minute
  summaries while on battery, kept for 7 days. Gaps are time on mains power.
- Low battery: on battery, a notification at 10 % and an urgent one at 5 %, which stays
  until dismissed. Each comes once per discharge, and again only after the battery has
  charged more than 3 points above it, so a charger that keeps dropping out cannot repeat it; a
  new warning replaces the one on screen.
- Power menu: the power icon at the right end offers Lock, Suspend, Log out, Restart
  and Power off. Log out, Restart and Power off turn red and ask for a second click
  within 4 seconds (a double-click does not count as both); Suspend locks the screen
  first (swayidle's `before-sleep`), and Log out ends labwc (`labwc --exit`), back to
  the tty1 login.
- Tooltips: hover any icon for its state in plain words ("Wi-Fi: Home, 61% signal",
  "Wired: connected", "Volume: muted", "Brightness 40%", "3 notifications"); a window's
  button shows the app's name and the window's title, or how many windows it has. The
  wording rules are in `docs/UI-RULES.md`.
- Style: `~/.config/tinybar/style.css`, generated by the theme.
- Tests: `python3 -m unittest discover -s components/tinybar/tests`.
