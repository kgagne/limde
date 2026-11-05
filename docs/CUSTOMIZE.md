# Customizing limDE

limDE keeps its shipped defaults apart from your own files. You change things by adding
your own files in your home, which limDE reads on top of its defaults. The installer and
`limde-update` replace the defaults but never overwrite your own files.

`docs/CODEMAP.md` is the index of where each part lives in the repository, if you want to
read the code behind a setting.

## Where things live

limDE's defaults, replaced by every `./install` that finds them out of date. Don't edit
these; your changes would be lost at the next install or update:

- `/etc/xdg/labwc/`: labwc's `rc.xml` (keys, touchpad, window rules), `autostart` and
  `environment`.
- `/usr/local/share/limde/autostart.d/`: the pieces the session starts.
- `/usr/local/share/limde/appearance/`: the default `appearance.toml` and the style
  templates.
- `/usr/local/share/limde/tinybar/` and `/usr/local/share/limde/agent-web/`: the panel
  and the agent window.
- `/usr/local/share/icons/limde` and `/usr/local/share/icons/limde-light`: the icon
  themes.
- `/usr/local/share/themes/limde/labwc/`: the shapes of the window title-bar buttons.
- `/usr/local/bin/`: limDE's commands, and labwc, PCManFM, Walker and Elephant.

Your own files, which limDE reads and never overwrites. None of them exist until you make
them:

- `~/.config/labwc/rc.xml`: your labwc settings.
- `~/.config/limde/autostart.d/`: your session pieces.
- `~/.config/limde/appearance.toml`: your colours, fonts, shapes and icon settings.
- `~/.config/tinybar/settings.toml`: the panel's settings.
- `~/.config/limde/agent-web.conf`: the agent window's page (see
  `components/agent-web/README.md`).

Starting files, which the installer puts in your home only when you don't have them yet.
After that they are yours to edit, and the installer leaves them alone (it says how many
it kept; limDE's current versions are in the clone's `config/home/`):

- `~/.config/mimeapps.list`: default apps.
- `~/.config/walker/config.toml`: the launcher.
- `~/.config/elephant/files.toml` and `~/.config/elephant/calc.toml`: the launcher's file
  search and calculator.
- `~/.config/pcmanfm/default/pcmanfm.conf` and `~/.config/libfm/libfm.conf`: the file
  manager.
- `~/.config/swaylock/config`: the lock screen.
- `~/.config/fontconfig/fonts.conf`: Open Sans as the desktop's sans-serif font.

Generated files, which `limde-appearance` writes from the appearance settings. Don't edit
them: they are rewritten whenever the appearance changes, including during `./install`.
Before it replaces one, `limde-appearance` saves the old copy in
`~/.local/state/limde/appearance/backups/`.

- `~/.config/tinybar/style.css`
- `~/.config/walker/themes/limde/style.css`
- `~/.config/mako/config`
- `~/.config/labwc/themerc-override`
- `~/.config/gtk-3.0/settings.ini`, `~/.config/gtk-4.0/settings.ini` and
  `~/.config/gtk-4.0/gtk.css`
- `~/.local/share/themes/limde/labwc/themerc`, `~/.local/share/themes/LimDE/` (GTK) and
  `~/.local/share/themes/LimDE-Panel/`

## labwc settings

labwc starts with `--merge-config`. It reads limDE's `/etc/xdg/labwc/rc.xml` first, then
your `~/.config/labwc/rc.xml` on top. Put only the settings you change in your file.
Every option is described in labwc's manual:

```
man labwc-config
```

After you change your file, tell the running labwc to read it again, from a terminal in
the desktop:

```
labwc --reconfigure
```

### Keys

limDE's keys are in the `<keyboard>` section of `/etc/xdg/labwc/rc.xml`, next to labwc's
own defaults. To add a key, put a `<keybind>` in your own file. This one opens PCManFM
with Super+E:

```xml
<?xml version="1.0"?>
<labwc_config>
  <keyboard>
    <keybind key="W-e"><action name="Execute" command="pcmanfm" /></keybind>
  </keyboard>
</labwc_config>
```

limDE's keys keep working next to yours. The volume, mic-mute and brightness keys
run `tinybar-volume` and `tinybar-brightness`, and the screenshot keys run
`limde-screenshot`; if you rebind those keys, keep those commands so the panel still shows
the change.

### Touchpad

limDE's touchpad settings are one `<device category="touchpad">` block in the
`<libinput>` section of `/etc/xdg/labwc/rc.xml`, with natural scrolling, click by finger
count, and custom motion and scroll curves tuned on one laptop.

A touchpad block in your own file replaces limDE's whole block. It is not merged setting
by setting. So to change one thing, copy the whole block into your
`~/.config/labwc/rc.xml`, inside `<labwc_config><libinput>…</libinput></labwc_config>`,
and edit it there. For libinput's default motion, use
`<accelProfile>adaptive</accelProfile>` and remove the three curve lines
(`motionCurve`, `scrollCurve` and `fallbackCurve`).

### Window rules

limDE's window rules (for the Space preview and PCManFM's copy questions) are in the
`<windowRules>` section. Add your own in the same section of your file; see
`man labwc-config` for the format.

## Session start

labwc runs `/etc/xdg/labwc/autostart` when the session starts. It runs every piece in
`/usr/local/share/limde/autostart.d/`, in name order, then every piece in your
`~/.config/limde/autostart.d/`. limDE's pieces are:

- `10-notifications.sh`: Mako, the notifications.
- `20-idle.sh`: swayidle: the panel's idle hide at 90 seconds, the lock at 5 minutes,
  and at 8 minutes the screen off on mains power or suspend on battery.
