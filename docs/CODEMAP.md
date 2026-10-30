# Code map

Where to look before searching: one line per thing you might change, with its files.
`path::Name` is a class, function, constant or section in that file. `scripts/check`
fails if a path or name here stops existing, so update this map in the same commit as
a change that moves, renames or adds something it lists. Keep it under 150 lines.

**Repo vs installed:** `./install` copies everything to `/usr/local` and `/etc/xdg`.
Repo edits do nothing on a machine until a reinstall (and a restart of what changed).
Files in `config/home` are starter copies, put in a home only when missing.

## Tinybar (the panel): `components/tinybar/`
Test: `python3 -m unittest discover -s components/tinybar/tests`. Installed by
`lib/install/78-tinybar.sh::step_tinybar`, started by `config/autostart.d/40-tinybar.sh`.
- **window, layout, clock** — panel window, widget order, clock format, CSS load: `components/tinybar/tinybar.py::TinyBar.do_activate`, `components/tinybar/tinybar.py::TinyBar.update_clock`. Trap: the `components/tinybar/tinybar` launcher preloads gtk4-layer-shell; run `tinybar.py` directly and it won't dock.
- **task list, windows** — buttons per app ID, click to focus or cycle, first app pinned left: `components/tinybar/tinybar.py::TinyBar.render_task_list`, `components/tinybar/tinybar.py::TinyBar.on_task_clicked`, `components/tinybar/tinybar.py::FIRST_APP_ID`. Trap: a button's icon and position are set once, when it is created.
- **window helper** — C helper on wlr-foreign-toplevel: JSON snapshots out, `activate|minimize|unminimize ID` in: `components/tinybar/toplevel-helper.c`, `components/tinybar/tinybar.py::TinyBar.send_toplevel_command`. Rebuild with `components/tinybar/build.sh`.
- **icons** — theme icons by desktop entry or StartupWMClass; status icons picked from indicator text: `components/tinybar/tinybar_icons.py::desktop_entry`, `components/tinybar/tinybar_icons.py::IconLibrary.status_name`. Trap: rewording a `set_text` string ("VOL MUTED") can change its icon.
- **wifi menu** — status, nearby list, join form, Disconnect/Forget, on/off switch: `components/tinybar/tinybar.py::NetworkMenu`, `components/tinybar/tinybar.py::NetworkMenu.on_network_clicked`, `components/tinybar/tinybar.py::NetworkMenu.rebuild`. Trap: the panel takes the keyboard (ON_DEMAND) only while this popover is open.
- **wifi join, NetworkManager** — D-Bus calls with no widgets, security and password helpers: `components/tinybar/tinybar.py::WifiControl`, `components/tinybar/tinybar.py::WifiControl.watch`, `components/tinybar/tinybar.py::wifi_security`. Trap: new networks are added in memory and saved only once connected; a wrong password shows only in the device's state reason (`device_failure`).
- **tailscale** — on/off button, status every 10 s: `components/tinybar/tinybar.py::TailscaleButton`, `components/tinybar/tinybar.py::tailscale_view`. Trap: needs the user set as Tailscale's operator; `up` has no `--timeout` on purpose.
- **volume** — keys run `components/tinybar/tinybar-volume` (wpctl), which writes a state file Tinybar watches: `components/tinybar/tinybar.py::TinyBar.setup_volume_monitor`, `components/tinybar/tinybar.py::TinyBar.update_volume_from_state`. Trap: changes made outside the keys are missed until the next key press.
- **brightness** — `components/tinybar/tinybar-brightness` steps 10 % (1 % below 10 %, never 0); Tinybar watches sysfs: `components/tinybar/tinybar.py::TinyBar.update_brightness`. Trap: brightnessctl comes only with the optional `packages/optional/laptop.list`.
- **level overlay** — the bar shown 1.5 s after a volume or brightness change: `components/tinybar/tinybar.py::LevelOverlay.show_level`.
- **media keys** — volume, brightness, screenshot keys: `config/labwc/rc.xml::keyboard`.
- **battery** — 5 s tick, time left, tooltip, load colour: `components/tinybar/tinybar.py::TinyBar.update_battery`, `components/tinybar/tinybar.py::BATTERY_LOAD_LEVELS`. Trap: the load colours are `load_*` in `components/appearance/appearance.toml` (both palettes).
- **low-battery warning** — notifications at 10 % and 5 % (urgent), once per discharge: `components/tinybar/tinybar.py::battery_warning`, `components/tinybar/tinybar.py::BATTERY_LOW_PERCENT`, `components/tinybar/tinybar.py::TinyBar.send_battery_warning`. Trap: the once-only state is in memory, so a Tinybar restart below 10 % warns again.
- **power graph, history** — 5-minute buckets in `~/.local/state/tinybar/history.jsonl`, 7 days: `components/tinybar/tinybar.py::HistoryStore`, `components/tinybar/tinybar.py::power_series`, `components/tinybar/tinybar.py::PowerGraph`. Trap: `power_w` is recorded only on battery; empty bins mean mains.
- **power menu** — Lock, Suspend, Log out, Restart, Power off at the right end; the last three ask for a second click: `components/tinybar/tinybar.py::SystemMenu`, `components/tinybar/tinybar.py::needs_second_click`, `components/tinybar/tinybar.py::CONFIRM_SECONDS`. Trap: Log out is `labwc --exit`, which needs the `LABWC_PID` labwc gives what it starts.
- **cpu, ram, temperature** — off in the panel (`SHOW_USAGE`), shown in the battery tooltip: `components/tinybar/tinybar.py::TinyBar.update_usage`, `components/tinybar/tinybar.py::usage_lines`.
- **notifications** — bell, Mako over D-Bus every 2 s, per-row dismiss: `components/tinybar/tinybar.py::NotificationCenter`. Trap: Mako's history can't be cleared; dismissed rows are hidden in memory and return after a restart.
- **idle hide** — swayidle runs `components/tinybar/tinybar-idle`, which signals the pid file (USR1 hide, USR2 restore): `components/tinybar/tinybar.py::TinyBar.setup_idle_hide`, `components/tinybar/tinybar.py::idle_hide_order`. Trap: hidden windows are remembered in memory only.
- **settings** — optional `~/.config/tinybar/settings.toml`, read once at start: `components/tinybar/tinybar.py::load_settings`. Trap: broken TOML silently resets every setting.
- **panel style** — `components/appearance/templates/tinybar.css.in` (rendered to `~/.config/tinybar/style.css`; edit the template). Loaded at USER+1 priority so the user's GTK CSS can't restyle the panel.

