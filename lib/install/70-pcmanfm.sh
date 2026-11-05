# Build PCManFM from its pinned tag with limde's patches (Space preview; Cut, Copy and
# Paste keys that work after picking a place in the side pane; even space around list
# icons; a GTK theme of its own) and install it to /usr/local, where it takes precedence
# over Ubuntu's copy (on Arch, as a local package; pcmanfm_build_arch). Ubuntu's package stays installed for its supporting files and
# dependencies; the patched build's own menu entries are removed so the launcher doesn't
# list PCManFM twice. The program goes to libexec, and /usr/local/bin/pcmanfm is a small
# wrapper that gives it the panel's GTK theme (components/pcmanfm/pcmanfm), so desktop
# entries, the launcher, default apps and keybinds that run "pcmanfm" all get it.

PCMANFM_PREFIX=/usr/local
PCMANFM_BIN=$PCMANFM_PREFIX/libexec/limde/pcmanfm
PCMANFM_STAMP=$PCMANFM_PREFIX/share/limde/pcmanfm.build

step_pcmanfm() {
  heading "PCManFM with Space preview (built from source)"
  pcmanfm_build
  # Older installs put the program itself here; the wrapper replaces it.
  if ! cmp -s "$LIMDE_ROOT/components/pcmanfm/pcmanfm" "$PCMANFM_PREFIX/bin/pcmanfm"; then
    sudo install -m 755 "$LIMDE_ROOT/components/pcmanfm/pcmanfm" "$PCMANFM_PREFIX/bin/pcmanfm"
    changed "installed the pcmanfm command (PCManFM in the panel's theme)"
  fi
}

# Arch: the same build as a local package (components/pcmanfm/arch/PKGBUILD), so pacman
# owns its files. $1: the stamp text, then the patch files in order.
pcmanfm_build_arch() {
  local want=$1 patch names=() sum pkg
  shift
  local work=${XDG_CACHE_HOME:-$HOME/.cache}/limde/build/pcmanfm-arch
  local log=$STATE_DIR/pcmanfm-build.log
  mkdir -p "$STATE_DIR" "$work"; : > "$log"
  cp "$LIMDE_ROOT/components/pcmanfm/arch/PKGBUILD" "$work/"
  for patch in "$@"; do cp "$patch" "$work/"; names+=("${patch##*/}"); done
  sum=$(cat "$@" | sha256sum | cut -c1-8)
  note "building PCManFM $PCMANFM_TAG as a local package (log: $log)"
  (
    cd "$work"
    export LIMDE_PCMANFM_URL=$PCMANFM_URL LIMDE_PCMANFM_COMMIT=$PCMANFM_COMMIT \
      LIMDE_PCMANFM_TAG=$PCMANFM_TAG LIMDE_PCMANFM_PATCHSUM=$sum \
      LIMDE_PCMANFM_PATCHES="${names[*]}" LIMDE_PCMANFM_STAMP_TEXT=$want
    # --nodeps: the build packages are in packages/arch/build.list, installed already.
    makepkg --force --cleanbuild --nodeps --noconfirm
  ) >>"$log" 2>&1 || { tail -n 20 "$log" >&2; die "PCManFM did not build (log: $log)"; }
  pkg=$(find "$work" -maxdepth 1 -name "limde-pcmanfm-$PCMANFM_TAG.p$sum-1-*.pkg.tar*" | head -1)
  [[ -n $pkg ]] || die "makepkg made no package (log: $log)"
  sudo pacman -U --noconfirm "$pkg" >>"$log" 2>&1 || die "PCManFM did not install (log: $log)"
  [[ $(cat "$PCMANFM_STAMP" 2>/dev/null) == "$want" ]] || die "the installed PCManFM package has no build stamp"
  changed "installed PCManFM $PCMANFM_TAG with Space preview (local package limde-pcmanfm)"
}

pcmanfm_build() {
  # shellcheck source=/dev/null
  . "$LIMDE_ROOT/pins/pcmanfm"
  local patches=("$LIMDE_ROOT/components/preview/pcmanfm-space-preview.patch"
                 "$LIMDE_ROOT/components/pcmanfm/pcmanfm-focus-file-shortcuts.patch"
                 "$LIMDE_ROOT/components/pcmanfm/pcmanfm-icon-spacing.patch"
                 "$LIMDE_ROOT/components/pcmanfm/pcmanfm-own-gtk-theme.patch")
  local patch want; want="$PCMANFM_COMMIT $(cat "${patches[@]}" | sha256sum | cut -d' ' -f1)"
  if [[ -x $PCMANFM_BIN && -f $PCMANFM_STAMP && $(cat "$PCMANFM_STAMP") == "$want" ]]; then
    ok "PCManFM $PCMANFM_TAG with Space preview is installed"
    return
  fi

  [[ $DISTRO == arch ]] && { pcmanfm_build_arch "$want" "${patches[@]}"; return; }

  local work=${XDG_CACHE_HOME:-$HOME/.cache}/limde/build/pcmanfm
  local log=$STATE_DIR/pcmanfm-build.log
  mkdir -p "$STATE_DIR"; : > "$log"
  note "downloading PCManFM $PCMANFM_TAG"
  fetch_commit "$PCMANFM_URL" "$PCMANFM_COMMIT" "$work" >>"$log" 2>&1 \
    || die "could not download PCManFM (log: $log)"
  for patch in "${patches[@]}"; do
    git -C "$work" apply "$patch" >>"$log" 2>&1 \
      || die "${patch##*/} does not apply to PCManFM $PCMANFM_TAG (log: $log)"
  done

  note "building (log: $log)"
  (
    cd "$work"
    ./autogen.sh
    ./configure --prefix="$PCMANFM_PREFIX" --bindir="${PCMANFM_BIN%/*}" --with-gtk=3
    make -j"$(nproc)"
  ) >>"$log" 2>&1 || { tail -n 20 "$log" >&2; die "PCManFM did not build (log: $log)"; }
  grep -q preview_cmd "$work/src/pcmanfm" \
    || die "the built PCManFM lacks the Space-preview code; the patch did not take effect"

  sudo make -C "$work" install >>"$log" 2>&1 || die "PCManFM did not install (log: $log)"
  sudo rm -f "$PCMANFM_PREFIX"/share/applications/pcmanfm*.desktop
  echo "$want" | sudo install -D -m 644 /dev/stdin "$PCMANFM_STAMP"
  changed "installed PCManFM $PCMANFM_TAG with Space preview to $PCMANFM_PREFIX"
}
