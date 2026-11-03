# Updating limDE

limDE updates only when you ask it to. Nothing runs `limde-update` on a schedule. Ubuntu's
own packages are a separate matter, covered at the end.

## How limDE knows what is installed

Every `./install` ends by writing an install record to `/usr/local/share/limde/installed`:

- `commit`: the commit the clone had checked out.
- `source`: the clone's path.
- `groups`: the optional groups chosen in that run.
- `modified`: `yes` if the clone had uncommitted changes, otherwise `no`.

`limde-update` reads this record to find your clone and what is installed from it. If the
record is missing, or the clone is no longer at that path, it stops and asks you to run
`./install` from your clone again.

## Releases

Releases are Git tags named `vMAJOR.MINOR.PATCH`, such as `v1.0.0`. Test releases add
`-beta.N` or `-rc.N`, such as `v1.0.0-beta.3` or `v1.0.0-rc.1`. For the same version, the
betas come first, then the release candidates, then the final release.

Test releases are offered only while the installed version is a test release itself, or
is not a release at all (a commit with no release tag). Once you are on a final release,
`limde-update` offers only final releases. `--to` installs any tag or commit you name,
test releases included.

## Check for an update

```
limde-update --check
```

This fetches tags and branches from the clone's `origin`, then shows the installed
version, the newest one available, how many new commits it has, the release notes from
the tag (the first 20 lines), and which parts the install will build or download again:
labwc, Walker and Elephant, PCManFM or Firefox, when their pins changed. It also says
when the package lists changed, which means the install may add Ubuntu packages. It
installs nothing.

## Install an update

```
limde-update
```

It shows the same as `--check`, then asks "Install vX.Y.Z? [Y/n]". On yes it:

1. checks out the release in your clone, detached at that commit (your branches are left
   as they are), and
2. runs `./install --yes` with the optional groups from the install record, so you get the
   same groups as last time.

To skip the question:

```
limde-update --yes
```

Run it as your normal user; `./install` asks for sudo itself.

`limde-update` refuses to check anything out while the clone has uncommitted changes to
tracked files. Commit or stash them first; `git status` in the clone shows them. Files Git
does not track don't count.

Programs that are running keep the old version until they restart. Log out and back in
after an update.

If `./install` stops part way, `limde-update` says so and prints the command to go back to
what you had. The clone stays at the new release, so you can also fix the problem and run
`./install` again from the clone.

### Adding an optional group

`limde-update` passes the recorded groups with `--yes`, so it never asks about other
groups. To add one, run the installer from your clone and name it (or answer its
question):

```
./install --with=bluetooth
```

The record then holds the groups of that run. Log out and back in afterwards: for
example, the sound server loads Bluetooth audio support only when it starts.

## Follow the main branch

```
limde-update --main
```

This offers the newest commit on `origin/main` instead of the newest release. It can
include changes that are not in any release yet. `--main --check` shows what it would
install.

## Install a given version, or go back

```
limde-update --to TAG
```

Put a release tag such as `v1.0.0-beta.3` in place of `TAG`; `git tag` in the clone lists
them. `--to` takes a release tag or a commit, newer or older than what is installed. It is
also how to go back to an earlier release. When the target does not contain everything
that is installed now, it says so before asking.

Going back has limits:

- Ubuntu packages that a newer version added stay installed.
- Firefox stays at whatever version it has updated itself to.
- Your own files are not touched, but settings that only a newer version understands may
  stop working, or make `limde-appearance` refuse an unknown key.
- Releases up to `v1.0.0-beta.3` came before `limde-update` and the install record. Their
  `./install` does not write the record, so after going back to one, the record still
  names the version you left, and `limde-update` reports from that. To leave such a
  release again, check out the version you want in the clone and run `./install` there,
  which writes a new record.

## With Git directly

`limde-update` is a convenience; the clone and `./install` are what matter. In a clone
that follows a branch, this also works:

```
git pull
```

```
./install
```

`./install` changes only what is missing or out of date, including the pinned source
builds, and asks about the optional groups again. After `limde-update`, the clone is
detached at a release, so switch back to the branch first:

```
git switch main
```

## Ubuntu's packages

Every package limDE installs from Ubuntu, including the build packages, is updated by
apt like the rest of the system. Ubuntu Server installs security updates by itself with
unattended-upgrades, and limDE leaves that as it is. For all other updates:

```
sudo apt update
```

```
sudo apt upgrade
```

The parts limDE builds or downloads itself (labwc, PCManFM, Walker and Elephant) change
only when a new limDE version moves their pins. Firefox updates itself.
