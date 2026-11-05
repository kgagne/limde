# Let NetworkManager manage the network, so the panel can show and change it.
# Ubuntu Server uses systemd-networkd through netplan. Switch netplan's renderer, wait
# until NetworkManager has a connection, and only then turn networkd off. If no
# connection comes up, put everything back.

NETPLAN_FILE=/etc/netplan/90-limde-networkmanager.yaml

# Connected, and names resolve: NetworkManager reports "connected" slightly before DNS works.
nm_connected() {
  [[ $(nmcli -t -f STATE general 2>/dev/null) == connected* ]] && getent hosts archive.ubuntu.com >/dev/null
}

# networkd's service and sockets that are running, one per line. Turning networkd off
# stops only the units named, and its sockets keep listening: the next connection to one
# (systemd-resolved's hook, for example) starts networkd again.
networkd_active() {
  systemctl list-units --plain --no-legend --state=active \
    systemd-networkd.service 'systemd-networkd*.socket' 2>/dev/null | awk '{print $1}' || true
}

step_network() {
  heading "Network"
  if [[ -f $NETPLAN_FILE ]] && nm_connected && ! systemctl -q is-enabled systemd-networkd.service 2>/dev/null \
     && [[ -z $(networkd_active) ]]; then
    ok "NetworkManager manages the network"
    return
  fi

  if [[ ! -f $NETPLAN_FILE ]]; then
    printf '%s\n' '# Written by limde: NetworkManager manages all interfaces.' \
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
  # Disabling the service disabled its sockets too (its Also= line), but left them
  # listening. Stop them first, so nothing can start networkd again, then networkd.
  local active sockets
  active=$(networkd_active)
  if [[ -n $active ]]; then
    mapfile -t sockets < <(grep '\.socket$' <<< "$active" || true)
    ((${#sockets[@]} == 0)) || sudo systemctl stop "${sockets[@]}"
    sudo systemctl stop systemd-networkd.service
    active=$(networkd_active)
    [[ -z $active ]] || die "networkd is still running: ${active//$'\n'/ }"
    # Until now networkd also ran the links NetworkManager took over. Stopping it removed
    # the address they shared, and systemd-resolved dropped the DNS servers it had from
    # networkd (it refused NetworkManager's while networkd ran). Connect NetworkManager's
    # devices again, so it sets both.
    local device
    while read -r device; do
      sudo nmcli device connect "$device" >/dev/null 2>&1 || true
    done < <(nmcli -t -f DEVICE,STATE device 2>/dev/null | sed -n 's/:connected$//p')
    changed "stopped networkd and its sockets"
  fi
  local i
  for i in $(seq 30); do nm_connected && break; sleep 1; done
  nm_connected || die "network lost after turning networkd off"
}
