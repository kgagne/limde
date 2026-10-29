# Lock after 5 minutes idle. At 8 minutes: on mains power, turn the screen off; on
# battery, suspend. Also lock before sleep, and when asked (Super+L, loginctl lock-session).
# At 90 seconds Tinybar minimises every window (on battery, by default), and the next
# input brings them back in their stacking order (tinybar-idle; Tinybar's README).
limde_lock='swaylock -f -C "$HOME/.config/swaylock/config"'
limde_on_mains='for f in /sys/class/power_supply/*/type; do [ "$(cat "$f")" = Mains ] && [ "$(cat "${f%/type}/online")" = 1 ] && exit 0; done; ls /sys/class/power_supply/*/capacity >/dev/null 2>&1 && exit 1 || exit 0'
swayidle -w \
    timeout 90 'tinybar-idle hide' resume 'tinybar-idle restore' \
    timeout 300 "$limde_lock" \
    timeout 480 "if sh -c '$limde_on_mains'; then wlopm --off '*'; else systemctl suspend --no-block; fi" \
    resume "wlopm --on '*'" \
    after-resume "wlopm --on '*'" \
    before-sleep "$limde_lock" \
    lock "$limde_lock" \
    >/dev/null 2>&1 &
