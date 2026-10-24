# Build labwc (with wlroots built in) from the commits pinned in pins/labwc and install
# it to /usr/local. Before installing, the new build must start and stop cleanly in a
# headless test session, so a broken build never replaces a working one.

LABWC_PREFIX=/usr/local
LABWC_STAMP=$LABWC_PREFIX/share/elachisto/labwc.commit

# Fetch exactly one commit of a repository into a directory.
# Returns non-zero on failure; callers report it (their output may go to a log).
fetch_commit() {  # $1: url, $2: commit, $3: directory
  rm -rf "$3" && mkdir -p "$3" \
    && git -C "$3" init -q \
    && git -C "$3" fetch -q --depth 1 "$1" "$2" \
    && git -C "$3" checkout -q FETCH_HEAD \
    && [[ $(git -C "$3" rev-parse HEAD) == "$2" ]]
}

step_labwc() {
  heading "labwc (built from source)"
  # shellcheck source=/dev/null
  . "$ELACHISTO_ROOT/pins/labwc"
  local want="$LABWC_COMMIT $WLROOTS_COMMIT"
  if [[ -x $LABWC_PREFIX/bin/labwc && -f $LABWC_STAMP && $(cat "$LABWC_STAMP") == "$want" ]]; then
    ok "labwc ${LABWC_COMMIT:0:12} is installed ($($LABWC_PREFIX/bin/labwc --version | head -1))"
    return
  fi

  local work=${XDG_CACHE_HOME:-$HOME/.cache}/elachisto/build/labwc
  local log=$STATE_DIR/labwc-build.log
  mkdir -p "$STATE_DIR"; : > "$log"
  note "downloading labwc ${LABWC_COMMIT:0:12} and wlroots ${WLROOTS_COMMIT:0:12}"
  fetch_commit "$LABWC_URL" "$LABWC_COMMIT" "$work/source" >>"$log" 2>&1 \
    || die "could not download labwc (log: $log)"
  fetch_commit "$WLROOTS_URL" "$WLROOTS_COMMIT" "$work/source/subprojects/wlroots" >>"$log" 2>&1 \
    || die "could not download wlroots (log: $log)"

  note "building (a few minutes; log: $log)"
  rm -rf "$work/build"
  {
    meson setup "$work/build" "$work/source" --prefix="$LABWC_PREFIX" \
      --buildtype=debugoptimized --wrap-mode=nodownload \
      -Dtest=disabled -Dman-pages=enabled -Dxwayland=enabled -Dsvg=enabled -Dicon=enabled \
      -Dlabnag=enabled -Dnls=disabled -Dsystemd-session=disabled -Dstatic_analyzer=disabled \
      -Dforce_fallback_for=wlroots-0.20 -Dwlroots:default_library=static \
      -Dwlroots:examples=false -Dwlroots:backends=drm,libinput -Dwlroots:renderers=gles2 \
      -Dwlroots:allocators=gbm,udmabuf -Dwlroots:session=enabled \
      -Dwlroots:color-management=enabled -Dwlroots:xwayland=enabled \
      -Dwlroots:libliftoff=enabled -Dwlroots:xcb-errors=disabled
    meson compile -C "$work/build"
  } >>"$log" 2>&1 || { tail -n 20 "$log" >&2; die "labwc did not build (log: $log)"; }

  # Start the new build in a throwaway headless session; it must exit cleanly.
  local runtime; runtime=$(mktemp -d)
  if ! env -u WAYLAND_DISPLAY -u DISPLAY XDG_RUNTIME_DIR="$runtime" \
       WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1 \
       timeout 30 "$work/build/labwc" -S true >>"$log" 2>&1; then
    rm -rf "$runtime"; tail -n 20 "$log" >&2
    die "the new labwc build did not start in a headless test (log: $log)"
  fi
  rm -rf "$runtime"

  sudo meson install -C "$work/build" --no-rebuild --skip-subprojects >>"$log" 2>&1 \
    || die "labwc did not install (log: $log)"
  echo "$want" | sudo install -D -m 644 /dev/stdin "$LABWC_STAMP"
  changed "installed labwc ${LABWC_COMMIT:0:12} to $LABWC_PREFIX ($("$LABWC_PREFIX/bin/labwc" --version | head -1))"
}
