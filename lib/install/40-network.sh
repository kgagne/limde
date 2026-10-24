# Let NetworkManager manage the network, so the panel can show and change it.
# Ubuntu Server uses systemd-networkd through netplan. Switch netplan's renderer, wait
# until NetworkManager has a connection, and only then turn networkd off. If no
# connection comes up, put everything back.

NETPLAN_FILE=/etc/netplan/90-elachisto-networkmanager.yaml

# Connected, and names resolve: NetworkManager reports "connected" slightly before DNS works.
nm_connected() {
  [[ $(nmcli -t -f STATE general 2>/dev/null) == connected* ]] && getent hosts archive.ubuntu.com >/dev/null
}

step_network() {
  heading "Network"
  if [[ -f $NETPLAN_FILE ]] && nm_connected && ! systemctl -q is-enabled systemd-networkd.service 2>/dev/null; then
    ok "NetworkManager manages the network"
    return
  fi

  if [[ ! -f $NETPLAN_FILE ]]; then
    printf '%s\n' '# Written by elachisto: NetworkManager manages all interfaces.' \
      'network:' '  version: 2' '  renderer: NetworkManager' \
      | sudo install -m 600 /dev/stdin "$NETPLAN_FILE"
    sudo systemctl enable --now NetworkManager.service >/dev/null 2>&1
    sudo netplan apply || { sudo rm -f "$NETPLAN_FILE"; sudo netplan apply; die "netplan apply failed; restored"; }
    local i
    for i in $(seq 30); do nm_connected && break; sleep 1; done
    if ! nm_connected; then
      sudo rm -f "$NETPLAN_FILE"; sudo netplan apply
      die "NetworkManager did not connect (with working DNS) within 30 s; the previous network setup is restored"
    fi
    changed "netplan now uses NetworkManager ($NETPLAN_FILE)"
  fi

  local unit
  for unit in systemd-networkd.service systemd-networkd.socket systemd-networkd-wait-online.service \
              networkd-dispatcher.service; do
    if systemctl -q is-enabled "$unit" 2>/dev/null; then
      sudo systemctl disable --now "$unit" >/dev/null 2>&1
      changed "turned off $unit"
    fi
  done
  nm_connected || die "network lost after turning networkd off"
}