## Installer: `install`, `lib/install/`
Test: `scripts/check`; `./install --plan` shows the plan without changing anything.
- **steps, order** — `install` sources each `lib/install/*.sh` (NN-name.sh) and calls the `step_*` functions in the list at its end; shared helpers in `lib/install/common.sh::changed`. Trap: order is that call list, not the file numbers. A second run must print "No changes".
- **packages** — `packages/runtime.list`, `packages/build.list`, optional groups in `packages/optional`: `lib/install/30-packages.sh::step_packages`, `lib/install/20-plan.sh::step_plan`. Trap: apt runs without recommends, so list anything only recommended.
- **labwc build** — commits pinned in `pins/labwc::LABWC_COMMIT`; built by `lib/install/60-labwc.sh::step_labwc`. Trap: rebuilds only when the stamp differs; a build must pass a headless `labwc -S true`.
- **other pins** — Walker/Elephant `pins/launcher::LAUNCHER_ASSETS`, PCManFM `pins/pcmanfm::PCMANFM_COMMIT`, `pins/firefox`. Trap: bump the Walker version together with its asset name, URL and sha256.
- **launcher config** — `config/home/.config/walker`, `config/home/.config/elephant`, started by `config/autostart.d/30-elephant.sh` and `config/autostart.d/50-launcher.sh`.
- **network** — switches netplan to NetworkManager and rolls back if it can't connect in 30 s: `lib/install/40-network.sh::step_network`, `lib/install/40-network.sh::nm_connected`.
- **login, tty1** — marked `~/.profile` block that execs labwc: `lib/install/50-session.sh::profile_block`.
- **session config** — `config/labwc` to `/etc/xdg/labwc`, autostart pieces, starter files, hidden apps: `lib/install/85-session-config.sh::step_session_config`, `config/hidden-apps.list`.
- **autostart** — `config/labwc/autostart` runs `config/autostart.d` pieces, then the user's; same name overrides, empty file disables. Trap: pieces are sourced into one shell; background long-running commands with `&`.
- **idle, lock** — 90 s idle hide, 5 min lock, 8 min screen off or suspend: `config/autostart.d/20-idle.sh::limde_lock`, `config/home/.config/swaylock/config`.
- **keys, touchpad, window rules** — `config/labwc/rc.xml::keyboard`, `config/labwc/rc.xml::libinput`, `config/labwc/rc.xml::windowRules`. Trap: a user's touchpad block replaces limDE's whole block. Window corners and title fonts are fixed in rc.xml's `<theme>`, not the appearance settings.
- **default apps** — `config/home/.config/mimeapps.list` (starter file).
- **helper commands** — `lib/install/82-helpers.sh::step_helpers` installs a named list to `/usr/local/bin`. Trap: a new command needs a line here (Tinybar's in `step_tinybar`, listed in three loops).
- **scrub gate** — no personal or machine data in tracked files: `scripts/check`, `scripts/public-patterns`, `scripts/public-allow`, run by `.githooks/pre-commit`.

## Appearance and icons: `components/appearance/`, `components/icons/`
Test: `scripts/check` (icons, both themes, contrast); `python3 components/appearance/check-contrast`.
- **colours** — dark `[colors]` and `[colors_light]` palettes; contrast pairs: `components/appearance/appearance.toml::colors_light`, `components/appearance/check-contrast::PAIRS`. Trap: a new colour key goes in both palettes.
- **dark/light mode** — `components/appearance/appearance.toml::desktop`, `components/appearance/limde-appearance::template_values`, `components/appearance/limde-appearance::icon_theme`. Trap: light mode needs a fresh login and uses the `limde-light` icon theme.
- **render, apply** — `components/appearance/manifest.toml` maps templates to home files; `components/appearance/limde-appearance::render`. Trap: templates use Python `string.Template`: write a literal `$` as `$$`.
- **new setting** — becomes a `${group_key}` template variable; a new group needs a branch in `components/appearance/limde-appearance::template_values`.
- **shapes, fonts, icon sizes** — `components/appearance/appearance.toml::shape`, `components/appearance/appearance.toml::fonts`. Trap: padding lives in the templates; Mako's font and the Tinybar/Walker px font sizes are fixed in their templates.
- **app styles** — `components/appearance/templates/walker.css.in`, `components/appearance/templates/mako.conf.in`, `components/appearance/templates/labwc.themerc.in`, Alt-Tab `components/appearance/templates/labwc-override.in`. Trap: running programs keep old styles (`makoctl reload`, `labwc --reconfigure`).
- **GTK apps** — `components/appearance/templates/gtk3-desktop.css.in` (PCManFM uses this), `components/appearance/templates/gtk4-desktop.css.in`, libadwaita `components/appearance/templates/gtk4-user.css.in`. Trap: `pcmanfm.css.in` renders a theme nothing selects.
- **icon themes** — `components/icons/build_theme.py::main` builds `limde` and `limde-light` from `components/icons/outlined`; installed by `lib/install/75-icons.sh::step_icons`. Trap: `limde-appearance --apply` never rebuilds icons; only `./install` does.
- **draw an icon** — 24-unit stroke SVGs in `components/icons/src`; generators `components/icons/draw_tier1.py`, `components/icons/draw_tier2.py`; rules in `components/icons/README.md`. Trap: re-running a `draw_*.py` overwrites hand edits.
- **aliases** — freedesktop names to drawn icons: `components/icons/aliases.toml`.
- **brand icons** — `components/icons/brands.toml`, `components/icons/brand-colours.toml`, licences `components/icons/brands/NOTICE.md`; drawn ones in `components/icons/draw_brands_apps.py`. Trap: keys must match in both tomls.
- **outlines** — after any `src` or `brands` SVG change run `components/icons/tools/outline.py` (records `components/icons/outlined/SOURCES.json`); `scripts/check` flags stale ones.

## Other components
- **agent-web** — the AI agent window: `components/agent-web/agent-web`, link routing `components/agent-web/agent-web.cfg::openInMain`, `components/agent-web/welcome.html`. Trap: the `.cfg` is copied into Firefox at each start and its first line must stay a comment.
- **firefox** — AppArmor profile `components/firefox/apparmor-profile`; installed by `lib/install/85-firefox.sh::step_firefox`, then updates itself.
- **pcmanfm** — focus patch `components/pcmanfm/pcmanfm-focus-file-shortcuts.patch`; built by `lib/install/70-pcmanfm.sh::step_pcmanfm`.
- **space preview** — `components/preview/limde-preview::classify`; the Space patch is `components/preview/pcmanfm-space-preview.patch`. Trap: needs `preview_cmd` in `config/home/.config/pcmanfm/default/pcmanfm.conf`.
- **screenshots** — `components/screenshot/limde-screenshot`; test fakes the tools through `LIMDE_SCREENSHOT_*` variables.
- **clipboard notice** — `components/clipboard-notify/limde-clipboard-notify::event`. Trap: never read `x-special/gnome-copied-files`; it cancels a cut.
- **super+w, super+q** — `components/shortcuts/app-shortcut.c::native_key`, built by `components/shortcuts/build.sh`.

## VM tests: `tests/vm/` (needs KVM; details in `tests/vm/README.md`)
- **vm tool** — `tests/vm/vm::cmd_base`, `tests/vm/vm::cmd_up`, `tests/vm/vm::cmd_copy`, `tests/vm/vm::cmd_shot`, `tests/vm/vm::cmd_click`. Trap: `copy` is `rsync --delete`; `click` assumes the same `LIMDE_VM_RES` as `up`.
- **install test** — `tests/vm/test-install NAME [--keep]`: two runs ("No changes"), reboot, session checks.
- **release check** — `tests/vm/test-acceptance` (about 40 min): power cut and Ctrl+C mid-install, first login, baseline, update over user changes.
- **wifi test** — `tests/vm/test-wifi NAME` after `test-install NAME --keep`: simulated radios, two hostapd networks, `tests/vm/wifi-check`. Trap: it tests the installed Tinybar, not the repo copy.
- **session-only actions** — polkit refuses NetworkManager control over SSH, so tests type into foot through QMP: `tests/vm/test-wifi::type_text`, `tests/vm/test-acceptance::key`. Trap: only `tests/vm/vm` honours `LIMDE_VM_DIR`.
