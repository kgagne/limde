# Lock after 5 minutes idle. At 8 minutes: on mains power, turn the screen off; on
# battery, suspend. Also lock before sleep, and when asked (Super+L, loginctl lock-session).
elachisto_lock='swaylock -f -C "$HOME/.config/swaylock/config"'
elachisto_on_mains='for f in /sys/class/power_supply/*/type; do [ "$(cat "$f")" = Mains ] && [ "$(cat "${f%/type}/online")" = 1 ] && exit 0; done; ls /sys/class/power_supply/*/capacity >/dev/null 2>&1 && exit 1 || exit 0'
swayidle -w \
    timeout 300 "$elachisto_lock" \
    timeout 480 "if sh -c '$elachisto_on_mains'; then wlopm --off '*'; else systemctl suspend --no-block; fi" \
    resume "wlopm --on '*'" \
    after-resume "wlopm --on '*'" \
    before-sleep "$elachisto_lock" \
    lock "$elachisto_lock" \
    >/dev/null 2>&1 &
