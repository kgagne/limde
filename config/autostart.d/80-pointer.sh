# The pointer starts in the middle of the screen. labwc has no command that runs one of
# its actions, so this presses the key bound to it, Alt+Super+H (labwc's rc.xml).
wtype -M alt -M logo -k h -m logo -m alt >/dev/null 2>&1 &
