# Tinybar

limDE's panel: open windows (with the agent-web window always leftmost), Wi-Fi,
Bluetooth, volume, brightness, battery, a power menu, notifications and the clock
(with a calendar).
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
- Sign-in pages (hotel, airport and café Wi-Fi): when NetworkManager reports that a
  captive portal is in the way, the Wi-Fi menu says "Sign-in needed" and offers "Sign
  in to the network", which opens the page in the default browser; the icon's tooltip
  says so too, and one notification is sent per network (a middle click on it, Mako's default action, opens the page).
  The page opened is NetworkManager's own check address over plain http, which the
  portal redirects to its sign-in page. This needs NetworkManager's connectivity check,
  which limDE turns on with `network-manager-config-connectivity-ubuntu`
  ([docs/DEPENDENCIES.md](../../docs/DEPENDENCIES.md)); with the check off, nothing about
  sign-in is ever shown.
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
  shown. Closing the menu leaves a pairing or connection running; its result shows
  in the panel icon, never under another device's row, and a new action can start at
  once. "Pair new device" folds away a device's open buttons.
- Volume: click the speaker for a mute toggle, a slider (up to 100 %, like the keys)
  and the list of outputs; click an output to make it the default. Below them, when
  PipeWire has a microphone, the same for the default microphone: mute, level, and with
  more than one, the list to pick from (monitors of outputs are left out). When the
  default source is no microphone (WirePlumber's choice can be an output's monitor),
  only the list shows, to pick one; the mic-mute key then does nothing. The panel
  icon is the speaker's alone; hover it for the microphone's level or "Microphone:
  muted" on a second line. The mic-mute key (`XF86AudioMicMute`, `tinybar-volume
  mic-mute`) toggles the default microphone and shows the overlay with a microphone.
  Only the keys show the level overlay. Changes made elsewhere, such as another app or a
  new default output, show at once: Tinybar follows PipeWire through `pw-dump --monitor`.
- Brightness (on a screen with a backlight): click the sun for a slider, for keyboards
  without brightness keys. It changes the backlight as the keys do (`tinybar-brightness
  set`), never below 1 %, and shows no level overlay: the slider shows the level, and
  only the keys bring up the overlay. Changing it needs `brightnessctl` (the optional
  `laptop` install group, like the keys); without it the slider is greyed out and says so.
  `TINYBAR_BACKLIGHT_DIR` and `TINYBAR_BRIGHTNESSCTL` point Tinybar and
  `tinybar-brightness` at a stand-in backlight, for tests.
- Clock: click it for this month's calendar, opened on today, which is outlined (and
  highlighted until another day is clicked). The arrows browse months and years; Today
  comes back. Dates only: no events.
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
- Windows: one button per app. Click it to raise the app's window; click the focused
  app's button to minimise its window, or, when the app has several, to raise the next
  one (a click never minimises one of several). Right-click for Close, which asks
  every window of the app to close, as its own close button would. Long names end in
  "…" (hover for the whole name); with many apps open they shorten further, so the
  list stops short of the clock instead of pushing it and the icons aside. Each app's
  desktop entry is found by its app ID, or, as Labwc's window switcher does, by the
  entry's `StartupWMClass` (FreeRDP's SDL client, for one).
- Battery: the panel shows the time left; hover for the percentage and time left in
  words, the live draw, a 3-hour average, and CPU and memory use (sampled with the
  battery every 5 seconds, not recorded). Click it for a list of the battery's state
  (on battery, charging, plugged in), the draw on battery or the charge rate while
  charging, the time left or to full, and the charge limit; under it a graph of the
  draw over the last 3 hours, 24 hours or 7 days (arrows or Left/Right cycle through
  them). Gaps are time on mains power. The data is the history Tinybar keeps in the
  SQLite database `~/.local/state/tinybar/history.sqlite` for 30 days: table `buckets`
  has 5-minute summaries (count, average, minimum, maximum) per metric, table `samples`
  the raw readings behind them for metrics read every 5 seconds or slower (battery draw
  and temperature). It is written once per 5 minutes; a `history.jsonl` from older
  versions is imported once and kept as `history.jsonl.imported`. Python's `sqlite3`
  module or any SQLite tool reads it.
- Charge limit: when the battery driver has `charge_control_end_threshold` below 100,
  the popover and the tooltip say what it does: "Held at 80%" while plugged in at the
  limit, "Charging to 80%" (and the time to reach it) while charging, "Not charging
  until below 50%" between the start and end thresholds, else "Charge limit 80%". It
  is read only; set it in the firmware or with your laptop's tools.
  `TINYBAR_BATTERY_DIR` points Tinybar at a stand-in battery folder, for tests and VMs.
- Low battery: on battery, a notification at 10 % and an urgent one at 5 %, which stays
  until dismissed. Each comes once per discharge, and again only after the battery has
  charged more than 3 points above it, so a charger that keeps dropping out cannot repeat it; a
  new warning replaces the one on screen.
- Notifications: the bell shows how many Mako holds; click it to read them and dismiss
  one or all. Its "Do not disturb" switch hides pop-ups (Mako's `do-not-disturb` mode)
  while notifications still arrive and are listed; urgent ones, like the 5 % battery
  warning, still show. The bell is crossed out while it is on. The mode lives in Mako,
  so a Tinybar restart keeps it and a new login starts with it off.
- System menu: the cog at the right end has Appearance (light or dark) and Power: Lock
  and Restart, with Suspend, Log out and Power off under More. Log out, Restart and
  Power off turn red and ask for a second click
  within 4 seconds (a double-click does not count as both); Suspend locks the screen
  first (swayidle's `before-sleep`), and Log out ends labwc (`labwc --exit`), back to
  the tty1 login.
- Tooltips: hover any icon for its state in plain words ("Wi-Fi: Home, 61% signal",
  "Wired: connected", "Volume: muted", "Brightness 40%", "3 notifications"); a window's
  button shows the app's name and the window's title, or how many windows it has. The
  wording rules are in `docs/UI-RULES.md`.
- Style: `~/.config/tinybar/style.css`, generated by the theme.
- Tests: `python3 -m unittest discover -s components/tinybar/tests`.
