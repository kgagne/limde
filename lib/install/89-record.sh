# Record what was installed, from where and with which optional parts, for limde-update.

RECORD_FILE=/usr/local/share/limde/installed

step_record() {
  heading "Install record"
  local commit dirty="" want
  commit=$(git -C "$LIMDE_ROOT" rev-parse HEAD 2>/dev/null) || {
    note "not a Git clone; limde-update will not work from here"; return; }
  git -C "$LIMDE_ROOT" diff --quiet HEAD -- 2>/dev/null || dirty=yes
  want=$(printf 'commit=%s\nsource=%s\ngroups=%s\nmodified=%s\n' \
    "$commit" "$LIMDE_ROOT" "$(IFS=,; echo "${CHOSEN_GROUPS[*]}")" "${dirty:-no}")
  if [[ -f $RECORD_FILE && $(cat "$RECORD_FILE") == "$want" ]]; then
    ok "install record is up to date"
    return
  fi
  printf '%s\n' "$want" | sudo install -D -m 644 /dev/stdin "$RECORD_FILE"
  changed "recorded ${commit:0:12}${dirty:+ (with uncommitted changes)} in $RECORD_FILE"
}
