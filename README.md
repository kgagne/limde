# elachisto

*elachisto* (ελάχιστο) is Greek for "minimum".

A small Wayland desktop for Ubuntu Server: labwc, a compact panel (Tinybar), the Walker
launcher, a consistent dark theme, Space-bar file preview in PCManFM, and a persistent
window for a web-based AI agent. Install Ubuntu Server 26.04, clone this repository,
run `./install`, and log in.

> **Status: in development, not yet usable.** Nothing here installs a desktop yet. The
> first release candidate will be `v1.0.0-rc.1`.

## Philosophy

- **Minimal, but not dogmatic.** The installer lists every package it wants, with the
  reason for it, before installing anything. Optional pieces are optional, and you choose
  them.
- **Built from source where it matters.** labwc is built from a pinned upstream commit,
  because the newest pointer-acceleration and scrolling work is often not in a release
  or in Ubuntu's package yet. Everything else comes from Ubuntu or from pinned upstream
  releases.
- **Yours to change.** Shipped defaults sit apart from your own changes, so updates
  don't overwrite them.

## How this was made

elachisto grew out of one person's daily-driver laptop setup. It was designed, tested
and directed by its author over many iterations, and much of the implementation, review
and documentation was done with AI coding tools working from that guidance. Without that
tooling, a project of this scope would not have been practical for one person. Every
change was steered and accepted by a human, and tested on real hardware and in VMs.

## Licence

MIT for elachisto's own code (see `LICENSE`). Some files come from or patch other
projects and keep their own licences; `REUSE.toml` lists them.
