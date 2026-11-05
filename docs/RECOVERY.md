# Recovery

What to do when something goes wrong, using only what limDE itself provides. There is
no uninstaller yet.

## The desktop does not start

limDE starts labwc from a block in your `~/.profile`, only on the first console (tty1),
with `exec`. If labwc fails to start or exits, your login on tty1 ends and you see the
login prompt again. Logging in again on tty1 tries again.

To get a shell instead, switch to another console with Ctrl+Alt+F2 (or F3 to F6) and log
in there. The block runs only on tty1, so on any other console you get a normal shell.

### Read the logs

The session's logs are in `~/.local/state/limde/`:

- `labwc.log`: labwc's output. It is replaced at each login on tty1, so read it before
  you try again.
- `tinybar.log`: the panel.
- `walker.log`: the launcher.
- `elephant.log`: the launcher's data service.
- `clipboard-notify.log`: the notice for cut and copied files.
- `agent-web.log`: the agent window: its home page, and the links it sent to Firefox.

For example:

```
less ~/.local/state/limde/labwc.log
```

The system journal has the rest, such as graphics driver errors:

```
journalctl -b -p warning
```

To see the previous boot's journal, after a restart:

```
journalctl -b -1 -p warning
```

### Check the installed labwc

The session runs the labwc limDE built, in `/usr/local/bin`. Check that it is there and
which version it is:

```
labwc --version
```

```
cat /usr/local/share/limde/labwc.commit
```

The second command shows the labwc and wlroots commits that were installed. They should
match `pins/labwc` in your clone.

### Move your own files aside

limDE never overwrites your own config files, so a mistake in one of them stays until you
fix it. To rule them out, move them aside one at a time and log in on tty1 again:

- `~/.config/labwc/rc.xml`
- `~/.config/limde/autostart.d/`
- `~/.config/limde/appearance.toml`

For example:

```
mv ~/.config/labwc/rc.xml ~/.config/labwc/rc.xml.off
```

A piece in `~/.config/limde/autostart.d/` that runs a long-lived command without `&` stops
every piece after it.

## Run the installer again

Running `./install` again from your clone is safe. Each step checks first and changes
only what is missing or out of date, so it puts back limDE's defaults, commands and
builds if something removed or changed them. It does not touch your own files.

```
cd ~/limde
```

```
./install
```

Use your clone's path if it is not `~/limde`; `/usr/local/share/limde/installed` names
it on the `source=` line.

If the install itself fails, the installer's logs are in `~/.local/state/limde/` too
(`apt.log`, `labwc-build.log`, `pcmanfm-build.log` and the others; see
[INSTALL.md](INSTALL.md#when-a-step-fails)). Some things to know:

- A package install cut short by a power cut or Ctrl+C is finished at the start of the
  next run.
- A new labwc build is installed only after it starts and stops cleanly in a headless
  test session. If the build or the test fails, the labwc you had stays installed.
- If `./install` stops at the Appearance or Icons step, check
  `~/.local/state/limde/appearance.log` and your `~/.config/limde/appearance.toml`: an
  unknown key or a bad value there stops both.

## Go back to an earlier release

If a new release does not work for you, install the one you had before:

```
limde-update --to TAG
```

Put the release tag in place of `TAG`. When an update's `./install` fails, `limde-update`
prints this command with the commit you had.
[UPDATE.md](UPDATE.md#install-a-given-version-or-go-back) covers what going back does not
undo, and why releases up to `v1.0.0-beta.3` need care.

`limde-update` refuses while the clone has uncommitted changes. Commit or stash them
first.

## Put back an earlier style

`limde-appearance --apply` (also run by `./install` and the light and dark switch) saves
every file it replaces in `~/.local/state/limde/appearance/backups/`, one folder per run,
named by date and time. Inside, the files sit at their paths relative to your home. Copy
one back to put it back. The next `limde-appearance --apply` will render it again from
your settings, so change `~/.config/limde/appearance.toml` too if the cause is there.

## Stop the desktop starting on tty1

The block in `~/.profile` sits between two marker lines:

```
# >>> limde session >>>
# <<< limde session <<<
```

Delete those two lines and everything between them, from another console or over SSH,
and tty1 gives you a normal shell at the next login. The rest of your `~/.profile` is
yours and limDE does not change it.

Before each change to `~/.profile`, the installer saved the previous copy in
`~/.local/state/limde/backups/`, named `profile.` and the date and time. The oldest one is
normally your `~/.profile` from before limDE.

Running `./install` again adds the block back.

## The login keyring lines

The installer adds two lines to `/etc/pam.d/login`, both `optional`, so a keyring problem
never stops you logging in:

```
auth       optional   pam_gnome_keyring.so
session    optional   pam_gnome_keyring.so auto_start
```

Before it changed the file, it saved the previous copy in `~/.local/state/limde/backups/`,
named `pam.d-login.` and the date and time. To take the lines out, delete them with
`sudoedit /etc/pam.d/login`, or copy that saved file back:

```
sudo cp ~/.local/state/limde/backups/pam.d-login.DATE /etc/pam.d/login
```

Running `./install` again adds them back.

The file belongs to Ubuntu's `login` package. If an update changes Ubuntu's own copy, apt
asks whether to keep yours: keep it (`N`, the default) and the lines stay; take the new
one and they are gone until the next `./install`. Automatic security updates skip a
package that would ask this, so when `sudo apt upgrade` shows that question, answer it
there.

If an app asks for the keyring's password even though you logged in with a password, the
keyring's password is no longer your login password (it was set before a password reset
done as root, for example). Give it the old one, or delete
`~/.local/share/keyrings/login.keyring` to start a new keyring at the next login, which
loses the passwords saved in the old one.

## The network

### During the install

The installer hands the network to NetworkManager only if NetworkManager connects, with
working name lookups, within 30 seconds. If it does not, the installer removes its netplan
file (`/etc/netplan/90-limde-networkmanager.yaml`), runs `netplan apply` to put the
previous setup back, and stops with:

"NetworkManager did not connect (with working DNS) within 30 s; the previous network
setup is restored"

Your connection then works as it did before. Running `./install` again tries the switch
again.

### Afterwards

Only once NetworkManager is connected does the installer turn off `systemd-networkd`,
`systemd-networkd.socket`, `systemd-networkd-wait-online.service` and
`networkd-dispatcher.service`. If the connection is lost right after that, the installer
stops with "network lost after turning networkd off" and does not undo the switch by
itself.

To return to Ubuntu Server's own network setup by hand, undo those two changes. This is
the reverse of what the installer does, but it is not something limDE tests:

```
sudo rm /etc/netplan/90-limde-networkmanager.yaml
```

```
sudo systemctl enable --now systemd-networkd.socket systemd-networkd.service
```

```
sudo netplan apply
```

The installer also turned off `systemd-networkd-wait-online.service` and
`networkd-dispatcher.service`; enable them the same way if you want them back.

Tinybar's Wi-Fi menu needs NetworkManager, so it will not work after this, and the next
`./install` switches to NetworkManager again.

## Reporting a problem

Bug reports are welcome. Include your hardware, the output of `journalctl -b -p warning`,
and the logs above that relate to the problem.
