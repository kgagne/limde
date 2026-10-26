# Install Mozilla's Firefox to ~/.local/opt/firefox, a folder you own, so Firefox's own
# updater can keep it current. Once installed, limde never changes its version.
# The download is checked against Mozilla's signed SHA256SUMS (see pins/firefox).

FIREFOX_DIR=$HOME/.local/opt/firefox
FIREFOX_PROFILE=/etc/apparmor.d/limde-firefox

# Mozilla's locale for this system's language, if Mozilla builds it; else en-US.
firefox_locale() {  # $1: SHA256SUMS text
  local lang=${LANG%%.*} candidate
  for candidate in "${lang/_/-}" "${lang%%_*}"; do
    [[ -n $candidate && $candidate != C && $candidate != POSIX ]] || continue
    grep -q " linux-x86_64/$candidate/firefox-" <<< "$1" && { echo "$candidate"; return; }
  done
  echo en-US
}

firefox_download() {
  # shellcheck source=/dev/null
  . "$LIMDE_ROOT/pins/firefox"
  local work=$1 version sums locale name sha
  version=$(curl -fsSL "$FIREFOX_VERSIONS_URL" | sed -n 's/.*"LATEST_FIREFOX_VERSION": *"\([^"]*\)".*/\1/p')
  [[ -n $version ]] || die "could not find the current Firefox version"
  local base=$FIREFOX_RELEASES_URL/$version
  curl -fsSL -o "$work/KEY" "$base/KEY" \
    && curl -fsSL -o "$work/SHA256SUMS" "$base/SHA256SUMS" \
    && curl -fsSL -o "$work/SHA256SUMS.asc" "$base/SHA256SUMS.asc" \
    || die "could not download Firefox $version's checksums"

  mkdir -m 700 "$work/gnupg"
  gpg --homedir "$work/gnupg" --batch --quiet --import "$work/KEY" 2>/dev/null
  local fpr
  fpr=$(gpg --homedir "$work/gnupg" --batch --with-colons --fingerprint 2>/dev/null | awk -F: '/^fpr/{print $10; exit}')
  [[ $fpr == "$MOZILLA_RELEASE_KEY_FPR" ]] \
    || die "Mozilla's release key has an unexpected fingerprint ($fpr); not installing Firefox"
  gpg --homedir "$work/gnupg" --batch --export > "$work/mozilla.gpg"
  gpgv --keyring "$work/mozilla.gpg" "$work/SHA256SUMS.asc" "$work/SHA256SUMS" 2>/dev/null \
    || die "Firefox $version's checksums are not signed by Mozilla's release key"

  sums=$(cat "$work/SHA256SUMS")
  locale=$(firefox_locale "$sums")
  name=$(grep -oE " linux-x86_64/$locale/firefox-$version\.tar\.(xz|bz2)$" <<< "$sums" | head -n 1 | tr -d ' ')
  [[ -n $name ]] || die "no Firefox $version build for linux-x86_64/$locale"
  sha=$(grep " $name$" <<< "$sums" | cut -d' ' -f1)
  note "downloading Firefox $version ($locale)"
  curl -fsSL -o "$work/firefox.tar" "$base/$name" || die "could not download Firefox"
  echo "$sha  $work/firefox.tar" | sha256sum -c --quiet - || die "Firefox download does not match Mozilla's signed checksum"
  FIREFOX_VERSION=$version
}

step_firefox() {
  heading "Firefox (Mozilla's build, updates itself)"
  if [[ -x $FIREFOX_DIR/firefox ]]; then
    ok "Firefox is installed ($("$FIREFOX_DIR/firefox" --version 2>/dev/null)); it updates itself"
  else
    local work; work=$(mktemp -d)
    firefox_download "$work"
    mkdir -p "$(dirname "$FIREFOX_DIR")"
    tar -xf "$work/firefox.tar" -C "$work" || die "could not unpack Firefox"
    [[ -x $work/firefox/firefox ]] || die "the Firefox archive has an unexpected layout"
    mkdir -p "$work/firefox/distribution"
    cp "$LIMDE_ROOT/config/firefox/policies.json" "$work/firefox/distribution/policies.json"
    mv "$work/firefox" "$FIREFOX_DIR"
    rm -rf "$work"
    changed "installed Firefox $FIREFOX_VERSION to $FIREFOX_DIR"
  fi

  if ! sudo cmp -s "$LIMDE_ROOT/components/firefox/apparmor-profile" "$FIREFOX_PROFILE" 2>/dev/null; then
    sudo install -m 644 "$LIMDE_ROOT/components/firefox/apparmor-profile" "$FIREFOX_PROFILE"
    sudo apparmor_parser -r "$FIREFOX_PROFILE" || die "the Firefox AppArmor profile did not load"
    changed "Firefox may use its sandbox ($FIREFOX_PROFILE)"
  else
    ok "Firefox AppArmor profile is in place"
  fi

  mkdir -p "$HOME/.local/bin"
  if [[ $(readlink "$HOME/.local/bin/firefox" 2>/dev/null) != "$FIREFOX_DIR/firefox" ]]; then
    ln -sfn "$FIREFOX_DIR/firefox" "$HOME/.local/bin/firefox"
    changed "firefox command in ~/.local/bin"
  fi

  local entry=$HOME/.local/share/applications/firefox.desktop want
  want=$(cat <<EOF
[Desktop Entry]
Type=Application
Name=Firefox
GenericName=Web Browser
Comment=Browse the web
Exec=$FIREFOX_DIR/firefox %u
Icon=$FIREFOX_DIR/browser/chrome/icons/default/default128.png
Terminal=false
Categories=Network;WebBrowser;
MimeType=text/html;x-scheme-handler/http;x-scheme-handler/https;
StartupWMClass=firefox
EOF
)
  if [[ $(cat "$entry" 2>/dev/null) != "$want" ]]; then
    mkdir -p "$(dirname "$entry")"
    echo "$want" > "$entry"
    changed "Firefox in the app menu"
  fi
}