- `30-elephant.sh`: Elephant, the launcher's data service.
- `40-tinybar.sh`: Tinybar, the panel.
- `50-launcher.sh`: Walker, kept running so it opens at once.
- `60-agent-web.sh`: the agent window.
- `70-clipboard-notify.sh`: the notice when files are cut or copied.
- `80-pointer.sh`: moves the pointer to the middle of the screen (it presses Alt+Super+H).

Your pieces follow three rules:

- **A new name adds a piece.** It runs after all of limDE's pieces.
- **The same name replaces limDE's piece.** Your file runs instead, in your folder's turn.
- **An empty file with the same name turns that piece off.**

Each name must end in `.sh`. The pieces are sourced into one shell, one after another,
so start anything that keeps running in the background with `&`, or the pieces after it
never run.

For example, to turn off the idle lock and screen-off:

```
mkdir -p ~/.config/limde/autostart.d
```

```
touch ~/.config/limde/autostart.d/20-idle.sh
```

To change the timings instead, copy limDE's piece and edit your copy:

```
cp /usr/local/share/limde/autostart.d/20-idle.sh ~/.config/limde/autostart.d/
```

Changes take effect at your next login.

## Appearance

The colours, fonts, shapes and icon settings for the panel, the launcher, notifications,
PCManFM, GTK apps and labwc's window borders all come from one file of defaults,
`/usr/local/share/limde/appearance/appearance.toml` (`components/appearance/appearance.toml`
in the repository). Read it for every setting and its group.

To change some, create `~/.config/limde/appearance.toml` with only the keys you change,
under the same group names. For example:

```toml
[colors]
focus = "#7fb4ca"

[fonts]
interface = "Open Sans 11"
```

The groups are `[colors]` (the dark mode's colours), `[colors_light]` (the light mode's),
`[shape]`, `[icons]`, `[desktop]` and `[fonts]`. An unknown group or key is an error, and
values are checked: colours as `#rrggbb` or `#rrggbbaa`, fonts as a name and a size.

Then see what would change, as a diff:

```
limde-appearance
```

And write it:

```
limde-appearance --apply
```

`--apply` saves the files it replaces in `~/.local/state/limde/appearance/backups/`, one
folder per run. Programs that are running keep their old style until they reload it.
`limde-appearance --apply` prints what to run for Mako and labwc:

```
makoctl reload
```

```
labwc --reconfigure
```

Reopen other apps, and log out and back in for the panel and the launcher.

The icon themes are built by `./install`, not by `limde-appearance`. If you change icon
settings, run `./install` from your clone afterwards.

The window title-bar buttons (close, minimise, maximise) are 16-pixel rounded squares.
Each is a one-bit mask that labwc fills with the mode's `button_close`,
`button_iconify`, `button_maximize` or, on inactive windows, `button_inactive` colour.
To draw your own shapes, put XBM files with the same names (`close.xbm`, `iconify.xbm`,
`max.xbm`, and `max_toggled.xbm` for a maximised window) in
`~/.local/share/themes/limde/labwc/`. labwc looks there first. Keep them within 22 by 22
pixels, the size of a button: larger ones are scaled down and look blurred.

`scripts/check` holds limDE's own palettes to WCAG 2.2's contrast minimums. It does not
check your file, so keep text at 4.5:1 and icons and control edges at 3:1 against their
backgrounds yourself.

### Light and dark

Both modes are complete themes. To switch, use the cog at the right end of Tinybar:
Appearance has the switch. It runs:

```
limde-appearance --apply --mode light
```

(or `--mode dark`), then reloads labwc and Mako and restarts Walker's service. GTK 4 apps
that are already open may keep their old icons until you reopen them, and foot's
terminal colours stay dark in both modes.

The choice made with `--mode` is kept in `~/.local/state/limde/appearance/mode`, and it
wins over any `mode` in the `[desktop]` group of your `appearance.toml`. To let your file
decide again, delete that file and apply:

```
rm ~/.local/state/limde/appearance/mode
```

```
limde-appearance --apply
```

## The panel

Tinybar reads `~/.config/tinybar/settings.toml` once, when it starts. Every setting is
optional:

- `first_app_id`: the app that always sits leftmost. The default is `"limde.AgentWeb"`,
  the agent window.
- `tailscale`: the Tailscale button. `"auto"` (the default) shows it when the `tailscale`
  command is installed, `false` hides it, `true` shows it even when it is missing.
- `bluetooth`: the Bluetooth menu. `"auto"` (the default) shows it while BlueZ runs with
  an adapter, `false` hides it, `true` shows it even without one.
- `idle_hide`: minimise every window after 90 seconds without input, and bring them back
  at the next input. The default is `true`.
- `idle_hide_battery_only`: idle hide only on battery. The default is `true`.
- `idle_hide_keep`: app IDs never hidden, for windows you watch without touching
  anything, such as a remote desktop.

For example:

```toml
tailscale = false
idle_hide_keep = ["com.freerdp.client.sdl3"]
```

If the file is not valid TOML, Tinybar ignores all of it, without a message, and uses the
defaults. Log out and back in for changes to take effect. `components/tinybar/README.md`
describes the rest of the panel.

## Default apps

The starting `~/.config/mimeapps.list` opens web links and HTML in Firefox, folders in
PCManFM, and PDF, DjVu and TIFF files in Papers (from the optional `papers` group). It is
yours to edit: change the `.desktop` name after a type to change its app. The desktop
entries for installed apps are in `/usr/share/applications`,
`/usr/local/share/applications` and `~/.local/share/applications`.

## The agent window

To use a different page, run `agent-web set-home` with its address; to turn the window
off, add an empty `~/.config/limde/autostart.d/60-agent-web.sh` and run `agent-web stop`.
`components/agent-web/README.md` has the details.
