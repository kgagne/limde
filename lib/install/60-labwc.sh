# Build labwc (with wlroots built in) from the commits pinned in pins/labwc and install
# it to /usr/local. Before installing, the new build must pass labwc_headless_test: it
# starts and stops cleanly in a headless test session and reads limde's rc.xml without a
# configuration error, so a broken build never replaces a working one.

LABWC_PREFIX=/usr/local
LABWC_STAMP=$LABWC_PREFIX/share/limde/labwc.commit

# Fetch exactly one commit of a repository into a directory.
# Returns non-zero on failure; callers report it (their output may go to a log).
fetch_commit() {  # $1: url, $2: commit, $3: directory
  rm -rf "$3" && mkdir -p "$3" \
    && git -C "$3" init -q \
    && git -C "$3" fetch -q --depth 1 "$1" "$2" \
    && git -C "$3" checkout -q FETCH_HEAD \
    && [[ $(git -C "$3" rev-parse HEAD) == "$2" ]]
}

# Start a labwc build in a throwaway headless session that reads only a copy of the given
# rc.xml. The session is cut off from the one you may be running: its own config folder
# (with an empty autostart and shutdown, so no limde or user autostart piece runs), its
# own runtime folder, no session D-Bus, no display, no WLR_*DRM* device choice and no
# update of the D-Bus or systemd environment. -V makes labwc log which rc.xml it read.
# It fails when labwc does not exit cleanly within 30 s, when it did not read the rc.xml,
# or when it logs a configuration error: an [ERROR] line from labwc's configuration
# reader (src/config/, an action's arguments in src/action.c, a yes/no or number value in
# src/common/parse-*.c), which includes "error parsing config file" for XML that does not
# parse (a theme's yes/no values go through the same parser, so a broken limde theme
# counts too). Other [ERROR] lines (a missing helper, a display problem) do not count:
# labwc starts despite them, and a first install has no earlier build to compare with.
# The reason goes to stderr, labwc's output is appended to the log.
labwc_headless_test() {  # $1: labwc program, $2: rc.xml, $3: log
  local dir status=0 errors
  local reader='\[ERROR\] \[([^]]*/)?src/(config/[^]]*|action\.c|common/parse-[a-z]+\.c):[0-9]+\]'
  dir=$(mktemp -d) || return 1
  mkdir -m 700 "$dir/runtime" && mkdir "$dir/config" \
    && cp "$2" "$dir/config/rc.xml" && : >"$dir/config/autostart" && : >"$dir/config/shutdown" \
    || { rm -rf "$dir"; echo "could not prepare the headless test" >&2; return 1; }
  env -u WAYLAND_DISPLAY -u WAYLAND_SOCKET -u DISPLAY -u DBUS_SESSION_BUS_ADDRESS \
      -u WLR_DRM_DEVICES -u WLR_RENDER_DRM_DEVICE \
      XDG_RUNTIME_DIR="$dir/runtime" XDG_CONFIG_HOME="$dir/config" XDG_CONFIG_DIRS="$dir/config" \
      WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1 \
      LABWC_UPDATE_ACTIVATION_ENV=no \
      timeout 30 "$1" -V -C "$dir/config" -S true >"$dir/out" 2>&1 || status=$?
  { echo "== headless test: $1 -C (copy of $2) -S true, exit $status =="; cat "$dir/out"; } >>"$3"
  if ((status)); then
    tail -n 20 "$dir/out" >&2
    echo "labwc did not start and stop cleanly (exit $status)" >&2
  elif ! grep -qF "read config file $dir/config/rc.xml" "$dir/out"; then
    echo "labwc did not read the rc.xml" >&2; status=1
  elif errors=$(grep -E "$reader" "$dir/out"); then
    { grep -F 'parser error' "$dir/out" || true; echo "$errors"
      echo "labwc logged configuration errors reading $2"; } >&2
    status=1
  fi
  rm -rf "$dir"
  return "$status"
}

step_labwc() {
  heading "labwc (built from source)"
  # shellcheck source=/dev/null
  . "$LIMDE_ROOT/pins/labwc"
  local want="$LABWC_COMMIT $WLROOTS_COMMIT"
  if [[ -x $LABWC_PREFIX/bin/labwc && -f $LABWC_STAMP && $(cat "$LABWC_STAMP") == "$want" ]]; then
    ok "labwc ${LABWC_COMMIT:0:12} is installed ($($LABWC_PREFIX/bin/labwc --version | head -1))"
    return
  fi

  local work=${XDG_CACHE_HOME:-$HOME/.cache}/limde/build/labwc
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

  note "testing the new build headless with limde's rc.xml"
  labwc_headless_test "$work/build/labwc" "$LIMDE_ROOT/config/labwc/rc.xml" "$log" \
    || die "the new labwc build failed its headless test, so it was not installed (log: $log)"

  sudo meson install -C "$work/build" --no-rebuild --skip-subprojects >>"$log" 2>&1 \
    || die "labwc did not install (log: $log)"
  echo "$want" | sudo install -D -m 644 /dev/stdin "$LABWC_STAMP"
  changed "installed labwc ${LABWC_COMMIT:0:12} to $LABWC_PREFIX ($("$LABWC_PREFIX/bin/labwc" --version | head -1))"
}
