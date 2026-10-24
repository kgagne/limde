# Build PCManFM from its pinned tag with the Space-preview patch and install it to
# /usr/local, where it takes precedence over Ubuntu's copy. Ubuntu's package stays
# installed for its supporting files and dependencies; the patched build's own menu
# entries are removed so the launcher doesn't list PCManFM twice.

PCMANFM_PREFIX=/usr/local
PCMANFM_STAMP=$PCMANFM_PREFIX/share/elachisto/pcmanfm.build

step_pcmanfm() {
  heading "PCManFM with Space preview (built from source)"
  # shellcheck source=/dev/null
  . "$ELACHISTO_ROOT/pins/pcmanfm"
  local patch=$ELACHISTO_ROOT/components/preview/pcmanfm-space-preview.patch
  local want; want="$PCMANFM_COMMIT $(sha256sum "$patch" | cut -d' ' -f1)"
  if [[ -x $PCMANFM_PREFIX/bin/pcmanfm && -f $PCMANFM_STAMP && $(cat "$PCMANFM_STAMP") == "$want" ]]; then
    ok "PCManFM $PCMANFM_TAG with Space preview is installed"
    return
  fi

  local work=${XDG_CACHE_HOME:-$HOME/.cache}/elachisto/build/pcmanfm
  local log=$STATE_DIR/pcmanfm-build.log
  mkdir -p "$STATE_DIR"; : > "$log"
  note "downloading PCManFM $PCMANFM_TAG"
  fetch_commit "$PCMANFM_URL" "$PCMANFM_COMMIT" "$work" >>"$log" 2>&1 \
    || die "could not download PCManFM (log: $log)"
  git -C "$work" apply "$patch" >>"$log" 2>&1 \
    || die "the Space-preview patch does not apply to PCManFM $PCMANFM_TAG (log: $log)"

  note "building (log: $log)"
  (
    cd "$work"
    ./autogen.sh
    ./configure --prefix="$PCMANFM_PREFIX" --with-gtk=3
    make -j"$(nproc)"
  ) >>"$log" 2>&1 || { tail -n 20 "$log" >&2; die "PCManFM did not build (log: $log)"; }
  grep -q preview_cmd "$work/src/pcmanfm" \
    || die "the built PCManFM lacks the Space-preview code; the patch did not take effect"

  sudo make -C "$work" install >>"$log" 2>&1 || die "PCManFM did not install (log: $log)"
  sudo rm -f "$PCMANFM_PREFIX"/share/applications/pcmanfm*.desktop
  echo "$want" | sudo install -D -m 644 /dev/stdin "$PCMANFM_STAMP"
  changed "installed PCManFM $PCMANFM_TAG with Space preview to $PCMANFM_PREFIX"
}
