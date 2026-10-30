# Show what will be installed and why; choose optional groups.

OPTIONAL_DIR=$LIMDE_ROOT/packages/optional
PACKAGES=()

optional_groups() { for f in "$OPTIONAL_DIR"/*.list; do basename "$f" .list; done; }

# A group's one-line description is the first comment line of its list.
group_title() { sed -n '1s/^#\s*//p' "$OPTIONAL_DIR/$1.list"; }

suggested() {
  case $1 in
    laptop) compgen -G '/sys/class/backlight/*' >/dev/null ;;
    bluetooth) compgen -G '/sys/class/bluetooth/*' >/dev/null ;;
    *) return 1 ;;
  esac
}

step_plan() {
  local with=("$@") group chosen=()
  for group in "${with[@]}"; do
    [[ -f $OPTIONAL_DIR/$group.list ]] \
      || die "unknown optional group: $group (available: $(optional_groups | tr '\n' ' '))"
  done

  heading "What limde installs"
  echo "  Runtime packages (needed for the desktop):"
  show_list "$LIMDE_ROOT/packages/runtime.list"

  echo
  echo "  Build packages (for the parts built from source; they stay installed):"
  show_list "$LIMDE_ROOT/packages/build.list"

  heading "Optional parts"
  for group in $(optional_groups); do
    echo "  $group: $(group_title "$group")"
    show_list "$OPTIONAL_DIR/$group.list"
    if printf '%s\n' "${with[@]}" | grep -qx "$group"; then
      chosen+=("$group"); note "→ included (--with)"
    elif ((ASSUME_YES || PLAN_ONLY)); then
      note "→ not included (add --with=$group)"
    else
      local default=n; suggested "$group" && default=y
      if ask "Include $group?" "$default"; then chosen+=("$group"); fi
    fi
  done

  mapfile -t PACKAGES < <(list_packages "$LIMDE_ROOT/packages/runtime.list"
    list_packages "$LIMDE_ROOT/packages/build.list"
    for group in "${chosen[@]}"; do list_packages "$OPTIONAL_DIR/$group.list"; done)

  # Count what apt would actually add, dependencies included (a simulation; no root).
  local total
  total=$(apt-get -s install --no-install-recommends "${PACKAGES[@]}" 2>/dev/null | grep -c '^Inst ' || true)
  heading "Summary"
  echo "  ${#PACKAGES[@]} packages listed; with their dependencies, $total new package(s) would be installed."
  dpkg_interrupted \
    && note "An earlier package install was cut short; it is finished first (the count above may be low)."

  if ((PLAN_ONLY)); then
    heading "Plan only"; echo "  Nothing was changed."; return
  fi
  if ((!ASSUME_YES)); then
    echo
    ask "Install ${#PACKAGES[@]} packages and set up the desktop?" y || die "stopped; nothing was changed"
  fi
}
