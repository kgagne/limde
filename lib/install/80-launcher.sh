# Install Walker and Elephant from their pinned upstream releases (pins/launcher) into
# /usr/local. Every download is checked against its pinned sha256 before use.

LAUNCHER_STAMP=/usr/local/share/elachisto/launcher.versions

step_launcher() {
  heading "Launcher (Walker and Elephant)"
  # Elephant's file search runs `fd`; Ubuntu's fd-find names it fdfind.
  if [[ $(readlink /usr/local/bin/fd 2>/dev/null) != /usr/bin/fdfind ]]; then
    [[ -e /usr/local/bin/fd && ! -L /usr/local/bin/fd ]] \
      && die "/usr/local/bin/fd exists and is not elachisto's link to fdfind; move it aside"
    sudo ln -sfn /usr/bin/fdfind /usr/local/bin/fd
    changed "fd command for the launcher's file search (/usr/local/bin/fd)"
  fi
  # shellcheck source=/dev/null
  . "$ELACHISTO_ROOT/pins/launcher"
  local want="walker $WALKER_VERSION elephant $ELEPHANT_VERSION providers $ELEPHANT_PROVIDERS"
  if [[ -x /usr/local/bin/walker && -x /usr/local/bin/elephant && -f $LAUNCHER_STAMP \
        && $(cat "$LAUNCHER_STAMP") == "$want" ]]; then
    ok "Walker $WALKER_VERSION and Elephant $ELEPHANT_VERSION are installed"
    return
  fi

  local work=${XDG_CACHE_HOME:-$HOME/.cache}/elachisto/downloads/launcher
  rm -rf "$work"; mkdir -p "$work"
  local name url sha
  while read -r name url sha; do
    [[ -n $name ]] || continue
    curl -fsSL --retry 3 -o "$work/$name" "$url" || die "could not download $name"
    echo "$sha  $work/$name" | sha256sum -c --quiet - || die "$name does not match its pinned sha256"
    mkdir -p "$work/${name%.tar.gz}"
    tar -xzf "$work/$name" -C "$work/${name%.tar.gz}" || die "could not unpack $name"
  done <<< "$LAUNCHER_ASSETS"

  # One file per archive; find it rather than assuming the archive layout.
  find_one() { find "$work/$1" -type f -name "$2" | head -n 1; }
  local walker elephant
  walker=$(find_one "walker-v$WALKER_VERSION-x86_64-unknown-linux-gnu" walker)
  elephant=$(find_one elephant-linux-amd64 'elephant*')
  [[ -n $walker && -n $elephant ]] || die "Walker or Elephant missing from its release archive"
  chmod 755 "$walker" "$elephant"   # some releases ship without the executable bit
  [[ $("$elephant" version) == *"$ELEPHANT_VERSION"* ]] || die "Elephant does not report version $ELEPHANT_VERSION"

  sudo install -m 755 "$walker" /usr/local/bin/walker
  sudo install -m 755 "$elephant" /usr/local/bin/elephant
  local p so
  for p in $ELEPHANT_PROVIDERS; do
    so=$(find_one "$p-linux-amd64" '*.so')
    [[ -n $so ]] || die "provider $p missing from its release archive"
    sudo install -D -m 644 "$so" "/usr/local/lib/elephant/$p.so"
  done
  echo "$want" | sudo install -D -m 644 /dev/stdin "$LAUNCHER_STAMP"
  rm -rf "$work"
  changed "installed Walker $WALKER_VERSION and Elephant $ELEPHANT_VERSION (providers: $ELEPHANT_PROVIDERS)"
}
