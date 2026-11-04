#!/usr/bin/env python3

import datetime
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import time
import tomllib
from collections import OrderedDict, deque
from pathlib import Path

import gi
from tinybar_icons import (
    IconLibrary,
    StatusIndicator,
    battery_glyph,
    brightness_glyph,
    desktop_entry,
    glyph_widget,
    layered_glyph,
    microphone_glyph,
    set_layered_glyph,
    signal_glyph,
    volume_glyph,
)

gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
gi.require_version("GioUnix", "2.0")
gi.require_version("GLibUnix", "2.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gsk", "4.0")

from gi.repository import (
    Gdk,
    Gio,
    GioUnix,
    GLib,
    GLibUnix,
    Graphene,
    Gsk,
    Gtk,
    Gtk4LayerShell,
    Pango,
)


def first_device(pattern, fallback):
    """The first matching sysfs device, so the panel works on any laptop or desktop."""
    found = sorted(Path("/sys/class").glob(pattern))
    return found[0] if found else Path("/sys/class") / fallback


# TINYBAR_BATTERY_DIR stands in another battery folder (a test's or VM's fake one).
BATTERY = (Path(os.environ["TINYBAR_BATTERY_DIR"]) if os.environ.get("TINYBAR_BATTERY_DIR")
           else first_device("power_supply/BAT*", "power_supply/BAT0"))
# TINYBAR_BACKLIGHT_DIR stands in another backlight folder (a test's fake one); the
# tinybar-brightness it runs reads the same variable.
BACKLIGHT = (Path(os.environ["TINYBAR_BACKLIGHT_DIR"]) if os.environ.get("TINYBAR_BACKLIGHT_DIR")
             else first_device("backlight/*", "backlight/none"))
HAS_BATTERY = (BATTERY / "capacity").exists()
HAS_BACKLIGHT = (BACKLIGHT / "brightness").exists()

RUNTIME_DIR = Path(
    f"/run/user/{os.getuid()}/tinybar"
)

VOLUME_STATE = RUNTIME_DIR / "volume"
# Written only by the mic-mute key, ending in a "key" line like VOLUME_STATE's.
MICROPHONE_STATE = RUNTIME_DIR / "microphone"
# tinybar-idle reads this to signal the panel: SIGUSR1 hides, SIGUSR2 restores.
PID_FILE = RUNTIME_DIR / "tinybar.pid"

CONFIG_DIR = Path.home() / ".config/tinybar"
STYLE_FILE = CONFIG_DIR / "style.css"
# The window-list helper is installed beside this file.
TOPLEVEL_HELPER = Path(__file__).resolve().with_name("toplevel-helper")

STATE_DIR = Path.home() / ".local/state/tinybar"
# The history database (SQLite): 5-minute buckets and the raw samples behind them.
HISTORY_DB = STATE_DIR / "history.sqlite"
# Before 2026-11-04 the buckets were lines in this file; it is imported once, then renamed
# to history.jsonl.imported.
HISTORY_FILE = STATE_DIR / "history.jsonl"

BATTERY_SAMPLE_SECONDS = 5
USAGE_SAMPLE_SECONDS = 2
TEMP_SAMPLE_SECONDS = 30
NOTIFICATION_SAMPLE_SECONDS = 2
# Log out, restart and power off ask for a second click; the question clears after this.
CONFIRM_SECONDS = 4
# A click on another panel button while a popover is open opens that button's popover
# this long after GTK closed the first one (PanelMenus).
SWITCH_DELAY_SECONDS = 0
# GTK's own default double-click time, for when its setting cannot be read. A second
# click sooner than the double-click time is the rest of a double-click, not an answer.
DOUBLE_CLICK_MS = 400

# CPU and RAM readouts are off in the panel until they show something more
# useful. The sampling code stays; with this off it is never scheduled, so
# those two metrics also stop being added to the history file. The battery
# popover shows both anyway (see update_battery).
SHOW_USAGE = False
TINYBAR_APP_IDS = {
    "limde.Tinybar",
    "tinybar",
}


def load_settings():
    """Optional ~/.config/tinybar/settings.toml; missing or broken means defaults."""
    try:
        return tomllib.loads((CONFIG_DIR / "settings.toml").read_text())
    except (OSError, ValueError):
        return {}


# This app's button always sits leftmost, ahead of every other app, however
# often its window closes and reopens, and shows only its icon. Defaults to
# limde's agent-web window; set first_app_id in settings.toml to change it.
FIRST_APP_ID = load_settings().get("first_app_id", "limde.AgentWeb")

# Widest an app's name gets on its task button, in characters, before it ends in "…".
# With many apps open the names shrink further, so the list stops short of the clock.
TASK_NAME_MAX_CHARS = 20

# Idle hide: swayidle (autostart.d/20-idle.sh) runs `tinybar-idle hide` after 90 s without
# input and `tinybar-idle restore` at the next input. Hiding minimises every window
# except those in idle_hide_keep; restoring brings back only those, bottom of the stack
# first, then focuses the window that had focus. The stack order is the order windows
# last had focus (Labwc raises the focused window). By default it hides only on battery.
IDLE_HIDE = load_settings().get("idle_hide", True)
IDLE_HIDE_BATTERY_ONLY = load_settings().get("idle_hide_battery_only", True)
IDLE_HIDE_KEEP = {app_id.casefold() for app_id in load_settings().get("idle_hide_keep", [])}

# Tailscale button beside Wi-Fi: "auto" (the default) shows it when the tailscale
# command is installed; false hides it; true shows it even when it is missing.
TAILSCALE = load_settings().get("tailscale", "auto")
TAILSCALE_SAMPLE_SECONDS = 10
# `tailscale up` waits until connected; the button stops waiting after this and
# leaves tailscaled to keep trying. (A --timeout flag would make `up` demand every
# non-default setting be repeated, so the bare command is used.)
TAILSCALE_UP_SECONDS = 15

# Bluetooth menu beside Wi-Fi: "auto" (the default) shows it while BlueZ runs with an
# adapter; false hides it; true shows it even without one.
BLUETOOTH = load_settings().get("bluetooth", "auto")

HISTORY_BUCKET_SECONDS = 300
# The database keeps 90 days; the panel keeps the 7 its graph can show in memory.
HISTORY_RETENTION_SECONDS = 90 * 24 * 60 * 60
HISTORY_MEMORY_SECONDS = 7 * 24 * 60 * 60
HISTORY_PRUNE_SECONDS = 24 * 60 * 60
# Raw samples are kept for metrics read every 5 s or slower; the 2-second panel readings
# (CPU, memory) would multiply the database's size for little more detail.
HISTORY_RAW_MIN_INTERVAL = 5

MAKO_NAME = "org.freedesktop.Notifications"
MAKO_PATH = "/fr/emersion/Mako"
MAKO_INTERFACE = "fr.emersion.Mako"

# Mako answers immediately; a short ceiling keeps a wedged daemon from
# stalling the panel's main loop on every poll.
MAKO_TIMEOUT_MS = 500
# The Mako mode that hides pop-ups; mako.conf's [mode=do-not-disturb] section makes
# every notification but a critical one invisible while it is set.
DO_NOT_DISTURB_MODE = "do-not-disturb"

# The standard notification interface, which Mako serves under the same bus name;
# the battery warnings are posted through it.
NOTIFICATIONS_PATH = "/org/freedesktop/Notifications"
NOTIFICATIONS_INTERFACE = "org.freedesktop.Notifications"
NOTIFY_URGENCY_NORMAL = 1
NOTIFY_URGENCY_CRITICAL = 2

NOTIFICATION_SUMMARY_CHARS = 44
NOTIFICATION_BODY_CHARS = 60
NOTIFICATION_LIST_HEIGHT = 320

# Space between the panel's bottom edge and a popover's top edge, and the least
# between a popover and the screen's left or right edge.
POPOVER_GAP = 4

NM_NAME = "org.freedesktop.NetworkManager"
NM_PATH = "/org/freedesktop/NetworkManager"
NM_DEVICE = "org.freedesktop.NetworkManager.Device"
NM_WIRELESS = "org.freedesktop.NetworkManager.Device.Wireless"
NM_ACCESS_POINT = "org.freedesktop.NetworkManager.AccessPoint"
NM_IP4_CONFIG = "org.freedesktop.NetworkManager.IP4Config"
NM_DEVICE_TYPE_ETHERNET = 1
NM_DEVICE_TYPE_WIFI = 2
NM_DEVICE_STATE_ACTIVATED = 100
NM_AP_FLAGS_PRIVACY = 0x1
# Key management bits of an access point's WpaFlags/RsnFlags (NM80211ApSecurityFlags).
NM_AP_SEC_KEY_MGMT_PSK = 0x100
NM_AP_SEC_KEY_MGMT_802_1X = 0x200
NM_AP_SEC_KEY_MGMT_SAE = 0x400
NM_AP_SEC_KEY_MGMT_OWE = 0x800
NM_AP_SEC_KEY_MGMT_OWE_TM = 0x1000
NM_AP_SEC_KEY_MGMT_EAP_SUITE_B_192 = 0x2000
NM_SETTINGS = "org.freedesktop.NetworkManager.Settings"
NM_SETTINGS_PATH = "/org/freedesktop/NetworkManager/Settings"
NM_CONNECTION = "org.freedesktop.NetworkManager.Settings.Connection"
NM_ACTIVE = "org.freedesktop.NetworkManager.Connection.Active"
NM_ACTIVE_STATE_ACTIVATED = 2
NM_ACTIVE_STATE_DEACTIVATED = 4
NM_ACTIVE_REASON_CONNECT_TIMEOUT = 6
NM_ACTIVE_REASON_NO_SECRETS = 9
NM_ACTIVE_REASON_LOGIN_FAILED = 10
NM_DEVICE_STATE_FAILED = 120
# Device failure reasons (NMDeviceStateReason) that mean the password was not accepted.
NM_DEVICE_REASON_NO_SECRETS = 7
NM_DEVICE_REASON_SSID_NOT_FOUND = 53
# Joining a network: NetworkManager's own attempt rarely runs past half a minute.
# NetworkManager's Connectivity property. It reports PORTAL (a hotel or airport
# sign-in page is in the way) only while its connectivity check is on, which the
# network-manager-config-connectivity-ubuntu package turns on.
NM_CONNECTIVITY_PORTAL = 2
NM_CONNECT_SECONDS = 45
NM_ACTION_TIMEOUT_MS = 10000
# "Other network…": hidden networks, enterprise logins and anything else nmtui handles.
OTHER_NETWORK_COMMAND = ["foot", "nmtui"]
NM_TIMEOUT_MS = 1000

NETWORK_LIST_HEIGHT = 320

BLUEZ_NAME = "org.bluez"
BLUEZ_ADAPTER = "org.bluez.Adapter1"
BLUEZ_DEVICE = "org.bluez.Device1"
BLUEZ_BATTERY = "org.bluez.Battery1"
BLUEZ_AGENT_MANAGER = "org.bluez.AgentManager1"
# Tinybar is the pairing agent. It can show a number and take a yes or no in the
# popover, so its capability is DisplayYesNo; it never asks for a typed PIN.
BLUEZ_AGENT_PATH = "/limde/tinybar/agent"
BLUEZ_AGENT_XML = """<node><interface name="org.bluez.Agent1">
<method name="Release"/><method name="Cancel"/>
<method name="RequestPinCode"><arg type="o"/><arg type="s" direction="out"/></method>
<method name="RequestPasskey"><arg type="o"/><arg type="u" direction="out"/></method>
<method name="DisplayPinCode"><arg type="o"/><arg type="s"/></method>
<method name="DisplayPasskey"><arg type="o"/><arg type="u"/><arg type="q"/></method>
<method name="RequestConfirmation"><arg type="o"/><arg type="u"/></method>
<method name="RequestAuthorization"><arg type="o"/></method>
<method name="AuthorizeService"><arg type="o"/><arg type="s"/></method>
</interface></node>"""
# Pairing waits for the person to compare numbers or type one on a keyboard.
BLUEZ_PAIR_TIMEOUT_MS = 90000
BLUEZ_CONNECT_TIMEOUT_MS = 30000
# Changes several times a second while searching, and nothing shows them.
BLUEZ_QUIET = {"RSSI", "TxPower", "ManufacturerData", "ServiceData"}
# BlueZ error names (org.bluez.Error.*) in words.
BLUEZ_FAILURES = {
    "AuthenticationFailed": "Pairing failed; try again",
    "AuthenticationCanceled": "Pairing was cancelled",
    "AuthenticationRejected": "Pairing was refused",
    "AuthenticationTimeout": "The device did not answer in time",
    "ConnectionAttemptFailed": "The device did not answer",
    "InProgress": "Busy; try again in a moment",
    "NotReady": "Bluetooth is off",
    "ProfileUnavailable": "Nothing on this device to connect to",
}
# "Other device…": devices that want a PIN typed, and anything else bluetoothctl does.
OTHER_DEVICE_COMMAND = ["foot", "bluetoothctl"]

WPCTL = "/usr/bin/wpctl"
# Reports every PipeWire change as JSON; from pipewire-bin, which pipewire needs.
AUDIO_MONITOR_COMMAND = ["/usr/bin/pw-dump", "--monitor", "--no-colors"]
# Sets the default microphone; from pipewire-bin too.
PW_METADATA = "/usr/bin/pw-metadata"
# PipeWire sends bursts of changes; one volume read follows a burst.
AUDIO_EVENT_MS = 100
# pw-dump quits when PipeWire restarts; it is started again after this. While it keeps
# quitting at once (PipeWire down), each wait doubles, up to the maximum.
AUDIO_MONITOR_RETRY_SECONDS = 5
AUDIO_MONITOR_RETRY_MAX_SECONDS = 60

# The brightness slider changes the backlight as the keys do, through tinybar-brightness
# (1-100 %, never 0), which needs brightnessctl (optional laptop install group). The
# copy beside this file when run from the source tree, else the installed one.
BRIGHTNESSCTL = os.environ.get("TINYBAR_BRIGHTNESSCTL", "/usr/bin/brightnessctl")
BRIGHTNESS_COMMAND = Path(__file__).resolve().with_name("tinybar-brightness")
# Backlight changes this soon after the slider's last one are the slider's: no overlay.
BRIGHTNESS_SLIDER_QUIET_SECONDS = 0.5

# How long the brightness/volume readout stays up after the last change.
LEVEL_OVERLAY_MS = 1500
LEVEL_OVERLAY_MARGIN = 96

# Smoothed discharge watts at which the battery icon changes colour. Tuned on a
# 15-inch laptop that idles around 6-8 W, where 12 W, 20 W and 30 W meant roughly
# 7 h, 4 h and under 3 h of battery.
BATTERY_LOAD_LEVELS = (
    (30.0, "load-severe"),
    (20.0, "load-high"),
    (12.0, "load-moderate"),
)

# Battery percentages that raise a notification, each at most once per discharge.
# The critical one is urgent: Mako keeps it on screen until it is dismissed.
BATTERY_LOW_PERCENT = 10
BATTERY_CRITICAL_PERCENT = 5
# A threshold is announced again only once a charge has taken the battery this many
# points above it, so a charger that flaps between charging and not cannot repeat it.
BATTERY_REARM_POINTS = 3

# A battery held by its charge limit reads at, or a point or two under, the end
# threshold (the firmware stops a little early, and capacity is rounded).
CHARGE_LIMIT_NEAR_POINTS = 2

# The battery popover's graph views, cycled with its arrows: name, span, bin
# size, and hours between gridlines (24 puts them at local midnight).
POWER_VIEWS = (
    ("3 hours", 3 * 60 * 60, 5 * 60, 1),
    ("24 hours", 24 * 60 * 60, 15 * 60, 6),
    ("7 days", 7 * 24 * 60 * 60, 60 * 60, 24),
)
POWER_GRAPH_WIDTH = 300
POWER_GRAPH_HEIGHT = 120
# Room under the plot for the gridline labels.
POWER_GRAPH_LABEL_HEIGHT = 16
# The graph's top is the highest bin average times the headroom, rounded up to
# the step and never below the minimum. Short spikes in the band may run off the
# top; scaling to them would flatten the line that matters.
POWER_GRAPH_HEADROOM = 1.5
POWER_GRAPH_STEP_W = 10
POWER_GRAPH_MIN_W = 10

METRIC_INTERVALS = {
    "power_w": BATTERY_SAMPLE_SECONDS,
    "cpu_percent": USAGE_SAMPLE_SECONDS,
    "memory_used_gib": USAGE_SAMPLE_SECONDS,
    "temperature_c": TEMP_SAMPLE_SECONDS,
}


def read_path(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def read_battery_text(name):
    return read_path(BATTERY / name)


def read_battery_int(name):
    value = read_battery_text(name)

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def format_runtime(hours):
    if hours is None or hours <= 0 or hours > 100:
        return None

    total_minutes = int(hours * 60)
    h, m = divmod(total_minutes, 60)

    if h:
        return f"{h}h {m:02d}m"

    return f"{m}m"


def format_hours(hours):
    """Remaining time for the panel: decimal hours, 3h 30m -> "3.5h"."""

    if hours is None or hours <= 0 or hours > 100:
        return None

    return f"{hours:.1f}h"


def battery_load(watts):
    """CSS class for a discharge rate, or None while it is in the normal range."""

    if watts is None:
        return None

    for threshold, name in BATTERY_LOAD_LEVELS:
        if watts >= threshold:
            return name

    return None


def battery_warning(percent, status, warned):
    """The low-battery threshold to announce now (or None), and the warned state to
    keep: the lowest threshold already announced this discharge, None for none.

    Each threshold is announced once per discharge, and a reading already below both
    announces only the critical one. Charging, full or plugged in ("Not charging")
    starts a threshold over only once the battery is BATTERY_REARM_POINTS above it,
    and an unknown status or percent keeps the state, so neither a flicker nor a
    charger that keeps dropping out can repeat one.
    """

    if percent is None:
        return None, warned

    if status in ("Charging", "Full", "Not charging"):
        if warned is None:
            return None, None

        # The thresholds still announced: the ones the charge has not cleared yet.
        kept = [
            threshold
            for threshold in (BATTERY_CRITICAL_PERCENT, BATTERY_LOW_PERCENT)
            if warned <= threshold and percent <= threshold + BATTERY_REARM_POINTS
        ]
        return None, (kept[0] if kept else None)

    if status != "Discharging":
        return None, warned

    for threshold in (BATTERY_CRITICAL_PERCENT, BATTERY_LOW_PERCENT):
        if percent <= threshold:
            if warned is None or threshold < warned:
                return threshold, threshold

            break

    return None, warned


def battery_warning_text(percent, threshold, runtime_text):
    """Summary and body of a low-battery notification."""

    if runtime_text:
        body = f"About {runtime_text} left."
    elif threshold == BATTERY_CRITICAL_PERCENT:
        body = "Plug in now."
    else:
        body = "Plug in soon."

    return f"Battery at {percent}%", body


def format_coverage(seconds):
    total_minutes = int(seconds / 60)

    if total_minutes < 1:
        return "<1m"

    h, m = divmod(total_minutes, 60)

    if h:
        return f"{h}h {m:02d}m"

    return f"{m}m"


def read_charge_limit():
    """The battery's charge limit as (end, start) percentages, each None when the
    driver has no such file. An end of 100 (or an unreadable one) is no limit."""

    end = read_battery_int("charge_control_end_threshold")
    start = read_battery_int("charge_control_start_threshold")

    if end is None or not 0 < end < 100:
        return None, None

    return end, start if start is not None and 0 <= start < end else None


def charge_limit_text(status, percent, end, start=None):
    """What the charge limit is doing, or None without one (end is None).

    Charging: it will stop at the limit. Plugged in and not charging (or reported
    full) at or near the end threshold: the limit holds the battery there. Between
    the start and end thresholds the firmware waits to drop below the start before
    it charges again. Otherwise "Not charging" has some other cause, so the limit is
    only stated, never given as the reason."""

    if end is None:
        return None

    if status == "Charging":
        return f"Charging to {end}%"

    if status in ("Not charging", "Full") and percent is not None:
        if percent >= end - CHARGE_LIMIT_NEAR_POINTS:
            return f"Held at {end}%"

        if start is not None and start <= percent < end:
            return f"Not charging until below {start}%"

    return f"Charge limit {end}%"


def battery_state(percent, status, end=None, start=None):
    """The battery's state line and its charge-limit line (None when there is no
    limit or the state line already says it): ("Battery 64%, charging to 80%",
    None), ("Battery 80%, plugged in", "Held at 80%")."""

    level = "Battery level unknown" if percent is None else f"Battery {percent}%"
    limit = charge_limit_text(status, percent, end, start)

    if status == "Charging":
        if end is not None:
            return f"{level}, charging to {end}%", None
        return f"{level}, charging", None

    if status == "Discharging":
        return f"{level}, on battery", limit

    if limit is not None and not limit.startswith("Charge limit"):
        # The limit explains why it is not charging.
        return f"{level}, plugged in", limit

    if status == "Full":
        return f"{level}, charged", limit

    if status == "Not charging":
        return f"{level}, plugged in, not charging", limit

    return level, limit


def battery_rows(percent, status, runtime_text=None, watts=None, end=None, start=None):
    """The battery popover's list, as (glyph, text) rows: the state, the draw on
    battery or the charge rate while charging, the time left or to full (or to the
    limit), then what the charge limit is doing. Rows without a reading are left
    out."""

    state, limit = battery_state(percent, status, end, start)

    if status == "Charging":
        glyph = "battery-bolt"
    elif status == "Not charging":
        glyph = "battery-plug"
    else:
        glyph = battery_glyph(percent) if percent is not None else "battery-exclamation"

    rows = [(glyph, state)]

    if status == "Discharging":
        if watts is not None:
            rows.append(("bolt", f"Drawing {watts:.1f} W"))
        if runtime_text:
            rows.append(("clock", f"{runtime_text} left"))
    elif status == "Charging":
        if watts is not None:
            rows.append(("bolt", f"Charging at {watts:.1f} W"))
        if runtime_text:
            target = f"{end}%" if end is not None else "Full"
            rows.append(("clock", f"{target} in {runtime_text}"))

    if limit is not None:
        rows.append(("shield-check", limit))

    return rows


def battery_tooltip(percent, status, runtime_text=None, end=None, start=None):
    """Hover words for the battery, one line: level and state, with the time left on
    battery (or to full, or to the charge limit, while charging). percent is None
    when unreadable; end and start are the charge limit's thresholds
    (read_charge_limit). The popover has the rest."""

    level = "Battery level unknown" if percent is None else f"Battery {percent}%"
    state, _limit = battery_state(percent, status, end, start)

    if status == "Discharging":
        return f"{level}, {runtime_text} left" if runtime_text else f"{level}, discharging"

    if status == "Charging" and runtime_text:
        return state + (f" in {runtime_text}" if end is not None else f", full in {runtime_text}")

    return state


def get_cpu_temperature():
    for hwmon in Path("/sys/class/hwmon").glob("hwmon*"):
        name = read_path(hwmon / "name")

        if name != "coretemp":
            continue

        for label_path in hwmon.glob("temp*_label"):
            label = read_path(label_path)

            if label and label.lower().startswith("package"):
                input_path = Path(
                    str(label_path).replace(
                        "_label",
                        "_input"
                    )
                )

                value = read_path(input_path)

                try:
                    return int(value) / 1000
                except (TypeError, ValueError):
                    pass

        for input_path in hwmon.glob("temp*_input"):
            value = read_path(input_path)

            try:
                return int(value) / 1000
            except (TypeError, ValueError):
                pass

    return None


def read_cpu_counters():
    try:
        first = Path("/proc/stat").read_text().splitlines()[0]
    except OSError:
        return None

    fields = first.split()

    if not fields or fields[0] != "cpu":
        return None

    try:
        values = [int(value) for value in fields[1:]]
    except ValueError:
        return None

    if len(values) < 5:
        return None

    idle = values[3]

    if len(values) > 4:
        idle += values[4]

    total = sum(values)

    return total, idle


def get_memory_usage():
    values = {}

    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if ":" not in line:
                continue

            key, value = line.split(":", 1)

            if key not in ("MemTotal", "MemAvailable"):
                continue

            parts = value.strip().split()

            if parts:
                values[key] = int(parts[0]) * 1024

    except (OSError, ValueError):
        return None

    total = values.get("MemTotal")
    available = values.get("MemAvailable")

    if total is None or available is None:
        return None

    used = total - available
    gib = 1024 ** 3

    return used / gib, total / gib


def cpu_percent(previous, current):
    """Busy share of all CPUs between two read_cpu_counters() readings."""
    if previous is None or current is None:
        return None

    total_delta = current[0] - previous[0]
    idle_delta = current[1] - previous[1]

    if total_delta <= 0:
        return None

    return max(0.0, min((total_delta - idle_delta) / total_delta * 100, 100.0))


def usage_lines(cpu, memory):
    """Words for CPU and RAM; an unavailable reading is left out."""
    lines = []

    if cpu is not None:
        lines.append(f"CPU {cpu:.0f}%")

    if memory:
        used, total = memory
        lines.append(f"Memory {used:.1f} of {total:.1f} GiB")

    return lines


def usage_rows(cpu, memory):
    """The battery popover's CPU and RAM rows, as (glyph, text) like battery_rows."""
    rows = []

    if cpu is not None:
        rows.append(("microchip", f"CPU {cpu:.0f}%"))

    if memory:
        used, total = memory
        rows.append(("memory", f"Memory {used:.1f} of {total:.1f} GiB"))

    return rows


class HistoryStore:
    """Bucketed history in an SQLite database, written once per 5-minute bucket.

    Tables: `buckets` (one row per bucket and metric: sample count, coverage, avg, min,
    max) and `samples` (time, metric, value for metrics read every
    HISTORY_RAW_MIN_INTERVAL seconds or slower). Times are Unix seconds. `records` holds
    the last HISTORY_MEMORY_SECONDS as dicts for the power graph. A database error never
    stops the panel; the bucket is then kept in memory only."""

    def __init__(self, path=None, legacy=None):
        self.path = Path(path or HISTORY_DB)
        self.legacy = Path(legacy or HISTORY_FILE)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self.records = deque()
        self.current_start = None
        self.current = {metric: [] for metric in METRIC_INTERVALS}
        self.raw = []
        self.last_prune = 0
        self.db = None

        self.open()
        self.import_legacy()
        self.load()
        self.prune_if_needed()

    def open(self):
        try:
            self.db = sqlite3.connect(self.path, timeout=2)
            self.db.executescript("""
                PRAGMA journal_mode = WAL;
                PRAGMA synchronous = NORMAL;
                CREATE TABLE IF NOT EXISTS buckets (
                    start INTEGER NOT NULL,
                    metric TEXT NOT NULL,
                    duration INTEGER NOT NULL,
                    sample_count INTEGER NOT NULL,
                    coverage_seconds INTEGER NOT NULL,
                    avg REAL, min REAL, max REAL,
                    PRIMARY KEY (start, metric)
                ) WITHOUT ROWID;
                CREATE TABLE IF NOT EXISTS samples (
                    time REAL NOT NULL,
                    metric TEXT NOT NULL,
                    value REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS samples_time ON samples (time);
            """)
        except sqlite3.Error:
            self.db = None

    def write(self, sql, rows):
        if self.db is None:
            return False

        try:
            with self.db:
                self.db.executemany(sql, rows)
            return True
        except sqlite3.Error:
            return False

    def import_legacy(self):
        """Buckets from history.jsonl, once; the file is then renamed, not deleted."""
        if self.db is None or not self.legacy.exists():
            return

        rows = []

        try:
            lines = self.legacy.read_text().splitlines()
        except OSError:
            return

        for line in lines:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if record.get("schema_version") != 1:
                continue

            rows.extend(bucket_rows(record))

        if self.write(
            "INSERT OR IGNORE INTO buckets VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows
        ):
            try:
                self.legacy.rename(self.legacy.with_name(self.legacy.name + ".imported"))
            except OSError:
                pass

    def load(self):
        if self.db is None:
            return

        cutoff = time.time() - HISTORY_MEMORY_SECONDS

        try:
            rows = self.db.execute(
                "SELECT start, metric, duration, sample_count, coverage_seconds,"
                " avg, min, max FROM buckets WHERE start >= ? ORDER BY start",
                (cutoff,),
            ).fetchall()
        except sqlite3.Error:
            return

        record = None

        for start, metric, duration, count, coverage, avg, low, high in rows:
            if record is None or record["start_epoch"] != start:
                record = bucket_record(start, duration, {})
                self.records.append(record)

            record["metrics"][metric] = {
                "sample_count": count,
                "coverage_seconds": coverage,
                "avg": avg,
                "min": low,
                "max": high,
            }

    def ensure_bucket(self, now):
        bucket_start = (
            int(now)
            // HISTORY_BUCKET_SECONDS
            * HISTORY_BUCKET_SECONDS
        )

        if self.current_start is None:
            self.current_start = bucket_start
            return

        if bucket_start != self.current_start:
            self.flush()
            self.current_start = bucket_start

    def add_sample(self, metric, value, now=None):
        if metric not in self.current:
            return

        if now is None:
            now = time.time()

        self.ensure_bucket(now)

        self.current[metric].append(
            float(value)
        )

        if METRIC_INTERVALS[metric] >= HISTORY_RAW_MIN_INTERVAL:
            self.raw.append((round(now, 1), metric, round(float(value), 3)))

    def flush(self):
        if self.current_start is None:
            return

        metrics = {}

        for metric, samples in self.current.items():
            if not samples:
                continue

            interval = METRIC_INTERVALS[metric]

            metrics[metric] = {
                "sample_count": len(samples),
                "coverage_seconds": min(
                    len(samples) * interval,
                    HISTORY_BUCKET_SECONDS
                ),
                "avg": round(sum(samples) / len(samples), 3),
                "min": round(min(samples), 3),
                "max": round(max(samples), 3),
            }

        if metrics:
            record = bucket_record(
                self.current_start, HISTORY_BUCKET_SECONDS, metrics
            )
            self.records.append(record)

            if self.db is not None:
                try:
                    with self.db:
                        # A restart within a bucket writes it twice: merge the halves.
                        self.db.executemany(
                            "INSERT INTO buckets VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                            " ON CONFLICT (start, metric) DO UPDATE SET"
                            " avg = round((avg * sample_count + excluded.avg"
                            " * excluded.sample_count) / (sample_count"
                            " + excluded.sample_count), 3),"
                            " sample_count = sample_count + excluded.sample_count,"
                            " coverage_seconds = min(duration, coverage_seconds"
                            " + excluded.coverage_seconds),"
                            " min = min(min, excluded.min),"
                            " max = max(max, excluded.max)",
                            bucket_rows(record),
                        )
                        self.db.executemany(
                            "INSERT INTO samples VALUES (?, ?, ?)", self.raw
                        )
                except sqlite3.Error:
                    pass

        self.current = {metric: [] for metric in METRIC_INTERVALS}
        self.raw = []

        self.prune_if_needed()

    def prune_if_needed(self):
        now = time.time()

        if now - self.last_prune < HISTORY_PRUNE_SECONDS:
            return

        self.last_prune = now
        memory_cutoff = now - HISTORY_MEMORY_SECONDS

        while self.records and self.records[0].get("start_epoch", 0) < memory_cutoff:
            self.records.popleft()

        cutoff = now - HISTORY_RETENTION_SECONDS
        self.write("DELETE FROM buckets WHERE start < ?", [(cutoff,)])
        self.write("DELETE FROM samples WHERE time < ?", [(cutoff,)])

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None


def bucket_record(start, duration, metrics):
    """The in-memory form of one bucket (the layout history.jsonl used)."""
    return {
        "schema_version": 1,
        "start": datetime.datetime.fromtimestamp(start).astimezone().isoformat(
            timespec="seconds"
        ),
        "start_epoch": start,
        "duration_seconds": duration,
        "metrics": metrics,
    }


def bucket_rows(record):
    """Database rows (start, metric, duration, count, coverage, avg, min, max)."""
    start = record.get("start_epoch")
    duration = record.get("duration_seconds", HISTORY_BUCKET_SECONDS)

    if not isinstance(start, (int, float)):
        return []

    return [
        (
            int(start), metric, duration,
            values.get("sample_count", 0), values.get("coverage_seconds", 0),
            values.get("avg"), values.get("min"), values.get("max"),
        )
        for metric, values in record.get("metrics", {}).items()
    ]


def power_series(records, now, span, bin_seconds, current=None):
    """Battery draw in clock-aligned bins covering the last `span` seconds.

    Returns (bins, start, end, summary). Each bin is (avg, low, high) in watts,
    or None when nothing was recorded (charging, on mains power, switched off),
    so the graph breaks there rather than drawing across. The last bin is the
    one in progress. summary is (avg, peak, seconds on battery), avg and peak
    None without data. current is HistoryStore's unflushed bucket as
    (start_epoch, samples).
    """

    count = max(1, round(span / bin_seconds))
    end = (int(now) // bin_seconds + 1) * bin_seconds
    start = end - count * bin_seconds

    weighted = [0.0] * count
    covered = [0.0] * count
    lows = [None] * count
    highs = [None] * count

    def add(epoch, duration, avg, low, high, coverage):
        middle = epoch + duration / 2

        if not start <= middle < end:
            return

        index = int((middle - start) // bin_seconds)
        weighted[index] += avg * coverage
        covered[index] += coverage

        if lows[index] is None or low < lows[index]:
            lows[index] = low

        if highs[index] is None or high > highs[index]:
            highs[index] = high

    for record in records:
        epoch = record.get("start_epoch")
        data = record.get("metrics", {}).get("power_w")

        if epoch is None or not data:
            continue

        avg = data.get("avg")
        coverage = data.get("coverage_seconds", 0)

        if avg is None or coverage <= 0:
            continue

        add(
            epoch,
            record.get("duration_seconds", HISTORY_BUCKET_SECONDS),
            float(avg),
            float(data.get("min", avg)),
            float(data.get("max", avg)),
            float(coverage)
        )

    if current and current[0] is not None and current[1]:
        epoch, samples = current
        add(
            epoch,
            HISTORY_BUCKET_SECONDS,
            sum(samples) / len(samples),
            min(samples),
            max(samples),
            float(len(samples) * BATTERY_SAMPLE_SECONDS)
        )

    bins = [
        (weighted[i] / covered[i], lows[i], highs[i])
        if covered[i] > 0 else None
        for i in range(count)
    ]

    total = sum(covered)

    if total <= 0:
        return bins, start, end, (None, None, 0)

    peak = max(high for high in highs if high is not None)

    return bins, start, end, (sum(weighted) / total, peak, total)


def power_grid(start, end, every_hours):
    """Gridline (time, label) pairs between start and end, on local hours that
    are a multiple of every_hours: "14:00", or the weekday at midnight."""

    lines = []
    moment = int(start) // 900 * 900 + 900

    while moment < end:
        local = datetime.datetime.fromtimestamp(moment)

        if local.minute == 0 and local.hour % every_hours == 0:
            label = (
                local.strftime("%a")
                if every_hours == 24
                else local.strftime("%H:%M")
            )
            lines.append((moment, label))

        moment += 900

    return lines


def power_summary(summary, name):
    avg, peak, covered = summary

    if avg is None:
        return f"No battery use in the last {name}"

    return (
        f"Avg {avg:.1f} W · Peak {peak:.1f} W · "
        f"{format_coverage(covered)} on battery"
    )


def shorten(text, limit):
    text = " ".join(text.split())

    if len(text) <= limit:
        return text

    return text[:limit - 1].rstrip() + "\u2026"


def notification_tooltip(count, quiet=False):
    """Hover text for the bell, saying so while do not disturb is on."""
    if not count:
        text = "No notifications"
    else:
        text = "1 notification" if count == 1 else f"{count} notifications"

    return text + ", do not disturb on" if quiet else text


def with_mode(modes, mode, enabled):
    """Mako's mode list with mode added or removed, the others kept in order."""
    kept = [name for name in modes if name != mode]
    return kept + [mode] if enabled else kept


def task_tooltip(name, titles, limit=60):
    """Hover text for a task button: the app's name, then its window's title, or how
    many windows it has when there are several."""
    if len(titles) > 1:
        return f"{name}\n{len(titles)} windows"

    title = shorten(titles[0], limit) if titles else ""

    if not title or title.casefold() == name.casefold():
        return name

    return f"{name}\n{title}"


def task_click_action(windows, last_active_id=None):
    """What a click on an app's task button does: (verb, window) for the helper.

    The app's focused window is minimised when it is the app's only window; with
    several, the click moves focus to the next one, so a click never hides one of
    many. Otherwise the window the app last had focused (or its first) is raised.
    """

    focused = next(
        (w for w in windows if w.get("active") and not w.get("minimized")),
        None
    )

    if focused is not None:
        if len(windows) == 1:
            return "minimize", focused

        return "activate", windows[(windows.index(focused) + 1) % len(windows)]

    target = next((w for w in windows if w["id"] == last_active_id), windows[0])
    return "activate", target


def task_close_label(count):
    """The task menu's close row: "Close" for one window, "Close 3 windows" for more."""

    return "Close" if count <= 1 else f"Close {count} windows"


def clickable(widget):
    """Show the hand cursor over a widget that does something when clicked."""

    widget.set_cursor_from_name("pointer")
    return widget


def open_below_panel(button):
    """Open a panel button's popover without an arrow, clear of the panel.

    GTK anchors a popover to the button itself, so by default its arrow and top
    edge sit over the lower part of the bar. The button gets the hand cursor: on its
    inner button, so the popover keeps the normal one.
    """

    clickable(button.get_first_child())
    place_below_panel(button.get_popover())
    PANEL_MENUS.add(button)


def set_surface_cursor(widget, name):
    """Set the cursor of the surface widget is drawn on (None for the default)."""
    native = widget.get_native()
    surface = native.get_surface() if native is not None else None

    if surface is not None:
        surface.set_cursor(Gdk.Cursor.new_from_name(name, None) if name else None)


def button_widgets(button):
    """A panel button and the widgets inside it, but not its popover's."""
    yield button
    child = button.get_first_child()
    while child is not None:
        if not isinstance(child, Gtk.Popover):
            yield from button_widgets(child)
        child = child.get_next_sibling()


class PanelMenus:
    """The panel's popover buttons: one click on another panel button while a popover
    is open closes it and opens that button's popover.

    GTK closes an open popover on any press outside it and drops the press: the other
    button sees neither the press nor the release. It does see the pointer enter and
    leave, so the button under the pointer when the popover closes is the one clicked.
    Escape closes for good. Pointing alone opens nothing.
    """

    def __init__(self, later=None):
        # later(seconds, callback): runs callback once, after seconds.
        self.later = later or (lambda seconds, callback: GLib.timeout_add(
            round(seconds * 1000), lambda: callback() and False))
        self.open = None      # the button whose popover is showing
        self.pointer = None   # the panel button under the pointer
        self.escaping = False
        self.muted = []       # widgets whose tooltips are off while the popover is open
        self.cursor_queued = False

    def add(self, button):
        popover = button.get_popover()
        popover.connect("show", lambda _popover: self.shown(button))
        popover.connect("hide", lambda _popover: self.hidden(button))

        # Only a popover with the keyboard (the Wi-Fi one) sees Escape.
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self.on_key)
        popover.add_controller(keys)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda *_args: self.entered(button))
        motion.connect("leave", lambda *_args: self.left(button))
        button.add_controller(motion)

    def on_key(self, _controller, keyval, _keycode, _state):
        self.escaping = keyval == Gdk.KEY_Escape
        return False

    def entered(self, button):
        self.pointer = button
        self.on_panel_motion()

    def left(self, button):
        if self.pointer is button:
            self.pointer = None
            self.on_panel_motion()

    def watch(self, window):
        """Keep the cursor right over the panel while a popover is open."""
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self.on_panel_motion)
        motion.connect("motion", self.on_panel_motion)
        window.add_controller(motion)

    def on_panel_motion(self, *_args):
        # While a popover holds the pointer, the cursor shown is the popover surface's
        # and GTK changes it only over the popover: over the panel it would stay the
        # arrow (or a hand from the last row). A panel button opens with one click.
        # Over empty panel space only the buttons' leave arrives, no motion. Known
        # gap: moving from inside the popover straight to empty panel space keeps the
        # last cursor until the pointer reaches a button (GTK ignores ours there).
        # GTK sets its own after this handler, so this runs once it is done.
        if self.open is not None and not self.cursor_queued:
            self.cursor_queued = True
            GLib.idle_add(self.update_cursor)

    def update_cursor(self):
        self.cursor_queued = False

        if self.open is not None:
            set_surface_cursor(self.open.get_popover(),
                               "pointer" if self.pointer is not None else "default")

        return False

    def shown(self, button):
        self.open = button

        # The button's own tooltip would cover its popover: a click cancels it, but
        # GTK dropped the click that swapped. It comes back when the popover closes.
        self.muted = [widget for widget in button_widgets(button) if widget.get_has_tooltip()]
        for widget in self.muted:
            widget.set_has_tooltip(False)

    def hidden(self, button):
        if self.open is button:
            self.open = None

        for widget in self.muted:
            widget.set_has_tooltip(True)
        self.muted = []

        target, escaping = self.pointer, self.escaping
        self.escaping = False

        if not escaping and target is not None and target is not button:
            self.later(SWITCH_DELAY_SECONDS, lambda: self.switch(target))

    def switch(self, target):
        """Open target's popover, unless something else opened or the pointer left."""
        if self.open is None and self.pointer is target:
            target.popup()


PANEL_MENUS = PanelMenus()


def place_below_panel(popover):
    """Show a popover without an arrow, POPOVER_GAP below the panel. The offset is
    measured from the popover's parent each time it opens, so it follows font and
    margin changes and a popover moved to another parent."""

    popover.set_has_arrow(False)

    def on_show(_popover):
        button = popover.get_parent()
        root = button.get_root()
        found, bounds = button.compute_bounds(root)

        if not found:
            return

        below = root.get_height() - (
            bounds.get_y() + bounds.get_height()
        )

        popover.set_offset(0, round(below) + POPOVER_GAP)

    popover.connect("show", on_show)

    # The compositor slides a popover that would cross the screen edge until it
    # touches the edge. A side margin on the card (the popover's "contents" node)
    # counts as part of the popup, so the card stops POPOVER_GAP short of it.
    contents = popover.get_first_child()
    contents.set_margin_start(POPOVER_GAP)
    contents.set_margin_end(POPOVER_GAP)


def panel_row(library, glyph, title, detail=None, trailing=None):
    """A popover row: glyph, a title over an optional detail line, a trailing glyph."""

    row = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        spacing=8
    )

    row.add_css_class("panel-row")

    holder, icon, backdrop = layered_glyph("panel-row-icon")
    set_layered_glyph(library, icon, backdrop, glyph)
    row.append(holder)

    text = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=1
    )

    text.set_hexpand(True)
    text.set_valign(Gtk.Align.CENTER)

    summary = Gtk.Label(label=title)
    summary.set_xalign(0)
    summary.set_ellipsize(Pango.EllipsizeMode.END)
    summary.add_css_class("notification-summary")
    text.append(summary)

    if detail:
        body = Gtk.Label(label=detail)
        body.set_xalign(0)
        body.add_css_class("notification-body")
        text.append(body)

    row.append(text)

    if trailing:
        mark = glyph_widget("panel-row-mark")

        if library.set_glyph(mark, trailing):
            row.append(mark)

    return row


class NotificationCenter(Gtk.MenuButton):
    """Bell, unread count, and the per-notification close control Mako lacks.

    Mako renders a banner as a single layout with no per-region hit testing, so
    a close button cannot live on the banner itself. The same notifications are
    listed here instead, each with its own dismiss control.

    Mako keeps retired banners in a history buffer it offers no way to clear, so
    a row that is closed here is recorded as acknowledged and filtered out. The
    acknowledged set is pruned against what Mako still reports, so it stays the
    size of the history buffer rather than growing for the session's lifetime.

    The do not disturb switch sets Mako's do-not-disturb mode, which hides pop-ups
    (all but critical ones) while they still arrive and are listed here. The mode
    lives in Mako, so it is read back on every refresh: a Tinybar restart or a
    `makoctl mode` change shows truly, and a new session (a new Mako) starts with it off.
    """

    def __init__(self, library):
        super().__init__()

        self.library = library
        self.proxy = None
        self.entries = []
        self.acknowledged = set()
        self.last_count = None
        self.last_quiet = None
        self.updating_switch = False

        self.set_has_frame(False)
        self.add_css_class("notification-button")
        self.add_css_class("panel-menu")

        face = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4
        )

        self.icon = glyph_widget("status-icon")

        # Hidden while zero: an empty label still takes the box spacing and
        # leaves a gap to the right of the bell.
        self.count = Gtk.Label()
        self.count.set_visible(False)

        face.append(self.icon)
        face.append(self.count)

        self.set_child(face)

        self.list = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4
        )

        scroller = Gtk.ScrolledWindow()

        scroller.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC
        )

        scroller.set_propagate_natural_height(True)
        scroller.set_max_content_height(NOTIFICATION_LIST_HEIGHT)
        scroller.set_child(self.list)

        # Hidden when empty; otherwise it keeps a scrollbar's minimum height.
        self.scroller = scroller

        self.empty = Gtk.Label(label="No notifications")
        self.empty.add_css_class("notification-empty")

        self.clear = clickable(Gtk.Button(label="Clear all"))
        self.clear.add_css_class("notification-clear")
        self.clear.connect("clicked", self.on_clear_clicked)

        header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8
        )

        header.add_css_class("network-header")

        words = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=1
        )

        words.set_hexpand(True)

        title = Gtk.Label(label="Do not disturb")
        title.set_xalign(0)
        title.add_css_class("notification-summary")

        detail = Gtk.Label(label="Hides pop-ups; urgent ones still show")
        detail.set_xalign(0)
        detail.add_css_class("notification-body")

        words.append(title)
        words.append(detail)

        self.switch = clickable(Gtk.Switch())
        self.switch.set_valign(Gtk.Align.CENTER)
        self.switch.connect("state-set", self.on_switch_set)

        header.append(words)
        header.append(self.switch)

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6
        )

        content.add_css_class("notification-popover")
        content.append(header)
        content.append(self.empty)
        content.append(scroller)
        content.append(self.clear)

        popover = Gtk.Popover()
        popover.set_child(content)
        popover.connect("show", self.on_popover_shown)

        self.set_popover(popover)
        open_below_panel(self)

        self.show_bell()
        self.icon.add_css_class("icon-only")

    # ---------- Mako ----------

    def call(self, method, parameters=None):
        if self.proxy is None:
            self.proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.DO_NOT_AUTO_START,
                None,
                MAKO_NAME,
                MAKO_PATH,
                MAKO_INTERFACE,
                None
            )

        return self.proxy.call_sync(
            method,
            parameters,
            Gio.DBusCallFlags.NONE,
            MAKO_TIMEOUT_MS,
            None
        )

    def read_notifications(self):
        found = OrderedDict()

        for method in ("ListNotifications", "ListHistory"):
            for record in self.call(method).unpack()[0]:
                identifier = record.get("id")

                if identifier is None or identifier in found:
                    continue

                found[identifier] = {
                    "id": identifier,
                    "live": method == "ListNotifications",
                    "app": record.get("app-name", ""),
                    "summary": record.get("summary", ""),
                    "body": record.get("body", "")
                }

        return sorted(
            found.values(),
            key=lambda entry: entry["id"],
            reverse=True
        )

    def read_modes(self):
        return list(self.call("ListModes").unpack()[0])

    def set_quiet(self, enabled):
        modes = with_mode(self.read_modes(), DO_NOT_DISTURB_MODE, enabled)
        self.call("SetModes", GLib.Variant("(as)", (modes,)))

    def dismiss(self, entry):
        # History rows no longer exist for Mako; acknowledging is the whole job.
        if not entry["live"]:
            return

        self.call(
            "DismissNotifications",
            GLib.Variant(
                "(a{sv})",
                ({"id": GLib.Variant("u", entry["id"])},)
            )
        )

    # ---------- panel ----------

    def refresh(self):
        try:
            found = self.read_notifications()

        except GLib.Error:
            # Mako may be absent or restarting; keep the last known count.
            return True

        try:
            quiet = DO_NOT_DISTURB_MODE in self.read_modes()
            self.switch.set_sensitive(True)

        except GLib.Error:
            # A Mako without modes: the switch could not do anything.
            quiet = False
            self.switch.set_sensitive(False)

        known = {entry["id"] for entry in found}
        self.acknowledged &= known

        self.entries = [
            entry for entry in found
            if entry["id"] not in self.acknowledged
        ]

        count = len(self.entries)

        quiet_changed = quiet != self.last_quiet

        if quiet_changed:
            self.last_quiet = quiet
            self.show_bell()
            self.updating_switch = True
            self.switch.set_active(quiet)
            self.updating_switch = False

        if quiet_changed or count != self.last_count:
            self.last_count = count
            self.count.set_text(str(count) if count else "")
            self.count.set_visible(bool(count))

            if count:
                self.icon.remove_css_class("icon-only")
            else:
                self.icon.add_css_class("icon-only")

            label = notification_tooltip(count, quiet)

            self.set_tooltip_text(label)

            self.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [label]
            )

        if self.get_popover().get_visible():
            self.rebuild_list()

        return True

    def rebuild_list(self):
        child = self.list.get_first_child()

        while child is not None:
            following = child.get_next_sibling()
            self.list.remove(child)
            child = following

        for entry in self.entries:
            self.list.append(self.build_row(entry))

        self.empty.set_visible(not self.entries)
        self.scroller.set_visible(bool(self.entries))
        self.clear.set_visible(bool(self.entries))

    def build_row(self, entry):
        row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8
        )

        row.add_css_class("notification-row")

        text = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=1
        )

        text.set_hexpand(True)

        summary = Gtk.Label(
            label=shorten(
                entry["summary"] or entry["app"] or "Notification",
                NOTIFICATION_SUMMARY_CHARS
            )
        )

        summary.set_xalign(0)
        summary.add_css_class("notification-summary")
        text.append(summary)

        if entry["body"]:
            body = Gtk.Label(
                label=shorten(
                    entry["body"],
                    NOTIFICATION_BODY_CHARS
                )
            )

            body.set_xalign(0)
            body.add_css_class("notification-body")
            text.append(body)

        close = clickable(Gtk.Button())
        close.set_has_frame(False)
        close.add_css_class("notification-close")
        close.set_valign(Gtk.Align.START)
        close.set_tooltip_text("Dismiss this notification")

        glyph = glyph_widget()

        if not self.library.set_glyph(glyph, "xmark"):
            glyph = Gtk.Label()
            glyph.set_text("\u00d7")
            glyph.set_visible(True)

        close.set_child(glyph)

        close.connect(
            "clicked",
            self.on_close_clicked,
            entry
        )

        row.append(text)
        row.append(close)

        return row

    def show_bell(self):
        """The bell, or a crossed-out bell while do not disturb is on. Without one in
        the theme, the plain bell is dimmed instead (the do-not-disturb class)."""
        quiet = bool(self.last_quiet)
        crossed = quiet and any(
            self.library.set_glyph(self.icon, name)
            for name in ("bell-slash", "notifications-disabled")
        )

        if not crossed:
            self.library.set_glyph(self.icon, "bell")

        if quiet and not crossed:
            self.add_css_class("do-not-disturb")
        else:
            self.remove_css_class("do-not-disturb")

    def on_switch_set(self, _switch, enabled):
        if self.updating_switch:
            return False

        try:
            self.set_quiet(enabled)

        except GLib.Error as error:
            print(f"tinybar: could not set do not disturb: {error}", flush=True)
            # Put the switch back to what Mako has.
            self.last_quiet = None

        GLib.idle_add(self.refresh_once)
        return False

    def refresh_once(self):
        self.refresh()
        return False

    def on_popover_shown(self, _popover):
        self.refresh()
        self.rebuild_list()

    def on_close_clicked(self, _button, entry):
        try:
            self.dismiss(entry)

        except GLib.Error:
            pass  # Already gone; acknowledging still clears it from the list.

        self.acknowledged.add(entry["id"])
        self.refresh()
        self.rebuild_list()

    def on_clear_clicked(self, _button):
        try:
            self.call(
                "DismissNotifications",
                GLib.Variant(
                    "(a{sv})",
                    ({"all": GLib.Variant("b", True)},)
                )
            )

        except GLib.Error:
            pass  # History-only rows still clear through the acknowledged set.

        self.acknowledged |= {
            entry["id"] for entry in self.entries
        }

        self.refresh()
        self.rebuild_list()
        self.get_popover().popdown()


def decode_ssid(raw):
    try:
        return bytes(raw).decode("utf-8", errors="replace")
    except (TypeError, ValueError):
        return ""


def describe_frequency(mhz):
    if not mhz:
        return None

    if mhz >= 5925:
        return "6 GHz"

    if mhz >= 5000:
        return "5 GHz"

    return "2.4 GHz"


def visible_networks(access_points, current_ssid=None):
    """One entry per SSID, strongest first, without hidden or current networks.

    Access points sharing an SSID are one network to the user; the strongest
    one stands for it, and it counts as secured if any of them is.
    """

    networks = {}

    for point in access_points:
        ssid = point["ssid"]

        if not ssid or ssid == current_ssid:
            continue

        known = networks.get(ssid)

        if known is None:
            networks[ssid] = dict(point)
            continue

        known["secured"] = known["secured"] or point["secured"]

        if point["strength"] > known["strength"]:
            secured = known["secured"]
            known.update(point)
            known["secured"] = secured

    return sorted(
        networks.values(),
        key=lambda network: (-network["strength"], network["ssid"].casefold())
    )


def network_tooltip(state):
    """Hover text for the network icon, in the Wi-Fi menu's words, from the state
    NetworkMenu.read_state returns (None when NetworkManager could not be asked). It
    names the connection the icon shows: Wi-Fi first, then a cable."""

    if state is None:
        return "Network: status unavailable"

    wifi = state["wifi"]

    if wifi:
        words = f"Wi-Fi: {wifi['ssid'] or 'hidden network'}, {wifi['strength']}% signal"
    elif state["wifi_connected"]:
        words = "Wi-Fi: connected"
    elif state["wired"]:
        words = "Wired: connected"
    else:
        words = None

    if words:
        if state.get("portal"):
            words += ", sign-in needed"

        return words

    if not state["wifi_device"]:
        return "Wi-Fi: no Wi-Fi device"

    if not state["hardware_enabled"]:
        return "Wi-Fi: off by the hardware switch"

    if not state["enabled"]:
        return "Wi-Fi: off"

    return "Wi-Fi: not connected"


def portal_url(check_uri):
    """The page that leads to a captive portal's sign-in: NetworkManager's own
    connectivity-check address (ConnectivityCheckUri), over plain http. The portal
    intercepts that request and redirects it to its sign-in page; that is how
    NetworkManager noticed it. No third-party site is involved, and the address is one
    the computer already contacts. None when there is no usable address."""

    scheme, separator, rest = (check_uri or "").partition("://")

    if not separator or scheme.lower() not in ("http", "https") or not rest:
        return None

    # A portal cannot answer an https request without a certificate warning.
    return f"http://{rest}"


def portal_name(state):
    """The connection a captive portal sits on, for the notification."""

    wifi = state["wifi"]

    if wifi and wifi["ssid"]:
        return wifi["ssid"]

    if state["wifi_connected"] or not state["wired"]:
        return "The Wi-Fi network"

    return "The wired network"


def portal_notice(state):
    """Summary and body of the notification sent once when a network asks to sign
    in, from a NetworkMenu.read_state result with "portal" set."""

    return (
        "Sign-in needed",
        f"{portal_name(state)} asks you to sign in before it connects to the "
        "internet. Choose Sign in to the network in the Wi-Fi menu."
    )


def wifi_security(flags, wpa_flags, rsn_flags):
    """How an access point is secured: "open", "owe" (encrypted, no password), "psk"
    (WPA/WPA2 password, also WPA3 transition networks), "sae" (WPA3-only password),
    "enterprise" (802.1X login) or "wep"."""

    key_mgmt = wpa_flags | rsn_flags

    if key_mgmt & (NM_AP_SEC_KEY_MGMT_802_1X | NM_AP_SEC_KEY_MGMT_EAP_SUITE_B_192):
        return "enterprise"

    if key_mgmt & NM_AP_SEC_KEY_MGMT_PSK:
        return "psk"

    if key_mgmt & NM_AP_SEC_KEY_MGMT_SAE:
        return "sae"

    if key_mgmt & (NM_AP_SEC_KEY_MGMT_OWE | NM_AP_SEC_KEY_MGMT_OWE_TM):
        return "owe"

    if flags & NM_AP_FLAGS_PRIVACY:
        return "wep"

    return "open"


def needs_password(security):
    return security in ("psk", "sae")


def wifi_settings(security, password=None):
    """Settings for a new connection to a network NetworkManager can see; it fills in
    the rest from the access point. None when the panel cannot set this kind up."""

    if security == "open":
        return {}

    if security == "owe":
        return {"802-11-wireless-security": {"key-mgmt": "owe"}}

    if security == "psk":
        return {"802-11-wireless-security": {"key-mgmt": "wpa-psk", "psk": password}}

    if security == "sae":
        return {"802-11-wireless-security": {"key-mgmt": "sae", "psk": password}}

    return None


def password_problem(security, password):
    """Why a password cannot be right before trying it, or None."""

    if not password:
        return "Enter the password"

    if security == "psk" and len(password) < 8:
        return "Wi-Fi passwords are at least 8 characters"

    if security == "psk" and len(password) > 63 and not (
        len(password) == 64 and all(c in "0123456789abcdefABCDEF" for c in password)
    ):
        return "Too long for a Wi-Fi password"

    return None


def connect_failure(reason):
    """Words for why NetworkManager gave up on a connection (its state reason)."""

    if reason in (NM_ACTIVE_REASON_NO_SECRETS, NM_ACTIVE_REASON_LOGIN_FAILED):
        return "Wrong password"

    if reason == NM_ACTIVE_REASON_CONNECT_TIMEOUT:
        return "The network did not answer"

    return "Could not connect"


def device_failure(reason):
    """Words for why the Wi-Fi device gave up joining (its state reason)."""

    if reason == NM_DEVICE_REASON_NO_SECRETS:
        return "Wrong password"

    if reason == NM_DEVICE_REASON_SSID_NOT_FOUND:
        return "The network is out of range"

    return "Could not connect"


def as_settings_variant(settings):
    """{"group": {"key": str}} as NetworkManager's a{sa{sv}}."""

    return {
        group: {key: GLib.Variant("s", value) for key, value in values.items()}
        for group, values in settings.items()
    }


def clear_box(box):
    child = box.get_first_child()

    while child is not None:
        following = child.get_next_sibling()
        box.remove(child)
        child = following


class WifiControl:
    """What the Wi-Fi popover asks NetworkManager to do, apart from any widgets, so
    the VM test (tests/vm/wifi-check) can drive the same calls.

    Every change is asynchronous and ends with on_done(ok, message). A new network is
    added in memory only and written to disk once it has connected, so a mistyped
    password is never saved.
    """

    def __init__(self, bus):
        self.bus = bus

    def call(self, path, interface, method, parameters, reply_type, on_reply):
        """Call a NetworkManager method; on_reply(result or None, error text or None)."""

        def finished(bus, result):
            try:
                value = bus.call_finish(result)
            except GLib.Error as error:
                on_reply(None, error.message)
                return
            on_reply(value.unpack() if value is not None else None, None)

        self.bus.call(
            NM_NAME, path, interface, method, parameters,
            GLib.VariantType.new(reply_type) if reply_type else None,
            Gio.DBusCallFlags.NONE, NM_ACTION_TIMEOUT_MS, None, finished
        )

    def saved_networks(self):
        """{ssid: connection path} for saved Wi-Fi connections. Blocking; quick, and
        only run when the popover opens or after a change."""

        paths = self.bus.call_sync(
            NM_NAME, NM_SETTINGS_PATH, NM_SETTINGS, "ListConnections", None,
            GLib.VariantType.new("(ao)"), Gio.DBusCallFlags.NONE, NM_TIMEOUT_MS, None
        ).unpack()[0]

        saved = {}

        for path in paths:
            try:
                settings = self.bus.call_sync(
                    NM_NAME, path, NM_CONNECTION, "GetSettings", None,
                    GLib.VariantType.new("(a{sa{sv}})"), Gio.DBusCallFlags.NONE,
                    NM_TIMEOUT_MS, None
                ).unpack()[0]
            except GLib.Error:
                continue  # Removed between the two calls.

            wireless = settings.get("802-11-wireless")

            if settings.get("connection", {}).get("type") != "802-11-wireless" or not wireless:
                continue

            ssid = decode_ssid(wireless.get("ssid", b""))

            if ssid:
                saved.setdefault(ssid, path)

        return saved

    def connect(self, device, point_path, saved_path=None, settings=None,
                replaces=None, on_done=None):
        """Join a network: a saved connection (saved_path), or a new one from settings
        (wifi_settings()). replaces is a saved connection to delete once the new one
        works (the old password was wrong)."""

        on_done = on_done or (lambda ok, message: None)

        if settings is None:
            self.call(
                NM_PATH, NM_NAME, "ActivateConnection",
                GLib.Variant("(ooo)", (saved_path, device, point_path or "/")),
                "(o)",
                lambda result, error: self.watch(
                    device, result and result[0], None, None, error, on_done
                )
            )
            return

        self.call(
            NM_PATH, NM_NAME, "AddAndActivateConnection2",
            GLib.Variant("(a{sa{sv}}ooa{sv})", (
                as_settings_variant(settings), device, point_path or "/",
                {"persist": GLib.Variant("s", "memory")}
            )),
            "(ooa{sv})",
            lambda result, error: self.watch(
                device, result and result[1], result and result[0], replaces, error, on_done
            )
        )

    def watch(self, device, active, added, replaces, error, on_done):
        """Follow an activation to its end: connected, failed or timed out. The device
        says why a join failed (a rejected password shows only there); the active
        connection says when it has finished."""

        if error or not active:
            print(f"tinybar: joining failed: {error}", flush=True)
            on_done(False, "Could not connect")
            return

        watch = {"done": False, "signals": [], "timeout": None}

        def finish(ok, message):
            if watch["done"]:
                return
            watch["done"] = True
            for signal_id in watch["signals"]:
                self.bus.signal_unsubscribe(signal_id)
            if watch["timeout"]:
                GLib.source_remove(watch["timeout"])

            if ok and added:
                self.call(added, NM_CONNECTION, "Save", None, None,
                          lambda _result, _error: None)
            if ok and replaces and replaces != added:
                self.call(replaces, NM_CONNECTION, "Delete", None, None,
                          lambda _result, _error: None)
            if not ok and added:
                self.call(added, NM_CONNECTION, "Delete", None, None,
                          lambda _result, _error: None)

            on_done(ok, message)

        def on_state(_bus, _sender, _path, _interface, _signal, parameters):
            state, reason = parameters.unpack()
            if state == NM_ACTIVE_STATE_ACTIVATED:
                finish(True, None)
            elif state == NM_ACTIVE_STATE_DEACTIVATED:
                finish(False, connect_failure(reason))

        def on_device_state(_bus, _sender, _path, _interface, _signal, parameters):
            new_state, _old_state, reason = parameters.unpack()
            if new_state == NM_DEVICE_STATE_FAILED:
                finish(False, device_failure(reason))

        def on_timeout():
            watch["timeout"] = None
            self.call(NM_PATH, NM_NAME, "DeactivateConnection",
                      GLib.Variant("(o)", (active,)), None,
                      lambda _result, _error: None)
            finish(False, "The network did not answer")
            return GLib.SOURCE_REMOVE

        watch["signals"] = [
            self.bus.signal_subscribe(
                NM_NAME, NM_ACTIVE, "StateChanged", active, None,
                Gio.DBusSignalFlags.NONE, on_state
            ),
            self.bus.signal_subscribe(
                NM_NAME, NM_DEVICE, "StateChanged", device, None,
                Gio.DBusSignalFlags.NONE, on_device_state
            ),
        ]
        watch["timeout"] = GLib.timeout_add_seconds(NM_CONNECT_SECONDS, on_timeout)

        # It may have finished before the subscription started.
        def on_current(result, error):
            if error:
                finish(False, "Could not connect")
            elif result[0] == NM_ACTIVE_STATE_ACTIVATED:
                finish(True, None)

        self.call(active, "org.freedesktop.DBus.Properties", "Get",
                  GLib.Variant("(ss)", (NM_ACTIVE, "State")), "(v)", on_current)

    def disconnect(self, device, on_done):
        self.call(device, NM_DEVICE, "Disconnect", None, None,
                  lambda _result, error: on_done(not error, error and "Could not disconnect"))

    def forget(self, connection, on_done):
        self.call(connection, NM_CONNECTION, "Delete", None, None,
                  lambda _result, error: on_done(not error, error and "Could not forget it"))

    def set_enabled(self, enabled, on_done):
        self.call(
            NM_PATH, "org.freedesktop.DBus.Properties", "Set",
            GLib.Variant("(ssv)", (NM_NAME, "WirelessEnabled", GLib.Variant("b", enabled))),
            None,
            lambda _result, error: on_done(not error, error and "Could not switch Wi-Fi")
        )


def on_mains_power():
    """True when a mains supply is online, or there is no battery to save."""
    supplies = Path("/sys/class/power_supply")
    batteries = 0
    for supply in supplies.glob("*"):
        kind = read_path(supply / "type")
        if kind == "Mains" and read_path(supply / "online") == "1":
            return True
        if kind == "Battery":
            batteries += 1
    return batteries == 0


def idle_hide_order(windows, focus_order, keep):
    """The windows idle hide minimises, bottom of the stack first: those never focused,
    then by when they last had focus. Dialogs follow their parent; windows already
    minimised and app IDs in keep are left alone."""
    rank = {window_id: position for position, window_id in enumerate(focus_order)}
    chosen = [
        window for window in windows
        if not window.get("parent")
        and not window.get("minimized")
        and str(window.get("app_id", "")).casefold() not in keep
        and str(window.get("app_id", "")).casefold() not in {i.casefold() for i in TINYBAR_APP_IDS}
    ]
    return sorted(chosen, key=lambda window: rank.get(window["id"], -1))


def tailscale_view(state, error=None):
    """Icon, tooltip and click action ("up", "down" or None) for a BackendState.
    state is None when tailscaled could not be asked (not installed or not running)."""
    if state == "Running":
        view = ("tailscale", "Tailscale: connected (click to turn off)", "down")
    elif state == "Stopped":
        view = ("tailscale-slash", "Tailscale: off (click to turn on)", "up")
    elif state == "Starting":
        view = ("tailscale-slash", "Tailscale: connecting… (click to turn off)", "down")
    elif state == "NeedsLogin":
        view = ("tailscale-slash", "Tailscale: signed out; sign in with `sudo tailscale up`", None)
    elif state == "NeedsMachineAuth":
        view = ("tailscale-slash", "Tailscale: waiting for an admin to approve this device", None)
    elif state is None:
        view = ("tailscale-slash", "Tailscale: not running (is tailscaled installed and started?)", None)
    else:
        view = ("tailscale-slash", f"Tailscale: {state}", None)
    if error:
        view = (view[0], f"{view[1]}\n{error}", view[2])
    return view


def tailscale_error(stderr, timed_out=False):
    """A short reason for a failed `tailscale up`/`down`, for the tooltip."""
    if timed_out:
        return f"Not connected after {TAILSCALE_UP_SECONDS} s; Tailscale keeps trying."
    text = (stderr or "").strip()
    if "access denied" in text.casefold():
        return "Not allowed: run `sudo tailscale set --operator=$USER` once."
    return text.splitlines()[-1] if text else "The tailscale command failed."


class TailscaleButton(Gtk.Box):
    """Tailscale on/off beside Wi-Fi: `tailscale up` or `tailscale down`, which needs
    the user to be Tailscale's operator (the tooltip says how). The state is read
    with `tailscale status` every TAILSCALE_SAMPLE_SECONDS, without blocking."""

    def __init__(self, library):
        super().__init__()
        self.library = library
        self.action = None
        self.busy = False
        self.error = None
        self.error_state = None
        self.state = None
        self.timed_out = False
        self.add_css_class("panel-menu")
        self.button = clickable(Gtk.Button())
        self.button.set_has_frame(False)
        self.image = glyph_widget("status-icon")
        self.image.add_css_class("icon-only")
        self.button.set_child(self.image)
        self.button.connect("clicked", self.toggle)
        self.append(self.button)
        self.show_state(None)

    def refresh(self):
        if not self.busy:
            try:
                proc = Gio.Subprocess.new(
                    ["tailscale", "status", "--json", "--peers=false"],
                    Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
            except GLib.Error:
                self.show_state(None)
            else:
                proc.communicate_utf8_async(None, None, self.status_read)
        return True

    def status_read(self, proc, result):
        try:
            _ok, out, _err = proc.communicate_utf8_finish(result)
            state = json.loads(out).get("BackendState") if out else None
        except (GLib.Error, ValueError):
            state = None
        self.show_state(state)

    def show_state(self, state):
        if self.error and state != self.error_state:
            self.error = None
        name, tooltip, self.action = tailscale_view(state, self.error)
        self.library.set_glyph(self.image, name)
        self.button.set_tooltip_text(tooltip)
        self.update_property([Gtk.AccessibleProperty.LABEL], [tooltip.splitlines()[0]])
        self.set_opacity(1.0)
        self.state = state

    def toggle(self, _button):
        if self.busy or self.action is None:
            return
        self.busy = True
        self.set_opacity(0.4)
        self.button.set_tooltip_text("Tailscale: switching…")
        try:
            proc = Gio.Subprocess.new(["tailscale", self.action],
                                      Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_PIPE)
        except GLib.Error as error:
            self.finish(error.message)
            return
        timer = GLib.timeout_add_seconds(TAILSCALE_UP_SECONDS, self.give_up, proc)
        proc.communicate_utf8_async(None, None, self.toggled, timer)

    def give_up(self, proc):
        proc.force_exit()
        self.timed_out = True
        return False

    def toggled(self, proc, result, timer):
        timed_out, self.timed_out = self.timed_out, False
        if not timed_out:
            GLib.source_remove(timer)
        try:
            _ok, _out, err = proc.communicate_utf8_finish(result)
        except GLib.Error as error:
            err = error.message
        failed = timed_out or not proc.get_successful()
        self.finish(tailscale_error(err, timed_out) if failed else None)

    def finish(self, error):
        self.busy = False
        self.error = error
        self.error_state = self.state
        self.refresh()


class NetworkMenu(Gtk.MenuButton):
    """Wi-Fi glyph whose popover shows the current and nearby networks and joins them.

    Clicking a saved or open network connects at once; a network with a password opens
    a password field under its row. The current network can be disconnected or
    forgotten, and a switch turns Wi-Fi off. Networks the panel cannot set up (hidden,
    enterprise logins, WEP) go through "Other network…", which opens nmtui.
    NetworkManager pushes property changes over D-Bus, so nothing polls. Opening the
    popover asks for a fresh scan, and the list updates when NetworkManager reports
    the new results.
    """

    def __init__(self, library):
        super().__init__()

        self.library = library
        self.bus = None
        self.control = None
        self.signal_ids = []
        self.refresh_source = None
        self.active_access_point = None
        self.wireless_paths = []
        self.state = None
        self.saved = {}
        # The network being joined: its row shows the form below it.
        self.target = None
        self.busy = False
        self.updating_switch = False
        # The network a captive-portal notification was last sent for.
        self.portal_notified = None

        self.set_has_frame(False)
        self.add_css_class("panel-menu")

        self.indicator = StatusIndicator(
            library,
            "wifi",
            show_value=False,
            layered=True
        )

        self.set_child(self.indicator)

        header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8
        )

        header.add_css_class("network-header")

        title = Gtk.Label(label="Wi-Fi")
        title.set_xalign(0)
        title.set_hexpand(True)
        title.add_css_class("notification-summary")

        self.switch = clickable(Gtk.Switch())
        self.switch.set_valign(Gtk.Align.CENTER)
        self.switch.connect("state-set", self.on_switch_set)

        header.append(title)
        header.append(self.switch)

        self.current = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4
        )

        self.actions = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )

        self.actions.set_halign(Gtk.Align.END)
        self.disconnect_button = self.action_button("Disconnect", self.on_disconnect)
        self.forget_button = self.action_button("Forget", self.on_forget)
        self.actions.append(self.disconnect_button)
        self.actions.append(self.forget_button)

        # Shown while a captive portal (hotel or airport sign-in page) is in the way.
        sign_in = clickable(Gtk.Button())
        sign_in.set_has_frame(False)
        sign_in.add_css_class("network-row")
        sign_in.set_child(
            panel_row(library, "key", "Sign in to the network",
                      "Opens its sign-in page in the browser")
        )
        sign_in.connect("clicked", self.on_sign_in_clicked)
        sign_in.set_visible(False)
        self.sign_in = sign_in

        self.heading = Gtk.Label(label="Available networks")
        self.heading.set_xalign(0)
        self.heading.add_css_class("panel-heading")

        self.available = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4
        )

        scroller = Gtk.ScrolledWindow()

        scroller.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC
        )

        scroller.set_propagate_natural_height(True)
        scroller.set_max_content_height(NETWORK_LIST_HEIGHT)
        scroller.set_child(self.available)
        self.scroller = scroller

        self.none = Gtk.Label(label="No other networks found")
        self.none.add_css_class("notification-empty")

        # The join form, moved under whichever row is being joined.
        self.form = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4
        )

        self.form.add_css_class("network-form")

        entry_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )

        self.password = Gtk.PasswordEntry()
        self.password.set_show_peek_icon(True)
        self.password.set_hexpand(True)
        self.password.set_property("placeholder-text", "Password")
        self.password.connect("activate", self.on_join_clicked)

        self.join_button = self.action_button("Connect", self.on_join_clicked)

        entry_row.append(self.password)
        entry_row.append(self.join_button)
        self.entry_row = entry_row

        self.status = Gtk.Label()
        self.status.set_xalign(0)
        self.status.set_wrap(True)
        self.status.add_css_class("notification-body")

        self.form.append(entry_row)
        self.form.append(self.status)

        other = clickable(Gtk.Button())
        other.set_has_frame(False)
        other.add_css_class("network-row")
        other.set_child(
            panel_row(library, "gear", "Other network…", "Hidden or work networks, in nmtui")
        )
        other.connect("clicked", self.on_other_clicked)
        self.other = other

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6
        )

        content.add_css_class("notification-popover")
        content.append(header)
        content.append(self.current)
        content.append(self.sign_in)
        content.append(self.actions)
        content.append(self.heading)
        content.append(self.none)
        content.append(scroller)
        content.append(other)

        popover = Gtk.Popover()
        popover.set_child(content)
        popover.connect("show", self.on_popover_shown)
        popover.connect("hide", self.on_popover_hidden)

        self.set_popover(popover)
        open_below_panel(self)

    def action_button(self, label, handler):
        button = clickable(Gtk.Button(label=label))
        button.add_css_class("network-action")
        button.connect("clicked", handler)
        return button

    # ---------- NetworkManager ----------

    def setup(self):
        try:
            self.bus = Gio.bus_get_sync(
                Gio.BusType.SYSTEM,
                None
            )

        except GLib.Error:
            self.indicator.set_text("WIFI ?", tooltip=network_tooltip(None))
            return

        self.control = WifiControl(self.bus)

        # Access points report strength changes; those matter only for the
        # connected one, or while the list is open (filtered in on_signal).
        for interface in (
            NM_NAME,
            NM_DEVICE,
            NM_WIRELESS,
            NM_ACCESS_POINT
        ):
            self.signal_ids.append(
                self.bus.signal_subscribe(
                    NM_NAME,
                    "org.freedesktop.DBus.Properties",
                    "PropertiesChanged",
                    None,
                    interface,
                    Gio.DBusSignalFlags.NONE,
                    self.on_signal
                )
            )

        self.refresh()

    def on_signal(self, _bus, _sender, path, _interface, _signal, parameters):
        changed = parameters.get_child_value(0).get_string()

        if (
            changed == NM_ACCESS_POINT
            and path != self.active_access_point
            and not self.get_popover().get_visible()
        ):
            return

        # NetworkManager sends bursts of changes; coalesce them.
        if self.refresh_source is None:
            self.refresh_source = GLib.timeout_add(
                100,
                self.refresh_after_event
            )

    def refresh_after_event(self):
        self.refresh_source = None
        self.refresh()

        return False

    def properties(self, path, interface):
        result = self.bus.call_sync(
            NM_NAME,
            path,
            "org.freedesktop.DBus.Properties",
            "GetAll",
            GLib.Variant("(s)", (interface,)),
            GLib.VariantType.new("(a{sv})"),
            Gio.DBusCallFlags.NONE,
            NM_TIMEOUT_MS,
            None
        )

        return result.unpack()[0]

    def access_point(self, path):
        values = self.properties(path, NM_ACCESS_POINT)
        security = wifi_security(
            values.get("Flags", 0),
            values.get("WpaFlags", 0),
            values.get("RsnFlags", 0)
        )

        return {
            "path": path,
            "ssid": decode_ssid(values.get("Ssid", b"")),
            "strength": int(values.get("Strength", 0)),
            "frequency": int(values.get("Frequency", 0)),
            "security": security,
            "secured": security not in ("open", "owe"),
        }

    def address(self, device):
        path = device.get("Ip4Config", "/")

        if path == "/":
            return None

        try:
            data = self.properties(path, NM_IP4_CONFIG).get("AddressData", [])

        except GLib.Error:
            return None

        for entry in data:
            if entry.get("address"):
                return entry["address"]

        return None

    def read_state(self, with_nearby):
        devices = self.bus.call_sync(
            NM_NAME,
            NM_PATH,
            NM_NAME,
            "GetDevices",
            None,
            GLib.VariantType.new("(ao)"),
            Gio.DBusCallFlags.NONE,
            NM_TIMEOUT_MS,
            None
        ).unpack()[0]

        manager = self.properties(NM_PATH, NM_NAME)

        state = {
            "enabled": bool(manager.get("WirelessEnabled", True)),
            "hardware_enabled": bool(manager.get("WirelessHardwareEnabled", True)),
            "wifi_device": None,
            "wifi": None,
            "wifi_connected": False,
            "wired": None,
            "nearby": [],
            # The sign-in page to open while a captive portal is in the way.
            "portal": portal_url(manager.get("ConnectivityCheckUri", ""))
            if manager.get("Connectivity") == NM_CONNECTIVITY_PORTAL else None,
        }

        wireless_paths = []
        active_access_point = None

        for path in devices:
            device = self.properties(path, NM_DEVICE)
            kind = device.get("DeviceType")
            activated = device.get("State") == NM_DEVICE_STATE_ACTIVATED

            if kind == NM_DEVICE_TYPE_ETHERNET and activated:
                state["wired"] = {"address": self.address(device)}
                continue

            if kind != NM_DEVICE_TYPE_WIFI:
                continue

            if state["wifi_device"] is None:
                state["wifi_device"] = path

            wireless_paths.append(path)
            wireless = self.properties(path, NM_WIRELESS)

            if activated and state["wifi"] is None:
                state["wifi_connected"] = True
                state["wifi_device"] = path
                point_path = wireless.get("ActiveAccessPoint", "/")

                if point_path != "/":
                    try:
                        point = self.access_point(point_path)

                    except GLib.Error:
                        point = None  # Vanished between the two calls.

                    if point is not None:
                        point["address"] = self.address(device)
                        state["wifi"] = point
                        active_access_point = point_path

            if not with_nearby:
                continue

            for point_path in wireless.get("AccessPoints", []):
                try:
                    point = self.access_point(point_path)

                except GLib.Error:
                    continue  # Access points come and go with every scan.

                point["device"] = path
                state["nearby"].append(point)

        self.wireless_paths = wireless_paths
        self.active_access_point = active_access_point

        return state

    def request_scan(self):
        for path in self.wireless_paths:
            self.bus.call(
                NM_NAME,
                path,
                NM_WIRELESS,
                "RequestScan",
                GLib.Variant("(a{sv})", ({},)),
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None,
                self.on_scan_requested
            )

    def on_scan_requested(self, bus, result):
        try:
            bus.call_finish(result)

        except GLib.Error:
            pass  # Refused while a scan is running or too recent; the list stays current.

    def read_saved(self):
        try:
            self.saved = self.control.saved_networks()

        except GLib.Error:
            self.saved = {}

    # ---------- panel ----------

    def refresh(self):
        if self.bus is None:
            return

        listing = self.get_popover().get_visible()

        try:
            state = self.read_state(listing)

        except GLib.Error:
            self.indicator.set_text("WIFI ?", tooltip=network_tooltip(None))
            return

        self.state = state
        wifi = state["wifi"]
        # The first argument picks the icon (IconLibrary.status_name); the words are
        # network_tooltip's.
        words = network_tooltip(state)

        if wifi and wifi["ssid"]:
            self.indicator.set_text(
                f"WIFI {wifi['ssid']}",
                icon=signal_glyph(wifi["strength"]),
                tooltip=words
            )

        elif state["wifi_connected"]:
            self.indicator.set_text("WIFI ON", tooltip=words)

        elif state["wired"]:
            # Online by cable (desktops, VMs, docks): show that rather than Wi-Fi off.
            self.indicator.set_text("WIRED Connected", icon="network-wired", tooltip=words)

        else:
            self.indicator.set_text("WIFI OFF", tooltip=words)

        self.notice_portal(state)

        if listing:
            self.rebuild(state)

    def notice_portal(self, state):
        """Notify once when a network asks to sign in; again only after it has
        stopped asking, or for another network."""

        if not state["portal"]:
            self.portal_notified = None
            return

        name = portal_name(state)

        if name == self.portal_notified:
            return

        self.portal_notified = name
        summary, body = portal_notice(state)
        wired = state["wired"] and not state["wifi_connected"]
        # Mako binds the default action (opening the page) to a middle click.
        post_notification(summary, body, "network-wired" if wired else "network-wireless",
                          on_click=self.open_portal)

    def rebuild(self, state):
        clear_box(self.current)

        self.updating_switch = True
        self.switch.set_active(state["enabled"])
        self.switch.set_sensitive(state["hardware_enabled"] and state["wifi_device"] is not None)
        self.updating_switch = False

        wifi = state["wifi"]

        if wifi:
            detail = ["Sign-in needed" if state["portal"] else "Connected",
                      f"{wifi['strength']}%"]
            band = describe_frequency(wifi["frequency"])

            if band:
                detail.append(band)

            if wifi["address"]:
                detail.append(wifi["address"])

            self.current.append(
                panel_row(
                    self.library,
                    signal_glyph(wifi["strength"]),
                    wifi["ssid"] or "Hidden network",
                    " · ".join(detail),
                    "lock" if wifi["secured"] else None
                )
            )

        elif state["wifi_connected"]:
            self.current.append(
                panel_row(self.library, "wifi", "Wi-Fi",
                          "Sign-in needed" if state["portal"] else "Connected")
            )

        elif not state["wifi_device"]:
            self.current.append(
                panel_row(self.library, "wifi-slash", "Wi-Fi", "No Wi-Fi device")
            )

        elif not state["hardware_enabled"]:
            self.current.append(
                panel_row(self.library, "wifi-slash", "Wi-Fi", "Off by the hardware switch")
            )

        elif not state["enabled"]:
            self.current.append(
                panel_row(self.library, "wifi-slash", "Wi-Fi", "Off")
            )

        else:
            self.current.append(
                panel_row(self.library, "wifi-slash", "Wi-Fi", "Not connected")
            )

        if state["wired"]:
            portal_here = state["portal"] and not state["wifi_connected"]
            detail = "Sign-in needed" if portal_here else "Connected"

            if state["wired"]["address"]:
                detail += f" · {state['wired']['address']}"

            self.current.append(
                panel_row(self.library, "network-wired", "Wired", detail)
            )

        self.sign_in.set_visible(bool(state["portal"]))
        self.actions.set_visible(state["wifi_connected"])
        self.forget_button.set_visible(bool(wifi and wifi["ssid"] in self.saved))
        self.disconnect_button.set_sensitive(not self.busy)
        self.forget_button.set_sensitive(not self.busy)

        listing = state["enabled"] and state["wifi_device"] is not None
        self.heading.set_visible(listing)
        self.other.set_visible(listing)

        # Leave the list alone while a password is typed or a join runs, so rows do
        # not jump under the pointer or take the field away.
        if self.target is not None:
            return

        clear_box(self.available)

        networks = visible_networks(
            state["nearby"],
            wifi["ssid"] if wifi else None
        ) if listing else []

        for network in networks:
            self.available.append(self.network_button(network))

        self.none.set_visible(listing and not networks)
        self.scroller.set_visible(bool(networks))

    def network_button(self, network):
        detail = [f"{network['strength']}%"]
        band = describe_frequency(network["frequency"])

        if band:
            detail.append(band)

        if network["ssid"] in self.saved:
            detail.append("Saved")

        button = clickable(Gtk.Button())
        button.set_has_frame(False)
        button.add_css_class("network-row")
        button.set_child(
            panel_row(
                self.library,
                signal_glyph(network["strength"]),
                network["ssid"],
                " · ".join(detail),
                "lock" if network["secured"] else None
            )
        )
        button.connect("clicked", self.on_network_clicked, network)
        return button

    # ---------- joining ----------

    def show_form(self, row, asking, message=None):
        """Show the form under row: the password field if asking, and a message."""

        parent = self.form.get_parent()

        if parent is not None:
            parent.remove(self.form)

        self.available.insert_child_after(self.form, row)
        self.entry_row.set_visible(asking)
        self.status.set_label(message or "")
        self.status.set_visible(bool(message))
        self.password.set_sensitive(not self.busy)
        self.join_button.set_sensitive(not self.busy)

        if asking and not self.busy:
            self.password.grab_focus()

    def close_form(self):
        parent = self.form.get_parent()

        if parent is not None:
            # Let the field lose focus before it goes, or GTK warns of a lost focus-out.
            root = self.form.get_root()

            if root is not None and self.password.get_focus_child() is not None:
                root.set_focus(None)

            parent.remove(self.form)

        self.password.set_text("")
        self.target = None

    def on_network_clicked(self, row, network):
        if self.busy:
            return

        if self.target is not None and self.target["network"]["ssid"] == network["ssid"]:
            # A second click folds the form away; the rows stay put under the pointer.
            self.close_form()
            return

        self.close_form()
        self.target = {"network": network, "row": row, "replaces": None, "joining": False}
        saved = self.saved.get(network["ssid"])

        if saved:
            self.join(saved_path=saved)

        elif wifi_settings(network["security"], "") is None:
            self.show_form(row, False, "This network needs Other network… below.")

        elif needs_password(network["security"]):
            self.show_form(row, True)

        else:
            self.join(settings=wifi_settings(network["security"]))

    def on_join_clicked(self, _widget):
        if self.busy or self.target is None:
            return

        network = self.target["network"]
        password = self.password.get_text()
        problem = password_problem(network["security"], password)

        if problem:
            self.show_form(self.target["row"], True, problem)
            return

        self.join(settings=wifi_settings(network["security"], password))

    def join(self, saved_path=None, settings=None):
        # The result goes to this target only, whatever the form shows by then.
        target = self.target
        network = target["network"]
        self.busy = True
        target["joining"] = True
        self.show_form(
            target["row"],
            settings is not None and needs_password(network["security"]),
            f"Connecting to {network['ssid']}…"
        )

        self.control.connect(
            network.get("device") or self.state["wifi_device"],
            network["path"],
            saved_path=saved_path,
            settings=settings,
            replaces=target["replaces"],
            on_done=lambda ok, message: self.on_joined(ok, message, saved_path, target)
        )

    def on_joined(self, ok, message, saved_path, target):
        target["joining"] = False

        if target is not self.target:
            # Its form was closed by the Wi-Fi switch, whose own call clears busy,
            # and another join may run now: this result is stale, so leave all alone.
            return

        self.busy = False

        if ok:
            self.close_form()
            self.read_saved()
            self.refresh()
            return

        if not self.get_popover().get_visible():
            # It failed after the popover closed: that shows in the panel glyph, and
            # the next opening starts from a fresh list.
            self.close_form()
            return

        network = self.target["network"]

        if saved_path and message == "Wrong password":
            # The saved password no longer works: ask, and replace it once it does.
            self.target["replaces"] = saved_path
            message = "The saved password did not work. Enter the new one."

        # A saved network that failed for another reason (out of range) asks for nothing.
        asking = needs_password(network["security"]) and (
            saved_path is None or self.target["replaces"] is not None
        )

        self.show_form(self.target["row"], asking, message)

    # ---------- current network and switch ----------

    def on_disconnect(self, _button):
        if self.busy or not self.state or not self.state["wifi_device"]:
            return

        self.busy = True
        self.control.disconnect(self.state["wifi_device"], self.on_action_done)

    def on_forget(self, _button):
        wifi = self.state and self.state["wifi"]
        connection = wifi and self.saved.get(wifi["ssid"])

        if self.busy or not connection:
            return

        self.busy = True
        self.control.forget(connection, self.on_action_done)

    def on_action_done(self, ok, message):
        self.busy = False

        if not ok:
            print(f"tinybar: {message}", flush=True)

        self.read_saved()
        self.refresh()

    def on_switch_set(self, _switch, enabled):
        if self.updating_switch or self.control is None:
            return False

        self.close_form()
        self.control.set_enabled(enabled, self.on_action_done)
        return False

    def on_other_clicked(self, _button):
        self.popdown()

        try:
            Gio.Subprocess.new(OTHER_NETWORK_COMMAND, Gio.SubprocessFlags.NONE)
        except GLib.Error as error:
            print(f"tinybar: could not open nmtui: {error}", flush=True)

    # ---------- captive portal ----------

    def on_sign_in_clicked(self, _button):
        self.popdown()
        self.open_portal()

    def open_portal(self):
        """Open the sign-in page (portal_url) in the default browser."""

        url = self.state and self.state["portal"]

        if not url:
            return

        # Without Tinybar's own preload and GTK settings: Firefox crashes at start
        # with gtk4-layer-shell preloaded.
        context = Gio.AppLaunchContext()

        for name in ("LD_PRELOAD", "GSK_RENDERER", "GTK_A11Y"):
            context.unsetenv(name)

        try:
            Gio.AppInfo.launch_default_for_uri(url, context)
        except GLib.Error as error:
            print(f"tinybar: could not open the sign-in page: {error.message}", flush=True)

    def check_connectivity(self):
        """Ask NetworkManager to check again now, so a finished sign-in shows without
        waiting for its next scheduled check. Refused outside the session; it then
        checks on its own schedule."""

        self.bus.call(
            NM_NAME, NM_PATH, NM_NAME, "CheckConnectivity", None,
            GLib.VariantType.new("(u)"), Gio.DBusCallFlags.NONE, NM_ACTION_TIMEOUT_MS,
            None, self.on_connectivity_checked
        )

    def on_connectivity_checked(self, bus, result):
        try:
            bus.call_finish(result)
        except GLib.Error:
            pass  # A change arrives as PropertiesChanged anyway.

    # ---------- popover ----------

    def on_popover_shown(self, _popover):
        # The password field needs the keyboard; the panel takes it only while open.
        Gtk4LayerShell.set_keyboard_mode(
            self.get_root(),
            Gtk4LayerShell.KeyboardMode.ON_DEMAND
        )

        if self.control is not None:
            self.read_saved()

        self.refresh()
        self.request_scan()

        if self.state and self.state["portal"]:
            self.check_connectivity()

    def on_popover_hidden(self, _popover):
        Gtk4LayerShell.set_keyboard_mode(
            self.get_root(),
            Gtk4LayerShell.KeyboardMode.NONE
        )

        # A join in progress carries on, still busy, and keeps its form and the list
        # as they are, so opening the popover again shows it connecting; its result
        # comes back to it alone (on_joined). Any other form closes.
        if self.target is None or not self.target["joining"]:
            self.close_form()


def apply_bluez_signal(objects, member, path, args):
    """Bring a GetManagedObjects tree ({path: {interface: {name: value}}}) up to date
    with one InterfacesAdded, InterfacesRemoved or PropertiesChanged signal."""
    if member == "InterfacesAdded":
        for interface, values in args[1].items():
            objects.setdefault(args[0], {}).setdefault(interface, {}).update(values)
    elif member == "InterfacesRemoved":
        for interface in args[1]:
            objects.get(args[0], {}).pop(interface, None)
        if not objects.get(args[0], True):
            del objects[args[0]]
    elif member == "PropertiesChanged" and args[0] in objects.get(path, {}):
        objects[path][args[0]].update(args[1])
        for name in args[2]:
            objects[path][args[0]].pop(name, None)


def bluetooth_adapter(objects):
    """The first adapter's path, or None."""
    return min((path for path, interfaces in objects.items() if BLUEZ_ADAPTER in interfaces),
               default=None)


def bluetooth_devices(objects, adapter):
    """(paired, nearby) devices of an adapter: paired ones connected first, then by name;
    nearby ones are unpaired devices that sent a name (an address means nothing to the
    person), by name, so rows stay put while signal strengths change."""
    paired, nearby = [], []
    for path, interfaces in objects.items():
        values = interfaces.get(BLUEZ_DEVICE)
        if values is None or values.get("Adapter") != adapter:
            continue
        device = {
            "path": path,
            "name": values.get("Alias") or values.get("Address", ""),
            "icon": values.get("Icon") or "bluetooth",
            "paired": bool(values.get("Paired")),
            "connected": bool(values.get("Connected")),
            "battery": interfaces.get(BLUEZ_BATTERY, {}).get("Percentage"),
        }
        if device["paired"]:
            paired.append(device)
        elif values.get("Name"):
            nearby.append(device)
    paired.sort(key=lambda device: (not device["connected"], device["name"].casefold()))
    nearby.sort(key=lambda device: device["name"].casefold())
    return paired, nearby


def bluetooth_view(adapter, paired):
    """Panel icon and tooltip for an adapter's properties (None: no adapter)."""
    if adapter is None:
        return "bluetooth-slash", "Bluetooth: no adapter"
    if not adapter.get("Powered"):
        return "bluetooth-slash", "Bluetooth: off"
    connected = [device["name"] for device in paired if device["connected"]]
    if len(connected) == 1:
        return "bluetooth", f"Bluetooth: connected to {connected[0]}"
    if connected:
        return "bluetooth", f"Bluetooth: {len(connected)} devices connected"
    return "bluetooth", "Bluetooth: on"


def bluetooth_detail(device):
    detail = ["Connected" if device["connected"] else "Not connected"]
    if device["battery"] is not None:
        detail.append(f"{device['battery']}% battery")
    return " · ".join(detail)


def bluetooth_failure(error, fallback):
    """Words for a failed BlueZ call, from its D-Bus error name."""
    return BLUEZ_FAILURES.get((error or "").rsplit(".", 1)[-1], fallback)


def bluetooth_lists_to_fill(target):
    """The device lists ("paired", "nearby") the popover may refill now, given the open
    form's target (None: no form). The form's own list stays as it is, and so does the
    paired list above the nearby one, so rows never jump under the pointer; the nearby
    list below a paired device's form still fills while searching."""
    if target is None:
        return {"paired", "nearby"}
    return {"nearby"} if target["device"]["paired"] else set()


def pairing_prompt(kind, name, code=None):
    """What the popover says when pairing needs the person: "confirm" a number the
    device shows, "display" one to type on it, or "pin" (refused; bluetoothctl asks)."""
    if isinstance(code, int):
        code = f"{code:06d}"
    if kind == "confirm":
        return f"Does {name} show {code}?"
    if kind == "display":
        return f"Type {code} on {name}, then press Enter"
    return f"{name} needs a PIN. Use Other device… below."


class BluetoothControl:
    """What the Bluetooth popover asks BlueZ to do, apart from any widgets, so the VM
    test (tests/vm/bluetooth-check) can drive the same calls.

    BlueZ's object tree is kept in self.objects from its ObjectManager and
    PropertiesChanged signals, and on_change() runs after each change; nothing polls.
    It is also the pairing agent: on_request(kind, device, code, answer) passes on what
    pairing asks, kind being "confirm" (answer(True) if the device shows code),
    "authorize" (pair without a number), "display" (code to type on the device) or
    "pin" (a PIN to type here, already refused); answer is None for the last two.
    Every action is asynchronous and ends with on_done(ok, message).
    """

    def __init__(self, bus, on_change, on_request):
        self.bus = bus
        self.on_change = on_change
        self.on_request = on_request
        self.objects = {}
        agent = Gio.DBusNodeInfo.new_for_xml(BLUEZ_AGENT_XML).interfaces[0]
        bus.register_object_with_closures2(BLUEZ_AGENT_PATH, agent, self.on_agent_call,
                                           None, None)
        for interface, member in (
            ("org.freedesktop.DBus.ObjectManager", "InterfacesAdded"),
            ("org.freedesktop.DBus.ObjectManager", "InterfacesRemoved"),
            ("org.freedesktop.DBus.Properties", "PropertiesChanged"),
        ):
            bus.signal_subscribe(BLUEZ_NAME, interface, member, None, None,
                                 Gio.DBusSignalFlags.NONE, self.on_signal)
        # BlueZ starts with the first adapter (bluetooth.target) and may restart.
        Gio.bus_watch_name_on_connection(bus, BLUEZ_NAME, Gio.BusNameWatcherFlags.NONE,
                                         self.on_appeared, self.on_vanished)

    def call(self, path, interface, method, parameters, on_reply, reply_type=None,
             timeout=NM_ACTION_TIMEOUT_MS):
        """Call a BlueZ method; on_reply(error name or None, result or None)."""

        def finished(bus, result):
            try:
                value = bus.call_finish(result)
            except GLib.Error as error:
                print(f"tinybar: bluetooth {method}: {error.message}", flush=True)
                on_reply(Gio.DBusError.get_remote_error(error) or error.message, None)
                return
            on_reply(None, value.unpack() if value is not None else None)

        self.bus.call(
            BLUEZ_NAME, path, interface, method, parameters,
            GLib.VariantType.new(reply_type) if reply_type else None,
            Gio.DBusCallFlags.NONE, timeout, None, finished
        )

    def on_appeared(self, _bus, _name, _owner):
        self.call("/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects", None,
                  self.on_objects, "(a{oa{sa{sv}}})")
        # BlueZ forgets the agent when it restarts; it handles calls in order.
        self.call("/org/bluez", BLUEZ_AGENT_MANAGER, "RegisterAgent",
                  GLib.Variant("(os)", (BLUEZ_AGENT_PATH, "DisplayYesNo")), lambda *_: None)
        self.call("/org/bluez", BLUEZ_AGENT_MANAGER, "RequestDefaultAgent",
                  GLib.Variant("(o)", (BLUEZ_AGENT_PATH,)), lambda *_: None)

    def on_objects(self, _error, result):
        self.objects = result[0] if result else {}
        self.on_change()

    def on_vanished(self, _bus, _name):
        self.objects = {}
        self.on_change()

    def on_signal(self, _bus, _sender, path, _interface, member, parameters):
        args = parameters.unpack()
        apply_bluez_signal(self.objects, member, path, args)
        if member != "PropertiesChanged" or args[2] or not set(args[1]) <= BLUEZ_QUIET:
            self.on_change()

    def on_agent_call(self, _bus, _sender, _path, _interface, method, parameters, invocation):
        args = parameters.unpack()
        answered = []

        def answer(yes):
            if not answered:  # once: the popover closing also says no
                answered.append(yes)
                if yes:
                    invocation.return_value(None)
                else:
                    invocation.return_dbus_error("org.bluez.Error.Rejected", "Refused")

        if method in ("RequestConfirmation", "RequestAuthorization"):
            kind = "confirm" if method == "RequestConfirmation" else "authorize"
            self.on_request(kind, args[0], args[1] if len(args) > 1 else None, answer)
        elif method in ("DisplayPasskey", "DisplayPinCode"):
            self.on_request("display", args[0], args[1], None)
            invocation.return_value(None)
        elif method in ("RequestPinCode", "RequestPasskey"):
            answer(False)
            self.on_request("pin", args[0], None, None)
        elif method == "AuthorizeService":
            # A paired device that is not trusted, connecting by itself.
            device = self.objects.get(args[0], {}).get(BLUEZ_DEVICE, {})
            answer(bool(device.get("Paired")))
        else:  # Release, Cancel
            invocation.return_value(None)

    def done(self, on_done, fallback):
        """An on_reply that ends an action with on_done(ok, words for the failure)."""
        return lambda error, _result: on_done(not error,
                                              error and bluetooth_failure(error, fallback))

    def set_property(self, path, interface, name, value, on_reply):
        self.call(path, "org.freedesktop.DBus.Properties", "Set",
                  GLib.Variant("(ssv)", (interface, name, value)), on_reply)

    def set_powered(self, adapter, powered, on_done):
        self.set_property(adapter, BLUEZ_ADAPTER, "Powered", GLib.Variant("b", powered),
                          self.done(on_done, "Could not switch Bluetooth"))

    def search(self, adapter, on):
        """Start or stop looking for nearby devices; BlueZ stops by itself if Tinybar
        quits."""
        self.call(adapter, BLUEZ_ADAPTER, "StartDiscovery" if on else "StopDiscovery", None,
                  lambda *_: None)

    def pair(self, device, on_done):
        """Pair a nearby device, trust it (so it may reconnect by itself) and connect."""

        def paired(error, _result):
            if error and not error.endswith(".AlreadyExists"):
                on_done(False, bluetooth_failure(error, "Could not pair"))
                return
            self.set_property(device, BLUEZ_DEVICE, "Trusted", GLib.Variant("b", True),
                              lambda *_: self.connect(device, on_done))

        self.call(device, BLUEZ_DEVICE, "Pair", None, paired, timeout=BLUEZ_PAIR_TIMEOUT_MS)

    def connect(self, device, on_done):
        self.call(device, BLUEZ_DEVICE, "Connect", None,
                  self.done(on_done, "Could not connect"), timeout=BLUEZ_CONNECT_TIMEOUT_MS)

    def disconnect(self, device, on_done):
        self.call(device, BLUEZ_DEVICE, "Disconnect", None,
                  self.done(on_done, "Could not disconnect"))

    def forget(self, adapter, device, on_done):
        self.call(adapter, BLUEZ_ADAPTER, "RemoveDevice", GLib.Variant("(o)", (device,)),
                  self.done(on_done, "Could not forget it"))


class BluetoothMenu(Gtk.MenuButton):
    """Bluetooth glyph whose popover lists paired devices and pairs new ones.

    The switch powers the adapter. Clicking a paired device opens Connect or Disconnect
    and Forget under its row. "Pair new device" searches while the popover stays open
    and lists nearby devices by name; clicking one pairs, trusts and connects it, and a
    question such as "Does <device> show 123456?" comes up under its row. Devices that
    want a PIN typed go through "Other device…", which opens bluetoothctl. BlueZ
    reports every change over D-Bus (BluetoothControl), so nothing polls.
    """

    def __init__(self, library):
        super().__init__()
        self.library = library
        self.control = None
        self.adapter = None
        self.refresh_source = None
        self.searching = False
        # The device whose row shows the form: {"device", "row", "answer", "pin"}.
        self.target = None
        self.busy = False
        self.updating_switch = False

        self.set_has_frame(False)
        self.add_css_class("panel-menu")
        self.set_visible(BLUETOOTH is True)
        self.indicator = StatusIndicator(library, "bluetooth", show_value=False)
        self.set_child(self.indicator)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.add_css_class("network-header")
        title = Gtk.Label(label="Bluetooth")
        title.set_xalign(0)
        title.set_hexpand(True)
        title.add_css_class("notification-summary")
        self.switch = clickable(Gtk.Switch())
        self.switch.set_valign(Gtk.Align.CENTER)
        self.switch.connect("state-set", self.on_switch_set)
        header.append(title)
        header.append(self.switch)

        # "Off" or "No Bluetooth adapter", in place of the lists.
        self.state_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.heading = self.text_label("Devices", "panel-heading")
        self.none = self.text_label("No paired devices", "notification-empty")
        self.paired = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.pair_new = self.row_button(
            panel_row(library, "plus", "Pair new device", "Searches while this menu is open"),
            self.on_pair_new_clicked
        )
        self.nearby_heading = self.text_label("Nearby devices", "panel-heading")
        self.searching_label = self.text_label("Searching…", "notification-empty")
        self.nearby = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_propagate_natural_height(True)
        self.scroller.set_max_content_height(NETWORK_LIST_HEIGHT)
        self.scroller.set_child(self.nearby)

        self.other = self.row_button(
            panel_row(library, "gear", "Other device…",
                      "Devices that want a PIN, in bluetoothctl"),
            self.on_other_clicked
        )

        # The form, moved under whichever row is being acted on.
        self.form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.form.add_css_class("network-form")
        self.status = self.text_label("", "notification-body")
        self.status.set_wrap(True)
        self.buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.buttons.set_halign(Gtk.Align.END)
        self.connect_button = self.action_button("Connect", self.on_connect_clicked)
        self.forget_button = self.action_button("Forget", self.on_forget_clicked)
        self.yes_button = self.action_button("Yes", self.on_answer, True)
        self.no_button = self.action_button("No", self.on_answer, False)
        self.form.append(self.status)
        self.form.append(self.buttons)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content.add_css_class("notification-popover")
        for widget in (header, self.state_row, self.heading, self.none, self.paired,
                       self.pair_new, self.nearby_heading, self.searching_label,
                       self.scroller, self.other):
            content.append(widget)

        popover = Gtk.Popover()
        popover.set_child(content)
        popover.connect("show", lambda _popover: self.refresh())
        popover.connect("hide", self.on_popover_hidden)
        self.set_popover(popover)
        open_below_panel(self)

    def text_label(self, text, css_class):
        label = Gtk.Label(label=text)
        label.set_xalign(0)
        label.add_css_class(css_class)
        return label

    def action_button(self, label, handler, *args):
        button = clickable(Gtk.Button(label=label))
        button.add_css_class("network-action")
        button.connect("clicked", handler, *args)
        self.buttons.append(button)
        return button

    def row_button(self, child, handler, *args):
        button = clickable(Gtk.Button())
        button.set_has_frame(False)
        button.add_css_class("network-row")
        button.set_child(child)
        button.connect("clicked", handler, *args)
        return button

    def setup(self):
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            self.control = BluetoothControl(bus, self.on_change, self.on_request)
        except GLib.Error as error:
            print(f"tinybar: no Bluetooth: {error.message}", flush=True)
        self.refresh()

    def on_change(self):
        # BlueZ sends bursts of changes; coalesce them.
        if self.refresh_source is None:
            self.refresh_source = GLib.timeout_add(100, self.refresh_after_event)

    def refresh_after_event(self):
        self.refresh_source = None
        self.refresh()
        return False

    # ---------- panel ----------

    def refresh(self):
        objects = self.control.objects if self.control else {}
        self.adapter = bluetooth_adapter(objects)
        adapter = objects.get(self.adapter, {}).get(BLUEZ_ADAPTER)
        paired, nearby = bluetooth_devices(objects, self.adapter)
        self.set_visible(BLUETOOTH is True or adapter is not None)
        icon, text = bluetooth_view(adapter, paired)
        self.indicator.set_text(text, icon=icon)
        if self.get_popover().get_visible():
            self.rebuild(adapter, paired, nearby)

    def rebuild(self, adapter, paired, nearby):
        powered = bool(adapter and adapter.get("Powered"))
        self.searching = self.searching and powered
        if not powered:
            self.close_form()  # BlueZ ends whatever it was doing for the form.

        self.updating_switch = True
        self.switch.set_active(powered)
        self.switch.set_sensitive(adapter is not None)
        self.updating_switch = False

        clear_box(self.state_row)
        if adapter is None:
            detail = "No Bluetooth adapter"
        elif adapter.get("PowerState") == "off-blocked":
            detail = "Blocked by a wireless switch or rfkill"
        else:
            detail = "Off"
        self.state_row.append(panel_row(self.library, "bluetooth-slash", "Bluetooth", detail))
        self.state_row.set_visible(not powered)
        for widget in (self.heading, self.other):
            widget.set_visible(powered)
        self.pair_new.set_visible(powered and not self.searching)
        self.nearby_heading.set_visible(self.searching)

        # An open form keeps its own list and the ones above it as they are.
        refill = bluetooth_lists_to_fill(self.target)
        if "paired" in refill:
            clear_box(self.paired)
            for device in paired:
                self.paired.append(self.device_button(device))
            self.paired.set_visible(powered and bool(paired))
            self.none.set_visible(powered and not paired)
        if "nearby" not in refill:
            return

        clear_box(self.nearby)
        nearby = nearby if self.searching else []
        for device in nearby:
            self.nearby.append(self.device_button(device))
        # A short list goes without a scrollbar, whose minimum height would pad it out;
        # one-line rows are 30 px with 4 between (docs/UI-RULES.md).
        tall = len(nearby) * 34 > NETWORK_LIST_HEIGHT
        self.scroller.set_policy(Gtk.PolicyType.NEVER,
                                 Gtk.PolicyType.AUTOMATIC if tall else Gtk.PolicyType.NEVER)
        self.scroller.set_visible(bool(nearby))
        self.searching_label.set_visible(self.searching and not nearby)

    def device_button(self, device):
        glyph = device["icon"] if self.library.has(device["icon"]) else "bluetooth"
        detail = bluetooth_detail(device) if device["paired"] else None
        row = panel_row(self.library, glyph, device["name"], detail)
        return self.row_button(row, self.on_device_clicked, device)

    # ---------- devices ----------

    def show_form(self, message=None, buttons=()):
        """Show the form under the target's row: a message and some of its buttons."""
        row = self.target["row"]
        parent = self.form.get_parent()
        if parent is not None:
            parent.remove(self.form)
        row.get_parent().insert_child_after(self.form, row)
        self.status.set_label(message or "")
        self.status.set_visible(bool(message))
        self.buttons.set_visible(bool(buttons))
        for button in self.buttons:
            button.set_visible(button in buttons)

    def close_form(self):
        parent = self.form.get_parent()
        if parent is not None:
            parent.remove(self.form)
        # An action still running carries on, but its result no longer has a form to
        # show in (on_done drops it), so the next one may start.
        self.target = None
        self.busy = False

    def on_device_clicked(self, row, device):
        if self.busy:
            return
        if self.target is not None and self.target["device"]["path"] == device["path"]:
            # A second click folds the form away; the rows stay put under the pointer.
            self.close_form()
            return
        self.close_form()
        self.target = {"device": device, "row": row, "answer": None, "pin": False}
        if device["paired"]:
            self.connect_button.set_label("Disconnect" if device["connected"] else "Connect")
            self.show_form(None, (self.connect_button, self.forget_button))
            return
        self.busy = True
        self.show_form(f"Pairing with {device['name']}…")
        self.control.pair(device["path"], self.done_for(self.target))

    def on_connect_clicked(self, _button):
        if self.busy or self.target is None:
            return
        device = self.target["device"]
        self.busy = True
        if device["connected"]:
            self.show_form("Disconnecting…")
            self.control.disconnect(device["path"], self.done_for(self.target))
        else:
            self.show_form(f"Connecting to {device['name']}…")
            self.control.connect(device["path"], self.done_for(self.target))

    def on_forget_clicked(self, _button):
        if self.busy or self.target is None:
            return
        self.busy = True
        self.control.forget(self.adapter, self.target["device"]["path"],
                            self.done_for(self.target))

    def done_for(self, target):
        """The on_done of an action started from target's form."""
        return lambda ok, message: self.on_done(target, ok, message)

    def on_done(self, target, ok, message):
        if target is not self.target:
            # Its form has closed (the popover hid, or the adapter went off), and another
            # device's action may be running now; the panel glyph shows the outcome.
            return
        self.busy = False
        if ok:
            self.close_form()
            self.refresh()
            return
        device = self.target["device"]
        if self.target["pin"]:
            message = pairing_prompt("pin", device["name"])
        buttons = (self.connect_button, self.forget_button) if device["paired"] else ()
        self.show_form(message, buttons)

    def on_request(self, kind, device, code, answer):
        """A pairing question from BlueZ: shown under the row of the device being
        paired here; refused for any other device."""
        target = self.target
        if target is None or target["device"]["path"] != device:
            if answer:
                answer(False)
            return
        if kind == "authorize":
            answer(True)  # The person chose this device; there is nothing to compare.
            return
        if target["answer"]:
            target["answer"](False)  # Superseded: BlueZ asks one thing at a time.
        target["pin"] = kind == "pin"
        target["answer"] = answer
        buttons = (self.yes_button, self.no_button) if answer else ()
        self.show_form(pairing_prompt(kind, target["device"]["name"], code), buttons)

    def on_answer(self, _button, yes):
        answer = self.target and self.target["answer"]
        if answer:
            self.target["answer"] = None
            answer(yes)
            self.show_form(f"Pairing with {self.target['device']['name']}…")

    # ---------- switch and popover ----------

    def on_switch_set(self, _switch, enabled):
        if self.updating_switch or self.control is None or self.adapter is None:
            return False
        self.close_form()
        # BlueZ replies before its PropertiesChanged for Powered, which redraws the
        # popover; a refresh on that reply would flip the switch back for a moment.
        # Only a failure puts it back.
        self.control.set_powered(self.adapter, enabled,
                                 lambda ok, _message: ok or self.refresh())
        return False

    def on_pair_new_clicked(self, _button):
        if self.control is None or self.adapter is None:
            return
        if not self.busy:
            # A form with nothing running folds away; a running one stays for its result.
            self.close_form()
        self.searching = True
        self.control.search(self.adapter, True)
        self.refresh()

    def on_other_clicked(self, _button):
        self.popdown()
        try:
            Gio.Subprocess.new(OTHER_DEVICE_COMMAND, Gio.SubprocessFlags.NONE)
        except GLib.Error as error:
            print(f"tinybar: could not open bluetoothctl: {error}", flush=True)

    def on_popover_hidden(self, _popover):
        if self.searching and self.adapter:
            self.control.search(self.adapter, False)
        self.searching = False
        # A question nobody can answer now is a no; a pairing or connection already
        # running carries on, and its result shows in the panel glyph.
        if self.target and self.target["answer"]:
            self.target["answer"](False)
        self.close_form()


def with_alpha(color, alpha):
    faded = color.copy()
    faded.alpha = color.alpha * alpha
    return faded


class PowerGraph(Gtk.Widget):
    """Battery draw over time: the bin averages as a line over a faint band from
    each bin's lowest to highest reading. Drawn with GTK's own path API in the
    CSS text colour, so it needs no cairo bindings and follows the theme."""

    def __init__(self):
        super().__init__()

        self.add_css_class("power-graph")
        self.set_size_request(POWER_GRAPH_WIDTH, POWER_GRAPH_HEIGHT)

        self.bins = []
        self.start = 0
        self.end = 1
        self.grid = []
        self.top = POWER_GRAPH_MIN_W

    def plot(self, bins, start, end, grid):
        self.bins = bins
        self.start = start
        self.end = end
        self.grid = grid

        highest = max((value[0] for value in bins if value), default=0)
        steps = -(-highest * POWER_GRAPH_HEADROOM // POWER_GRAPH_STEP_W)
        self.top = max(POWER_GRAPH_MIN_W, steps * POWER_GRAPH_STEP_W)
        self.queue_draw()

    def do_snapshot(self, snapshot):
        width = self.get_width()
        height = self.get_height() - POWER_GRAPH_LABEL_HEIGHT

        if width <= 0 or height <= 0 or not self.bins:
            return

        color = self.get_color()
        span = self.end - self.start
        step = width / len(self.bins)

        def x_at(moment):
            return (moment - self.start) / span * width

        def y_at(watts):
            return height - min(watts, self.top) / self.top * height

        def text(label, x, y, alpha):
            layout = self.create_pango_layout(label)
            snapshot.save()
            snapshot.translate(Graphene.Point().init(x, y))
            snapshot.append_layout(layout, with_alpha(color, alpha))
            snapshot.restore()

        # Gridlines: half and full scale across, the view's hours or days down.
        grid = Gsk.PathBuilder.new()

        for watts in (self.top / 2, self.top):
            grid.move_to(0, y_at(watts))
            grid.line_to(width, y_at(watts))

        grid.move_to(0, height)
        grid.line_to(width, height)

        for moment, _label in self.grid:
            grid.move_to(x_at(moment), 0)
            grid.line_to(x_at(moment), height)

        snapshot.append_stroke(
            grid.to_path(),
            Gsk.Stroke.new(1),
            with_alpha(color, 0.12)
        )

        for watts in (self.top / 2, self.top):
            text(f"{watts:g} W", 3, y_at(watts) + 1, 0.55)

        for moment, label in self.grid:
            text(label, x_at(moment) + 3, height + 1, 0.55)

        # Unbroken runs of recorded bins; each is drawn on its own.
        runs = []
        run = []

        for index, value in enumerate(self.bins):
            if value is None:
                if run:
                    runs.append(run)
                run = []
                continue

            run.append(((index + 0.5) * step, value))

        if run:
            runs.append(run)

        band = Gsk.PathBuilder.new()
        line = Gsk.PathBuilder.new()
        dots = Gsk.PathBuilder.new()

        for run in runs:
            if len(run) == 1:
                x, (avg, _low, _high) = run[0]
                dots.add_circle(Graphene.Point().init(x, y_at(avg)), 1.5)
                continue

            first_x, (_avg, _low, first_high) = run[0]
            band.move_to(first_x, y_at(first_high))

            for x, (_avg, _low, high) in run[1:]:
                band.line_to(x, y_at(high))

            for x, (_avg, low, _high) in reversed(run):
                band.line_to(x, y_at(low))

            band.close()

            line.move_to(run[0][0], y_at(run[0][1][0]))

            for x, (avg, _low, _high) in run[1:]:
                line.line_to(x, y_at(avg))

        snapshot.append_fill(
            band.to_path(),
            Gsk.FillRule.WINDING,
            with_alpha(color, 0.2)
        )

        stroke = Gsk.Stroke.new(1.5)
        stroke.set_line_join(Gsk.LineJoin.ROUND)

        snapshot.append_stroke(line.to_path(), stroke, color)
        snapshot.append_fill(dots.to_path(), Gsk.FillRule.WINDING, color)


class BatteryMenu(Gtk.MenuButton):
    """Battery icon and time left. The popover lists the battery's state (the rows
    battery_rows makes: state, draw or charge rate, time left, charge limit), then
    graphs the draw over the last 3 hours, 24 hours or 7 days from Tinybar's history
    file; its arrows (or the Left and Right keys) cycle through the three and wrap
    around."""

    def __init__(self, library, history):
        super().__init__()

        self.library = library
        self.history = history
        self.view = 0
        self.status_rows = None

        self.set_has_frame(False)
        self.add_css_class("panel-menu")

        self.indicator = StatusIndicator(library, "battery")
        # The panel colours this icon by the current draw.
        self.icon = self.indicator.icon
        self.set_child(self.indicator)

        self.title = Gtk.Label()
        self.title.set_hexpand(True)
        self.title.add_css_class("power-title")

        header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4
        )

        header.append(self.arrow("chevron-left", "<", -1, "Previous range"))
        header.append(self.title)
        header.append(self.arrow("chevron-right", ">", 1, "Next range"))

        self.graph = PowerGraph()

        self.summary = Gtk.Label()
        self.summary.set_xalign(0)
        self.summary.add_css_class("notification-body")

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6
        )

        # Filled by show_status on every battery tick, open or not.
        self.status = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4
        )

        content.add_css_class("notification-popover")
        content.append(self.status)
        content.append(header)
        content.append(self.graph)
        content.append(self.summary)

        popover = Gtk.Popover()
        popover.set_child(content)
        popover.connect("show", lambda _popover: self.refresh())

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key_pressed)
        popover.add_controller(keys)

        self.set_popover(popover)
        open_below_panel(self)

    def arrow(self, glyph, fallback, direction, label):
        button = clickable(Gtk.Button())
        button.set_has_frame(False)
        button.add_css_class("power-arrow")
        button.set_tooltip_text(label)

        image = glyph_widget()

        if self.library.set_glyph(image, glyph):
            button.set_child(image)
        else:
            button.set_label(fallback)

        button.connect("clicked", lambda _button: self.cycle(direction))
        return button

    def cycle(self, direction):
        self.view = (self.view + direction) % len(POWER_VIEWS)
        self.refresh()

    def on_key_pressed(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Left:
            self.cycle(-1)
            return True

        if keyval == Gdk.KEY_Right:
            self.cycle(1)
            return True

        return False

    def set_text(self, text, **kwargs):
        self.indicator.set_text(text, **kwargs)

    def show_status(self, rows):
        """Show battery_rows' (glyph, text) list above the graph; rebuilt only when it
        changes."""

        if rows == self.status_rows:
            return

        self.status_rows = rows

        while child := self.status.get_first_child():
            self.status.remove(child)

        for glyph, text in rows:
            row = panel_row(self.library, glyph, text)
            row.add_css_class("battery-fact")
            self.status.append(row)

    def refresh(self):
        name, span, bin_seconds, every_hours = POWER_VIEWS[self.view]

        bins, start, end, summary = power_series(
            self.history.records,
            time.time(),
            span,
            bin_seconds,
            (
                self.history.current_start,
                self.history.current.get("power_w", [])
            )
        )

        self.title.set_text(f"Last {name}")
        self.graph.plot(
            bins,
            start,
            end,
            power_grid(start, end, every_hours)
        )
        self.summary.set_text(power_summary(summary, name))


def mode_action(color_scheme):
    """The system menu's mode row for the current GTK colour scheme:
    (glyph, title, mode to switch to)."""

    if color_scheme == "prefer-light":
        return ("moon", "Dark mode", "dark")

    return ("sun", "Light mode", "light")


# Walker's service runs in the background, so it is restarted to take the new icon
# theme (GTK 4 reads it only at start). It starts as in autostart.d/50-launcher.sh,
# without Tinybar's own preload and settings; the old instance must exit first, or the
# new one only hands over to it. It is matched by name: pkill -f would match this script.
MODE_SWITCH_SCRIPT = """
limde-appearance --apply --mode "$1" || exit
labwc --reconfigure
makoctl reload
pkill -x -u "$(id -u)" walker
for _ in 1 2 3 4 5 6 7 8 9 10; do
    pgrep -x -u "$(id -u)" walker >/dev/null || break
    sleep 0.2
done
env -u LD_PRELOAD -u GTK_A11Y GSK_RENDERER=cairo \\
    setsid -f walker --gapplication-service >"$HOME/.local/state/limde/walker.log" 2>&1
"""


def mode_switch_command(mode):
    """Apply the mode, let Labwc and Mako reread their generated styles, and restart
    Walker's service."""

    return ["sh", "-c", MODE_SWITCH_SCRIPT, "tinybar-mode", mode]


def interface_settings():
    """GNOME's interface settings, or None without their schema (Gio.Settings.new would
    abort the program)."""

    source = Gio.SettingsSchemaSource.get_default()

    if source and source.lookup("org.gnome.desktop.interface", True):
        return Gio.Settings.new("org.gnome.desktop.interface")

    return None


def needs_second_click(armed, key, confirm):
    """True when a click on the system menu's `key` row should ask again instead of
    acting: the row has a question (`confirm`) and is not the one already asking."""

    return bool(confirm) and armed != key


def confirms_too_soon(armed, key, armed_at, now, interval):
    """True when a click on the row already asking comes sooner than interval after
    the click that armed it: the second half of a double-click, not an answer, so it
    is ignored. Times in one unit (GLib's monotonic microseconds)."""

    return armed == key and now - armed_at < interval


def double_click_microseconds():
    """GTK's double-click time (gtk-double-click-time, in ms), in microseconds."""

    settings = Gtk.Settings.get_default()
    milliseconds = settings.get_property("gtk-double-click-time") if settings else 0

    return (milliseconds if milliseconds > 0 else DOUBLE_CLICK_MS) * 1000


def action_row():
    """A menu row that acts when clicked (the system and task menus): a glyph and a
    label in a flat button that highlights on hover. Returns (button, icon, label)."""

    button = clickable(Gtk.Button())
    button.add_css_class("system-action")

    row = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        spacing=8
    )

    icon = glyph_widget("panel-row-icon")
    label = Gtk.Label()
    label.set_xalign(0)
    label.set_hexpand(True)

    row.append(icon)
    row.append(label)
    button.set_child(row)

    return button, icon, label


class SystemMenu(Gtk.MenuButton):
    """Cog at the right end: light/dark mode, then lock and restart, with suspend, log
    out and power off behind More.

    Log out, restart and power off take a second click, so a stray click cannot end
    the session; a double-click does not count as both. Suspend needs none: swayidle
    locks the screen before sleep.
    """

    ACTIONS = (
        ("lock", "lock", "Lock", None,
         ["loginctl", "lock-session"]),
        ("suspend", "moon", "Suspend", None,
         ["systemctl", "suspend"]),
        # Labwc exports LABWC_PID to what it starts; --exit signals that process.
        ("log-out", "log-out", "Log out", "Click again to log out",
         ["labwc", "--exit"]),
        ("restart", "rotate-right", "Restart", "Click again to restart",
         ["systemctl", "reboot"]),
        ("power-off", "power-off", "Power off", "Click again to power off",
         ["systemctl", "poweroff"]),
    )

    # The power rows always shown; the rest of ACTIONS opens under More.
    SHOWN_FIRST = ("lock", "restart")

    def __init__(self, library, on_mode_changed):
        super().__init__()

        self.library = library
        self.on_mode_changed = on_mode_changed
        self.interface = interface_settings()
        self.target_mode = None
        self.armed = None
        # When the asking row was armed, in GLib monotonic microseconds.
        self.armed_at = 0
        self.disarm_source = None
        self.rows = {}

        self.set_has_frame(False)
        self.add_css_class("panel-menu")

        self.icon = glyph_widget("status-icon")
        self.set_child(self.icon)

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4
        )

        content.add_css_class("system-popover")

        if self.interface:
            content.append(self.menu_heading("Appearance"))
            self.mode_button, self.mode_icon, self.mode_label = action_row()
            self.mode_button.connect("clicked", self.on_mode_clicked)
            content.append(self.mode_button)

        content.append(self.menu_heading("Power"))

        self.more_rows = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4
        )

        for key, glyph, title, confirm, command in self.ACTIONS:
            button, icon, label = action_row()
            library.set_glyph(icon, glyph)
            label.set_label(title)
            button.connect("clicked", self.on_action_clicked, key)
            self.rows[key] = (button, label, title, confirm, command)

            if key in self.SHOWN_FIRST:
                content.append(button)
            else:
                self.more_rows.append(button)

        # More stays where it is when it opens, with the rows below it: a double-click
        # on it then lands on Less, not on a row that has just appeared under the pointer.
        self.more_button, self.more_icon, self.more_label = action_row()
        self.more_button.connect("clicked", self.on_more_clicked)
        content.append(self.more_button)
        content.append(self.more_rows)
        self.show_more(False)

        popover = Gtk.Popover()
        popover.set_child(content)
        popover.connect("show", self.on_popover_shown)
        popover.connect("hide", self.on_popover_hidden)

        self.set_popover(popover)
        open_below_panel(self)

        if self.library.set_glyph(self.icon, "gear"):
            self.icon.add_css_class("icon-only")

        self.set_tooltip_text("Settings")

    def menu_heading(self, title):
        heading = Gtk.Label(label=title)
        heading.set_xalign(0)
        heading.add_css_class("panel-heading")

        return heading

    def show_more(self, shown):
        self.more_rows.set_visible(shown)
        self.library.set_glyph(self.more_icon, "chevron-up" if shown else "chevron-down")
        self.more_label.set_label("Less" if shown else "More")

    def on_more_clicked(self, _button):
        # A row asking for its second click may be about to hide.
        self.disarm()
        self.show_more(not self.more_rows.get_visible())

    def on_popover_shown(self, _popover):
        if not self.interface:
            return

        glyph, title, self.target_mode = mode_action(
            self.interface.get_string("color-scheme")
        )

        self.library.set_glyph(self.mode_icon, glyph)
        self.mode_label.set_label(title)

    def on_popover_hidden(self, _popover):
        self.disarm()
        self.show_more(False)

    def on_mode_clicked(self, _button):
        self.popdown()
        mode = self.target_mode

        try:
            process = Gio.Subprocess.new(
                mode_switch_command(mode),
                Gio.SubprocessFlags.STDOUT_SILENCE
            )
        except GLib.Error as error:
            print(f"tinybar: mode switch failed: {error}", flush=True)
            return

        process.wait_check_async(None, self.on_mode_switched, mode)

    def on_mode_switched(self, process, result, mode):
        try:
            process.wait_check_finish(result)
        except GLib.Error as error:
            print(f"tinybar: switching to {mode} mode failed: {error}", flush=True)

        # Reload even after a partial failure: whatever was written should show.
        self.on_mode_changed()

    def on_action_clicked(self, _button, key):
        button, label, title, confirm, command = self.rows[key]
        now = GLib.get_monotonic_time()

        if confirms_too_soon(self.armed, key, self.armed_at, now, double_click_microseconds()):
            # A double-click's second half: keep asking, for a deliberate click.
            return

        if needs_second_click(self.armed, key, confirm):
            self.disarm()
            self.armed = key
            self.armed_at = now
            label.set_label(confirm)
            button.add_css_class("system-confirm")
            self.disarm_source = GLib.timeout_add_seconds(
                CONFIRM_SECONDS,
                self.on_confirm_timeout
            )
            return

        self.popdown()

        try:
            process = Gio.Subprocess.new(command, Gio.SubprocessFlags.NONE)
        except GLib.Error as error:
            print(f"tinybar: {title.lower()} failed: {error}", flush=True)
            return

        # A refusal (polkit, or no LABWC_PID) shows only in the exit status.
        process.wait_check_async(None, self.on_action_finished, title)

    def on_action_finished(self, process, result, title):
        try:
            process.wait_check_finish(result)
        except GLib.Error as error:
            print(f"tinybar: {title.lower()} failed: {error}", flush=True)

    def on_confirm_timeout(self):
        self.disarm_source = None
        self.disarm()
        return GLib.SOURCE_REMOVE

    def disarm(self):
        if self.disarm_source:
            GLib.source_remove(self.disarm_source)
            self.disarm_source = None

        if self.armed:
            button, label, title, _confirm, _command = self.rows[self.armed]
            label.set_label(title)
            button.remove_css_class("system-confirm")
            self.armed = None


def parse_volume(output):
    """(percent, muted) from `wpctl get-volume` ("Volume: 0.40 [MUTED]"), or None."""
    match = re.search(r"Volume:\s+([0-9.]+)", output or "")
    return (round(float(match.group(1)) * 100), "[MUTED]" in output) if match else None


def volume_tooltip(level, microphone=None):
    """Hover text for the speaker, from parse_volume's (percent, muted) or None. The
    default microphone, read the same way, is named only while it is muted."""
    if level is None:
        text = "Volume: unavailable"
    else:
        percent, muted = level
        text = "Volume: muted" if muted else f"Volume {percent}%"

    if microphone is not None and microphone[1]:
        text += ", microphone muted"

    return text


def brightness_percent(current, maximum):
    """The backlight's level in percent (0-100) from its sysfs brightness and
    max_brightness texts; None when they cannot be read."""
    try:
        current, maximum = int(current), int(maximum)
    except (TypeError, ValueError):
        return None
    if maximum <= 0:
        return None
    return max(0, min(round(current / maximum * 100), 100))


def brightness_command():
    """tinybar-brightness: beside this file in the source tree, else from PATH."""
    if BRIGHTNESS_COMMAND.exists():
        return str(BRIGHTNESS_COMMAND)
    return shutil.which("tinybar-brightness") or "/usr/local/bin/tinybar-brightness"


def can_set_brightness():
    """True when brightnessctl, which tinybar-brightness runs, is installed."""
    return os.access(BRIGHTNESSCTL, os.X_OK)


def brightness_change_announced(now, quiet_until, slider_sending):
    """Whether a backlight change shows the level overlay: not while the slider is
    sending, nor until quiet_until after its last change (both monotonic seconds).
    The slider shows the level itself; the keys still get the overlay."""
    return not slider_sending and now >= quiet_until


def calendar_heading(day):
    """The calendar popover's title: the date in words, "Monday, November 2, 2026"."""
    return f"{day:%A}, {day:%B} {day.day}, {day.year}"


def calendar_shows_today(year, month, day, today):
    """True while the calendar is on today (month 1-12), so Today has nothing to do."""
    return (year, month, day) == (today.year, today.month, today.day)


def brightness_tooltip(percent):
    """Hover text for the brightness icon; percent is None when unreadable."""
    return "Brightness: unavailable" if percent is None else f"Brightness {percent}%"


def new_audio_state():
    return {"sinks": {}, "sources": {}, "watched": set(), "default": None,
            "default_source": None}


def is_microphone(props):
    """True for a node that records sound: a source, but not the monitor of an output
    (which only plays back what that output plays)."""
    return (props.get("media.class") in ("Audio/Source", "Audio/Source/Virtual")
            and not str(props.get("node.name") or "").endswith(".monitor")
            and props.get("device.class") != "monitor"
            and str(props.get("stream.monitor", "")).lower() not in ("true", "1"))


def split_dump(buffer):
    """Objects in the complete batches of `pw-dump --monitor` output, and the rest. A batch
    is an indented JSON array, so a line holding only "]" ends one; bad ones are skipped."""
    *batches, rest = buffer.split(b"\n]\n")
    objects = []
    for batch in batches:
        try:
            found = json.loads(batch + b"\n]")
        except ValueError:
            continue
        objects += [item for item in found if isinstance(item, dict)] if isinstance(found, list) else []
    return objects, rest


# The "default" metadata's keys, and where apply_audio_objects keeps their node names.
AUDIO_DEFAULTS = {"default.audio.sink": "default", "default.audio.source": "default_source"}


def apply_audio_objects(audio, objects):
    """Fold pw-dump objects into audio; True if a level or the device lists may have
    changed. "sinks" and "sources" map output and microphone node ids to (node.name,
    description); "watched" holds audio devices (hardware volume is set there) and the
    "default" metadata, which pw-dump sends with only its changed entries. A removed
    object comes as its id alone."""
    changed = False
    for item in objects:
        key, kind = item.get("id"), item.get("type", "")
        props = (item.get("info") or {}).get("props") or item.get("props") or {}
        if "type" not in item:
            removed = [audio[nodes].pop(key, None) for nodes in ("sinks", "sources")]
            if removed != [None, None] or key in audio["watched"]:
                audio["watched"].discard(key)
                changed = True
        elif kind.endswith(":Node") and props.get("media.class") == "Audio/Sink":
            name = props.get("node.name")
            audio["sinks"][key] = (name, props.get("node.description") or name or f"Output {key}")
            changed = True
        elif kind.endswith(":Node") and is_microphone(props):
            name = props.get("node.name")
            audio["sources"][key] = (
                name, props.get("node.description") or name or f"Microphone {key}")
            changed = True
        elif (kind.endswith(":Device") and props.get("media.class") == "Audio/Device") or (
                kind.endswith(":Metadata") and props.get("metadata.name") == "default"):
            audio["watched"].add(key)
            changed = True
            for entry in item.get("metadata") or []:
                if entry.get("subject") == 0 and entry.get("key") in AUDIO_DEFAULTS:
                    value = entry.get("value")
                    audio[AUDIO_DEFAULTS[entry["key"]]] = (
                        value.get("name") if isinstance(value, dict) else None)
    return changed


def audio_devices(nodes, default):
    """(node id, description, is the default) for each node, by description."""
    return sorted(((key, description, name == default)
                   for key, (name, description) in nodes.items()),
                  key=lambda device: device[1].casefold())


def audio_outputs(audio):
    """The popover's outputs: (node id, description, is the default)."""
    return audio_devices(audio["sinks"], audio["default"])


def audio_inputs(audio):
    """The popover's microphones, monitors left out: (node id, description, is the default)."""
    return audio_devices(audio["sources"], audio["default_source"])


def default_source_command(name):
    """pw-metadata's command that makes the source node called name the default."""
    return [PW_METADATA, "-n", "default", "0", "default.configured.audio.source",
            json.dumps({"name": name}), "Spa:String:JSON"]


def default_microphone(audio):
    """The default microphone's node id, or None. WirePlumber's default source can be an
    output's monitor (its sink's name): wpctl's @DEFAULT_AUDIO_SOURCE@ is then the
    output itself, so the microphone controls act on node ids, never on that name."""
    for key, (name, _description) in audio["sources"].items():
        if name is not None and name == audio["default_source"]:
            return key
    return None


def audio_monitor_delay(ran_seconds, last_delay):
    """Seconds to wait before starting pw-dump again after one that ran ran_seconds:
    the base wait after one that ran longer than that (PipeWire restarted), otherwise
    twice the last wait up to the maximum, so a PipeWire that stays down for a while
    is still followed once it is back, without a tight loop meanwhile."""
    if ran_seconds > AUDIO_MONITOR_RETRY_SECONDS or not last_delay:
        return AUDIO_MONITOR_RETRY_SECONDS
    return min(last_delay * 2, AUDIO_MONITOR_RETRY_MAX_SECONDS)


def run_command(argv, then=None):
    """Run a command without blocking, in the C locale; then(output, or None if it
    failed)."""
    launcher = Gio.SubprocessLauncher.new(
        Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
    launcher.setenv("LC_ALL", "C", True)
    try:
        proc = launcher.spawnv(argv)
    except GLib.Error as error:
        print(f"tinybar: cannot run {argv[0]}: {error.message}", flush=True)
        if then:
            then(None)
        return
    proc.communicate_utf8_async(None, None, on_command_done, then)


def on_command_done(proc, result, then):
    try:
        _ok, output, _err = proc.communicate_utf8_finish(result)
    except GLib.Error:
        output = None
    if then:
        then(output if proc.get_successful() else None)


class LevelSlider(Gtk.Box):
    """A slider from minimum to 100 % and its value. show() puts a level read back into
    it; moving it calls send(percent, then) with its newest value, one change at a time
    (send calls then() when that change is done), and done() after the last."""

    def __init__(self, name, send, done, minimum=0):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.send = send
        self.done = done
        # The slider's newest value not yet sent; one change runs at a time.
        self.wanted = None
        self.sending = False
        self.updating = False
        # The level last shown or asked for: a click can report the same value twice.
        self.last = None
        self.set_hexpand(True)

        self.slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, minimum, 100, 1)
        self.slider.set_hexpand(True)
        self.slider.add_css_class("volume-slider")
        self.slider.update_property([Gtk.AccessibleProperty.LABEL], [name])
        self.slider.connect("value-changed", self.on_slider_changed)
        self.value = Gtk.Label()
        self.value.set_width_chars(4)
        self.value.set_xalign(1)
        self.value.add_css_class("notification-body")
        self.append(self.slider)
        self.append(self.value)

    def show(self, percent):
        """Show a level read back; a drag in progress keeps the slider."""
        if self.sending:
            return
        self.updating = True
        self.slider.set_value(percent)
        self.value.set_text(f"{percent}%")
        self.last = percent
        self.updating = False

    def on_slider_changed(self, slider):
        percent = round(slider.get_value())
        if self.updating or percent == self.last:
            return
        self.wanted = self.last = percent
        self.value.set_text(f"{self.wanted}%")
        if not self.sending:
            self.send_next()

    def send_next(self, _output=None):
        # A drag sends its newest value once the change before it ends.
        if self.wanted is None:
            self.sending = False
            self.done()
            return
        self.sending = True
        percent, self.wanted = self.wanted, None
        self.send(percent, self.send_next)


class LevelControls(Gtk.Box):
    """A mute toggle and a LevelSlider, for one wpctl target (the default output or
    microphone). show() puts a level read back into them; a change runs wpctl through
    run(), then done() so the owner reads the level back."""

    def __init__(self, library, target, name, glyph, run, done):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.library = library
        self.target = target
        self.name = name
        self.glyph = glyph
        self.run = run
        self.done = done
        self.updating = False

        self.mute = clickable(Gtk.ToggleButton())
        self.mute.set_has_frame(False)
        self.mute.add_css_class("volume-mute")
        self.mute_icon = glyph_widget()
        self.mute.set_child(self.mute_icon)
        self.mute.connect("toggled", self.on_mute_toggled)
        self.level = LevelSlider(name, self.send_volume, done)
        self.append(self.mute)
        self.append(self.level)

    def show(self, percent, muted):
        """Show a level read back; a drag in progress keeps the slider."""
        self.updating = True
        self.mute.set_active(muted)
        words = "Unmute" if muted else "Mute"
        self.mute.set_tooltip_text(words if self.name == "Volume" else f"{words} {self.name.lower()}")
        self.library.set_glyph(self.mute_icon, self.glyph(percent, muted))
        (self.level.slider.add_css_class if muted else self.level.slider.remove_css_class)("muted")
        self.level.show(percent)
        self.updating = False

    def send_volume(self, percent, then):
        # The same 100 % cap as the keys.
        self.run("set-volume", "-l", "1.0", self.target, f"{percent}%", then=then)

    def on_mute_toggled(self, button):
        if not self.updating:
            self.run("set-mute", self.target, "1" if button.get_active() else "0",
                     then=self.done)


class VolumeMenu(Gtk.MenuButton):
    """Speaker glyph; its popover holds the output's mute toggle, volume slider and list,
    then, when there is a microphone, the same for the default microphone.

    Every change runs wpctl, then reads the volume back into the state file the keys write
    (VOLUME_STATE), which the panel shows. A `pw-dump --monitor` child reports PipeWire's
    changes, so changes made elsewhere are read too. Only the keys show the level overlay.
    The microphone's level is kept in microphone (None without one); on_microphone() is
    called when it changes, for the panel's tooltip.
    """

    def __init__(self, library):
        super().__init__()
        self.library = library
        self.audio = new_audio_state()
        self.microphone = None
        self.on_microphone = None
        self.monitor = None
        self.monitor_buffer = b""
        self.monitor_started = 0
        # The wait before the last restart of pw-dump (see audio_monitor_delay).
        self.monitor_delay = 0
        self.refresh_source = None
        self.set_has_frame(False)
        self.add_css_class("panel-menu")
        self.indicator = StatusIndicator(library, "volume", show_value=False)
        self.set_child(self.indicator)

        self.speaker = LevelControls(library, "@DEFAULT_AUDIO_SINK@", "Volume", volume_glyph,
                                     self.wpctl, self.refresh)
        self.heading = self.section_heading("Output")
        self.outputs = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        # Its target is the default microphone's node id, set by refresh.
        self.mic = LevelControls(library, None, "Microphone", microphone_glyph,
                                 self.wpctl, self.refresh)
        self.inputs = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        # Hidden while there is no microphone. The list shows with more than one, or
        # alone when none is the default (to pick one); the controls need a default.
        self.mic_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        for widget in (self.section_heading("Microphone"), self.mic, self.inputs):
            self.mic_section.append(widget)
        self.mic_section.set_visible(False)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content.add_css_class("notification-popover")
        for widget in (self.speaker, self.heading, self.outputs, self.mic_section):
            content.append(widget)

        popover = Gtk.Popover()
        popover.set_child(content)
        popover.connect("show", self.on_popover_shown)
        self.set_popover(popover)
        open_below_panel(self)

    @staticmethod
    def section_heading(text):
        heading = Gtk.Label(label=text)
        heading.set_xalign(0)
        heading.add_css_class("panel-heading")
        return heading

    def set_text(self, text, **kwargs):
        self.indicator.set_text(text, **kwargs)

    def show_volume(self, percent, muted):
        """Show the state file's level in the popover."""
        self.speaker.show(percent, muted)

    def wpctl(self, *args, then=None):
        self.spawn([WPCTL, *args], then)

    def spawn(self, argv, then=None):
        run_command(argv, then)

    def refresh(self, _output=None):
        """Read the default output's volume into the state file, as a key would, and the
        default microphone's level (see default_microphone)."""
        self.wpctl("get-volume", "@DEFAULT_AUDIO_SINK@", then=self.write_state)
        key = default_microphone(self.audio)
        if key is None:
            self.show_microphone(None)
        else:
            self.mic.target = str(key)
            self.wpctl("get-volume", self.mic.target, then=self.show_microphone)

    def write_state(self, output):
        level = parse_volume(output)
        if level is None:
            return
        # The popover shows it now, even if a failed wpctl left the file as it was. The
        # file gets no "key" line, so no overlay; an unchanged level is not rewritten, so
        # a key press's line survives the reread its own change causes.
        self.show_volume(*level)
        if level == parse_volume(read_path(VOLUME_STATE)):
            return
        try:
            VOLUME_STATE.write_text(output.strip() + "\n")
        except OSError:
            pass

    def show_microphone(self, output):
        """Show the default microphone's level; without one, only the list (if any)."""
        level = parse_volume(output)
        self.mic_section.set_visible(bool(self.audio["sources"]))
        self.mic.set_visible(level is not None)
        self.inputs.set_visible(len(self.audio["sources"]) > 1 or level is None)
        if level is not None:
            self.mic.show(*level)
        if level != self.microphone:
            self.microphone = level
            if self.on_microphone:
                self.on_microphone()

    def rebuild_lists(self):
        outputs = audio_outputs(self.audio)
        self.rebuild_list(self.outputs, outputs, "speaker", self.on_output_clicked)
        self.heading.set_visible(bool(outputs))
        self.rebuild_list(self.inputs, audio_inputs(self.audio), "microphone",
                          self.on_input_clicked)

    def rebuild_list(self, box, devices, glyph, on_clicked):
        """Rows that make a device the default when clicked; the default has a check."""
        clear_box(box)
        for key, description, default in devices:
            button = clickable(Gtk.Button())
            button.set_has_frame(False)
            button.add_css_class("network-row")
            button.set_child(panel_row(self.library, glyph, description, None,
                                       "check" if default else None))
            button.connect("clicked", on_clicked, key)
            box.append(button)

    def on_output_clicked(self, _button, key):
        self.wpctl("set-default", str(key), then=self.refresh)

    def on_input_clicked(self, _button, key):
        # wpctl set-default refuses virtual sources (a noise filter's, say), which
        # WirePlumber takes as the default when asked through the metadata, as wpctl
        # itself does for the rest.
        name = (self.audio["sources"].get(key) or (None,))[0]
        if name:
            self.spawn(default_source_command(name), then=self.refresh)

    def on_popover_shown(self, _popover):
        self.rebuild_lists()
        self.refresh()

    def setup(self):
        self.audio = new_audio_state()
        self.monitor_buffer = b""
        try:
            self.monitor = Gio.Subprocess.new(
                AUDIO_MONITOR_COMMAND,
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
        except GLib.Error as error:
            print(f"tinybar: cannot follow volume changes: {error.message}", flush=True)
            return False
        self.monitor_started = time.monotonic()
        self.read_monitor(self.monitor.get_stdout_pipe())
        return False

    def read_monitor(self, stream):
        stream.read_bytes_async(65536, GLib.PRIORITY_DEFAULT, None, self.on_monitor_output)

    def on_monitor_output(self, stream, result):
        try:
            chunk = stream.read_bytes_finish(result).get_data() or b""
        except GLib.Error:
            chunk = b""
        if not chunk:
            # PipeWire stopped or restarted: start again, waiting longer each time
            # pw-dump quits at once, so it never gives up on a PipeWire that comes back.
            self.monitor_delay = audio_monitor_delay(
                time.monotonic() - self.monitor_started, self.monitor_delay)
            GLib.timeout_add_seconds(self.monitor_delay, self.setup)
            return
        objects, self.monitor_buffer = split_dump(self.monitor_buffer + chunk)
        if apply_audio_objects(self.audio, objects) and self.refresh_source is None:
            self.refresh_source = GLib.timeout_add(AUDIO_EVENT_MS, self.refresh_after_event)
        self.read_monitor(stream)

    def refresh_after_event(self):
        self.refresh_source = None
        self.refresh()
        if self.get_popover().get_visible():
            self.rebuild_lists()
        return False


class BrightnessMenu(Gtk.MenuButton):
    """Brightness glyph; its popover holds a slider for the screen without brightness
    keys (an external keyboard). The slider runs `tinybar-brightness set`, the keys'
    command, so it keeps their 1 % floor. The panel reads the level back from sysfs
    (show), as for the keys, but a change the slider made shows no level overlay
    (announce). Without brightnessctl the slider is greyed out and says why."""

    def __init__(self, library):
        super().__init__()
        self.library = library
        # Monotonic time until which backlight changes count as the slider's.
        self.quiet_until = 0.0
        # Called after the slider's last change, to read the level back (the panel's
        # update_brightness), so a failed change does not leave the slider wrong.
        self.refresh = None
        self.set_has_frame(False)
        self.add_css_class("panel-menu")
        self.indicator = StatusIndicator(library, "brightness", show_value=False)
        self.set_child(self.indicator)

        self.icon = glyph_widget("level-glyph")
        self.level = LevelSlider("Brightness", self.send_brightness, self.on_sent, minimum=1)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        row.append(self.icon)
        row.append(self.level)

        self.missing = Gtk.Label(label="Install brightnessctl to change the brightness here.")
        self.missing.set_xalign(0)
        self.missing.set_wrap(True)
        self.missing.add_css_class("notification-body")

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content.add_css_class("notification-popover")
        content.append(row)
        content.append(self.missing)

        popover = Gtk.Popover()
        popover.set_child(content)
        popover.connect("show", self.on_popover_shown)
        self.set_popover(popover)
        open_below_panel(self)

    def set_text(self, text, **kwargs):
        self.indicator.set_text(text, **kwargs)

    def show(self, percent):
        """Show a level read from sysfs in the popover."""
        self.library.set_glyph(self.icon, brightness_glyph(percent))
        self.level.show(percent)

    def announce(self):
        """Whether the change just read should show the level overlay."""
        return brightness_change_announced(time.monotonic(), self.quiet_until,
                                           self.level.sending)

    def on_popover_shown(self, _popover):
        # brightnessctl may have been installed since the panel started.
        usable = can_set_brightness()
        self.level.set_sensitive(usable)
        self.missing.set_visible(not usable)

    def send_brightness(self, percent, then):
        run_command([brightness_command(), "set", str(percent)], then)

    def on_sent(self):
        self.quiet_until = time.monotonic() + BRIGHTNESS_SLIDER_QUIET_SECONDS
        if self.refresh:
            self.refresh()


class CalendarMenu(Gtk.MenuButton):
    """The clock. Its popover is a month calendar opened on today, which GTK marks;
    Today comes back to it after browsing other months. The clock keeps its label's
    look: the button's padding is cancelled by its margin (.panel-menu)."""

    def __init__(self):
        super().__init__()
        self.set_has_frame(False)
        self.add_css_class("panel-menu")
        self.add_css_class("clock-menu")
        self.label = Gtk.Label()
        self.label.add_css_class("clock")
        self.set_child(self.label)

        self.heading = Gtk.Label()
        self.heading.set_xalign(0)
        self.heading.set_hexpand(True)
        self.heading.add_css_class("power-title")
        self.today = clickable(Gtk.Button(label="Today"))
        self.today.add_css_class("network-action")
        self.today.connect("clicked", self.show_today)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.add_css_class("calendar-header")
        header.append(self.heading)
        header.append(self.today)

        self.calendar = Gtk.Calendar()
        for name in ("year", "month", "day"):
            self.calendar.connect(f"notify::{name}", self.update_today)
        # The month arrows are the calendar's own buttons.
        for widget in descendants(self.calendar):
            if isinstance(widget, Gtk.Button):
                clickable(widget)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content.add_css_class("calendar-popover")
        content.append(header)
        content.append(self.calendar)

        popover = Gtk.Popover()
        popover.set_child(content)
        popover.connect("show", self.show_today)
        self.set_popover(popover)
        open_below_panel(self)

    def set_text(self, text):
        self.label.set_text(text)

    def show_today(self, *_args):
        self.heading.set_text(calendar_heading(datetime.date.today()))
        now = GLib.DateTime.new_now_local()
        if hasattr(self.calendar, "set_date"):
            self.calendar.set_date(now)
        else:
            self.calendar.select_day(now)
        self.update_today()

    def update_today(self, *_args):
        calendar = self.calendar
        self.today.set_sensitive(not calendar_shows_today(
            calendar.get_year(), calendar.get_month() + 1, calendar.get_day(),
            datetime.date.today()))


def descendants(widget):
    """Every widget inside widget, depth first."""
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from descendants(child)
        child = child.get_next_sibling()


class LevelOverlay(Gtk.Window):
    """Brief brightness or volume readout near the bottom of the screen.

    The panel shows these as a glyph only; this shows the value for a moment
    after it changes. It takes no keyboard focus and hides itself again.
    """

    def __init__(self, application, library):
        super().__init__(application=application)

        self.library = library
        self.hide_source = None

        self.set_title("tinybar-level")
        self.set_decorated(False)
        self.add_css_class("level-window")

        Gtk4LayerShell.init_for_window(self)
        Gtk4LayerShell.set_namespace(self, "tinybar-level")

        Gtk4LayerShell.set_layer(
            self,
            Gtk4LayerShell.Layer.OVERLAY
        )

        Gtk4LayerShell.set_anchor(
            self,
            Gtk4LayerShell.Edge.BOTTOM,
            True
        )

        Gtk4LayerShell.set_margin(
            self,
            Gtk4LayerShell.Edge.BOTTOM,
            LEVEL_OVERLAY_MARGIN
        )

        Gtk4LayerShell.set_keyboard_mode(
            self,
            Gtk4LayerShell.KeyboardMode.NONE
        )

        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12
        )

        box.add_css_class("level-overlay")
        box.set_can_target(False)

        self.icon = glyph_widget("level-icon")

        self.bar = Gtk.ProgressBar()
        self.bar.add_css_class("level-bar")
        self.bar.set_hexpand(True)
        self.bar.set_valign(Gtk.Align.CENTER)

        self.value = Gtk.Label()
        self.value.add_css_class("level-value")
        self.value.set_width_chars(5)
        self.value.set_xalign(1)

        box.append(self.icon)
        box.append(self.bar)
        box.append(self.value)

        self.set_child(box)

    def show_level(self, glyph, percent, text=None, muted=False):
        self.library.set_glyph(self.icon, glyph)

        if muted:
            self.bar.add_css_class("muted")
        else:
            self.bar.remove_css_class("muted")

        self.bar.set_fraction(max(0, min(percent, 100)) / 100)
        self.value.set_text(text or f"{percent}%")

        self.set_visible(True)

        if self.hide_source is not None:
            GLib.source_remove(self.hide_source)

        self.hide_source = GLib.timeout_add(
            LEVEL_OVERLAY_MS,
            self.on_hide_timeout
        )

    def on_hide_timeout(self):
        self.hide_source = None
        self.set_visible(False)

        return False


class TaskStrip(Gtk.Widget):
    """Holds the task list and asks for no minimum width, so a full list can never
    widen the panel or push the clock and the icons aside. Given less than its list's
    natural width, the list's names shorten with "…"; given less than even the
    shortened list needs, the buttons that do not fit are cut off at the right."""

    def __init__(self, child):
        super().__init__()
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.child = child
        child.set_parent(self)

    def do_measure(self, orientation, for_size):
        minimum, natural, _base, _nat_base = self.child.measure(orientation, for_size)

        if orientation == Gtk.Orientation.HORIZONTAL:
            minimum = 0

        return minimum, natural, -1, -1

    def do_size_allocate(self, width, height, baseline):
        minimum = self.child.measure(Gtk.Orientation.HORIZONTAL, height)[0]
        self.child.allocate(max(width, minimum), height, baseline, None)


class PanelRow(Gtk.Widget):
    """The panel's row: tasks at the start, the clock centred on the panel, the icons
    at the end. The icons get their full width and the clock stays centred (moved left
    only if the icons would reach it); the tasks get what is left of the clock, never
    more. The clock does not count toward the row's height, so its larger text does not
    make the panel taller (it is centred on the row and may overhang it)."""

    def __init__(self, start, center, end, spacing):
        super().__init__()
        self.start, self.center, self.end = start, center, end
        self.spacing = spacing

        for child in (start, center, end):
            child.set_parent(self)

    def do_measure(self, orientation, for_size):
        if orientation == Gtk.Orientation.VERTICAL:
            sizes = [child.measure(orientation, -1) for child in (self.start, self.end)]
            return max(s[0] for s in sizes), max(s[1] for s in sizes), -1, -1

        sizes = [child.measure(orientation, -1) for child in (self.start, self.center, self.end)]
        gaps = 2 * self.spacing
        return sum(s[0] for s in sizes) + gaps, sum(s[1] for s in sizes) + gaps, -1, -1

    def do_size_allocate(self, width, height, baseline):
        end_min, end_nat = self.end.measure(Gtk.Orientation.HORIZONTAL, -1)[:2]
        end_width = max(end_min, min(end_nat, width))
        center_width = self.center.measure(Gtk.Orientation.HORIZONTAL, -1)[1]
        center_height = self.center.measure(Gtk.Orientation.VERTICAL, center_width)[1]
        center_x = min(
            (width - center_width) // 2,
            width - end_width - self.spacing - center_width
        )
        center_x = max(center_x, 0)
        start_width = max(0, center_x - self.spacing)

        self.place(self.start, 0, 0, start_width, height)
        self.place(self.center, center_x, (height - center_height) // 2, center_width, center_height)
        self.place(self.end, width - end_width, 0, end_width, height)

    @staticmethod
    def place(child, x, y, width, height):
        area = Gdk.Rectangle()
        area.x, area.y, area.width, area.height = x, y, width, height
        child.size_allocate(area, -1)


class TaskMenu(Gtk.Popover):
    """Right-click menu of a task button: the app's name and Close, which closes
    every window the app has. One popover, moved to the button it opens from."""

    def __init__(self, library, on_close):
        super().__init__()

        self.on_close = on_close
        self.app_id = None

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4
        )

        content.add_css_class("system-popover")

        self.heading = Gtk.Label()
        self.heading.set_xalign(0)
        self.heading.set_ellipsize(Pango.EllipsizeMode.END)
        self.heading.set_max_width_chars(30)
        self.heading.add_css_class("panel-heading")
        content.append(self.heading)

        self.close_button, icon, self.close_label = action_row()
        library.set_glyph(icon, "xmark")
        self.close_button.connect("clicked", self.on_close_clicked)
        content.append(self.close_button)

        self.set_child(content)
        place_below_panel(self)

    def open_for(self, button, app_id, name, count):
        if self.get_parent() is not button:
            self.release()
            self.set_parent(button)

        self.app_id = app_id
        self.heading.set_label(name)
        self.close_label.set_label(task_close_label(count))
        self.popup()

    def release(self, button=None):
        """Take the menu off its button (only `button`, when given), before the
        button goes."""

        parent = self.get_parent()

        if parent is None or (button is not None and parent is not button):
            return

        self.popdown()
        self.unparent()

    def on_close_clicked(self, _button):
        self.popdown()
        self.on_close(self.app_id)


class TinyBar(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="limde.Tinybar"
        )

        self.history = HistoryStore()

        self.current_samples = deque(
            maxlen=12
        )

        self.last_battery_status = None
        # Lowest warning threshold announced this discharge (see battery_warning).
        self.battery_warned = None
        # The last warning's notification id: the next one replaces it, not stacks.
        self.battery_notification = 0

        self.previous_cpu = None
        self.battery_cpu = None

        self.volume_monitor = None
        self.volume_refresh_source = None
        self.microphone_monitor = None
        self.microphone_refresh_source = None

        self.brightness_monitor = None
        self.brightness_refresh_source = None

        self.level_overlay = None

        self.task_list = None
        self.task_buttons = {}
        self.toplevel_groups = OrderedDict()
        self.active_toplevel = None
        self.last_active_toplevel = {}
        self.toplevel_windows = []
        self.focus_order = []
        self.idle_hidden = []
        self.idle_active = None
        self.toplevel_helper = None
        self.toplevel_helper_watch = None
        self.toplevel_output_buffer = b""

    def do_activate(self):
        window = Gtk.ApplicationWindow(
            application=self
        )

        window.set_title("tinybar")
        PANEL_MENUS.watch(window)

        Gtk4LayerShell.init_for_window(window)

        Gtk4LayerShell.set_layer(
            window,
            Gtk4LayerShell.Layer.TOP
        )

        for edge in (
            Gtk4LayerShell.Edge.TOP,
            Gtk4LayerShell.Edge.LEFT,
            Gtk4LayerShell.Edge.RIGHT
        ):
            Gtk4LayerShell.set_anchor(
                window,
                edge,
                True
            )

        Gtk4LayerShell.auto_exclusive_zone_enable(
            window
        )

        self.task_list = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4
        )

        self.task_list.add_css_class("task-list")
        self.task_list.set_halign(Gtk.Align.START)

        self.system_info = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12
        )

        self.system_info.set_halign(
            Gtk.Align.END
        )

        self.icons = IconLibrary()
        self.task_menu = TaskMenu(self.icons, self.close_app_windows)
        self.notifications = NotificationCenter(self.icons)
        self.cpu = StatusIndicator(self.icons, "cpu")
        self.memory = StatusIndicator(self.icons, "memory")
        self.wifi = NetworkMenu(self.icons)
        self.bluetooth = BluetoothMenu(self.icons) if BLUETOOTH is not False else None
        self.tailscale = None
        if TAILSCALE is True or (TAILSCALE == "auto" and shutil.which("tailscale")):
            self.tailscale = TailscaleButton(self.icons)
        self.brightness = BrightnessMenu(self.icons)
        self.brightness.refresh = self.update_brightness
        self.volume = VolumeMenu(self.icons)
        # A new microphone level rewrites the speaker's tooltip, which names it too.
        self.volume.on_microphone = self.update_volume_from_state
        self.battery = BatteryMenu(self.icons, self.history)
        self.system_menu = SystemMenu(self.icons, self.reload_style)
        # Desktops and VMs have no battery or backlight: leave those indicators out.
        self.battery.set_visible(HAS_BATTERY)
        self.brightness.set_visible(HAS_BACKLIGHT)

        self.level_overlay = LevelOverlay(self, self.icons)

        widgets = [self.notifications]

        if SHOW_USAGE:
            widgets += [self.cpu, self.memory]

        if self.tailscale:
            widgets.append(self.tailscale)

        widgets.append(self.wifi)

        if self.bluetooth:
            widgets.append(self.bluetooth)

        widgets += [
            self.brightness,
            self.volume,
            self.battery,
            self.system_menu
        ]

        for widget in widgets:
            widget.add_css_class("system-info")
            self.system_info.append(widget)

        self.clock = CalendarMenu()

        # TaskStrip lets the tasks take less than their own minimum, so a full list
        # never pushes the clock or the icons aside.
        row = PanelRow(TaskStrip(self.task_list), self.clock, self.system_info, spacing=12)

        row.set_margin_start(12)
        row.set_margin_end(12)
        row.set_margin_top(5)
        row.set_margin_bottom(5)

        window.set_child(row)

        css = self.css = Gtk.CssProvider()

        try:
            css.load_from_path(
                str(STYLE_FILE)
            )

            # ~/.config/gtk-4.0/gtk.css loads at USER priority, above
            # APPLICATION, and its generic button, .background and :checked
            # rules would otherwise box the panel buttons and paint behind
            # popovers. The panel's own sheet has to win inside the panel.
            Gtk.StyleContext.add_provider_for_display(
                window.get_display(),
                css,
                Gtk.STYLE_PROVIDER_PRIORITY_USER + 1
            )

        except GLib.Error as error:
            print(
                f"tinybar: failed to load CSS: {error}",
                flush=True
            )

        self.setup_volume_monitor()
        self.volume.setup()
        self.setup_brightness_monitor()
        self.wifi.setup()

        if self.bluetooth:
            self.bluetooth.setup()

        self.setup_toplevel_helper()
        self.setup_idle_hide()

        self.update_clock()
        self.notifications.refresh()

        if SHOW_USAGE:
            self.update_usage()

        self.update_battery()
        self.update_temperature_history()

        self.schedule_next_clock_update()

        if SHOW_USAGE:
            GLib.timeout_add_seconds(
                USAGE_SAMPLE_SECONDS,
                self.update_usage
            )

        GLib.timeout_add_seconds(
            BATTERY_SAMPLE_SECONDS,
            self.update_battery
        )

        GLib.timeout_add_seconds(
            TEMP_SAMPLE_SECONDS,
            self.update_temperature_history
        )

        GLib.timeout_add_seconds(
            NOTIFICATION_SAMPLE_SECONDS,
            self.notifications.refresh
        )

        if self.tailscale:
            self.tailscale.refresh()
            GLib.timeout_add_seconds(TAILSCALE_SAMPLE_SECONDS, self.tailscale.refresh)

        window.present()

    # ---------- running applications ----------

    def setup_toplevel_helper(self):
        helper_environment = os.environ.copy()
        helper_environment.pop("LD_PRELOAD", None)
        helper_environment.pop("GSK_RENDERER", None)
        helper_environment.pop("GTK_A11Y", None)

        try:
            self.toplevel_helper = subprocess.Popen(
                (str(TOPLEVEL_HELPER),),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=helper_environment
            )
        except OSError as error:
            print(
                f"tinybar: cannot start toplevel helper: {error}",
                flush=True
            )
            return

        os.set_blocking(
            self.toplevel_helper.stdout.fileno(),
            False
        )

        self.toplevel_helper_watch = GLib.io_add_watch(
            self.toplevel_helper.stdout,
            GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,
            self.on_toplevel_helper_output
        )

    def on_toplevel_helper_output(self, stream, condition):
        latest_snapshot = None

        while True:
            try:
                chunk = os.read(stream.fileno(), 65536)
            except BlockingIOError:
                break
            except OSError:
                chunk = b""

            if not chunk:
                break

            self.toplevel_output_buffer += chunk

        lines = self.toplevel_output_buffer.split(b"\n")
        self.toplevel_output_buffer = lines.pop()

        for line in lines:
            if not line:
                continue

            try:
                latest_snapshot = json.loads(
                    line.decode("utf-8")
                )
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue

        if latest_snapshot is not None:
            self.apply_toplevel_snapshot(
                latest_snapshot.get("windows", [])
            )

        if condition & (GLib.IO_HUP | GLib.IO_ERR):
            if self.toplevel_output_buffer:
                try:
                    snapshot = json.loads(
                        self.toplevel_output_buffer.decode(
                            "utf-8"
                        )
                    )
                    self.apply_toplevel_snapshot(
                        snapshot.get("windows", [])
                    )
                except (UnicodeDecodeError, json.JSONDecodeError):
                    pass

            self.toplevel_output_buffer = b""
            self.toplevel_helper_watch = None
            return False

        return True

    def display_name_for_app(self, app_id):
        desktop = desktop_entry(app_id)
        name = desktop.get_display_name() if desktop else None

        if name:
            return name

        name = app_id.rsplit(".", 1)[-1]
        name = name.replace("-", " ").replace("_", " ")

        return name.title()

    def apply_toplevel_snapshot(self, windows):
        active = None
        groups = OrderedDict()

        self.toplevel_windows = windows
        present = {window["id"] for window in windows}
        self.focus_order = [i for i in self.focus_order if i in present]
        for window in windows:
            if window.get("active") and not window.get("minimized"):
                if window["id"] in self.focus_order:
                    self.focus_order.remove(window["id"])
                self.focus_order.append(window["id"])

        for window in windows:
            app_id = str(window.get("app_id", "")).strip()
            title = str(window.get("title", "")).strip()

            if not app_id or window.get("parent"):
                continue

            if app_id.casefold() in TINYBAR_APP_IDS:
                continue

            if title.casefold() == "tinybar":
                continue

            groups.setdefault(app_id, []).append(window)

            if window.get("active"):
                active = window

        if active is not None:
            self.last_active_toplevel[active["app_id"]] = active["id"]

        self.toplevel_groups = groups
        self.active_toplevel = active
        self.render_task_list()

    def render_task_list(self):
        current_ids = set(self.toplevel_groups)

        for app_id in tuple(self.task_buttons):
            if app_id in current_ids:
                continue

            button = self.task_buttons.pop(app_id)
            self.task_menu.release(button)
            self.task_list.remove(button)

        for position, (app_id, windows) in enumerate(
            self.toplevel_groups.items()
        ):
            button = self.task_buttons.get(app_id)

            if button is None:
                button = clickable(Gtk.Button())
                button.add_css_class("task-label")
                button.connect(
                    "clicked",
                    self.on_task_clicked,
                    app_id
                )
                menu_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
                menu_click.connect("pressed", self.on_task_menu_pressed, button, app_id)
                button.add_controller(menu_click)
                content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                icon = self.icons.application_widget(app_id)
                if icon is not None:
                    content.append(icon)
                # A long name ends in "…" (the tooltip has it whole); the window count
                # has its own label so it never does.
                button.name_label = Gtk.Label()
                button.name_label.set_ellipsize(Pango.EllipsizeMode.END)
                button.name_label.set_max_width_chars(TASK_NAME_MAX_CHARS)
                button.count_label = Gtk.Label()
                # The first app shows its icon alone when it has one.
                icon_only = app_id == FIRST_APP_ID and icon is not None
                button.name_label.set_visible(not icon_only)
                button.icon_only = icon_only
                if icon_only:
                    icon.add_css_class("icon-only")
                content.append(button.name_label)
                content.append(button.count_label)
                button.set_child(content)
                self.task_buttons[app_id] = button
                # A None sibling inserts at the start of the box.
                self.task_list.insert_child_after(
                    button,
                    None if app_id == FIRST_APP_ID
                    else self.task_list.get_last_child()
                )

            count = len(windows)
            name = self.display_name_for_app(app_id)

            button.name_label.set_text(name)
            button.count_label.set_text(f"({count})")
            button.count_label.set_visible(count > 1 and not button.icon_only)
            button.set_tooltip_text(task_tooltip(
                name,
                [str(window.get("title") or "") for window in windows]
            ))

            is_active = (
                self.active_toplevel is not None
                and self.active_toplevel["app_id"] == app_id
            )

            if is_active:
                button.add_css_class("active")
            else:
                button.remove_css_class("active")

    def on_task_clicked(self, button, app_id):
        windows = self.toplevel_groups.get(app_id, [])

        if not windows:
            return

        verb, target = task_click_action(
            windows,
            self.last_active_toplevel.get(app_id)
        )

        if self.send_toplevel_command(verb, target["id"]):
            self.last_active_toplevel[app_id] = target["id"]

    def on_task_menu_pressed(self, gesture, _presses, _x, _y, button, app_id):
        windows = self.toplevel_groups.get(app_id, [])

        if not windows:
            return

        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self.task_menu.open_for(
            button,
            app_id,
            self.display_name_for_app(app_id),
            len(windows)
        )

    def close_app_windows(self, app_id):
        """Ask each of the app's windows to close, as its own close button would: an
        app with unsaved work can still ask first."""

        for window in self.toplevel_groups.get(app_id, []):
            self.send_toplevel_command("close", window["id"])

    def send_toplevel_command(self, verb, window_id):
        try:
            self.toplevel_helper.stdin.write(f"{verb} {window_id}\n")
            self.toplevel_helper.stdin.flush()
        except (AttributeError, BrokenPipeError, OSError):
            return False
        return True

    # ---------- idle hide ----------

    def setup_idle_hide(self):
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(f"{os.getpid()}\n")
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self.idle_hide)
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR2, self.idle_restore)

    def idle_hide(self):
        if not IDLE_HIDE or self.idle_hidden:
            return True
        if IDLE_HIDE_BATTERY_ONLY and on_mains_power():
            return True
        hidden = idle_hide_order(self.toplevel_windows, self.focus_order, IDLE_HIDE_KEEP)
        active = next((w["id"] for w in self.toplevel_windows if w.get("active")), None)
        self.idle_hidden = [w["id"] for w in hidden if self.send_toplevel_command("minimize", w["id"])]
        # Focus goes back to it on restore, even when it was kept visible (an RDP window).
        self.idle_active = active if self.idle_hidden else None
        return True

    def idle_restore(self):
        hidden, self.idle_hidden = self.idle_hidden, []
        still_minimized = {w["id"] for w in self.toplevel_windows if w.get("minimized")}
        for window_id in hidden:
            if window_id in still_minimized:
                self.send_toplevel_command("unminimize", window_id)
        if self.idle_active in {w["id"] for w in self.toplevel_windows}:
            self.send_toplevel_command("activate", self.idle_active)
        self.idle_active = None
        return True

    # ---------- clock ----------

    def reload_style(self):
        """Reread the generated stylesheet after the system menu switches mode."""

        try:
            self.css.load_from_path(str(STYLE_FILE))
        except GLib.Error as error:
            print(f"tinybar: failed to reload CSS: {error}", flush=True)

        # GTK 4 on Wayland reads the icon theme from settings.ini only at start, so
        # the light and dark app icons would otherwise stay as they were.
        interface = interface_settings()

        if interface:
            Gtk.Settings.get_default().set_property(
                "gtk-icon-theme-name", interface.get_string("icon-theme")
            )

    def update_clock(self):
        now = datetime.datetime.now()

        self.clock.set_text(
            now.strftime(
                "%a %b %-d   %-I:%M %p"
            )
        )

    def schedule_next_clock_update(self):
        now = datetime.datetime.now()

        delay_ms = int(
            (
                60
                - now.second
                - now.microsecond / 1_000_000
            )
            * 1000
        )

        delay_ms = max(
            delay_ms,
            100
        )

        GLib.timeout_add(
            delay_ms,
            self.on_clock_timer
        )

    def on_clock_timer(self):
        self.update_clock()
        self.schedule_next_clock_update()

        return False

    # ---------- CPU / RAM ----------

    def update_usage(self):
        now = time.time()

        current_cpu = read_cpu_counters()

        if (
            current_cpu is not None
            and self.previous_cpu is not None
        ):
            total_delta = (
                current_cpu[0]
                - self.previous_cpu[0]
            )

            idle_delta = (
                current_cpu[1]
                - self.previous_cpu[1]
            )

            if total_delta > 0:
                usage = (
                    (
                        total_delta
                        - idle_delta
                    )
                    / total_delta
                    * 100
                )

                usage = max(
                    0.0,
                    min(
                        usage,
                        100.0
                    )
                )

                self.cpu.set_text(
                    f"CPU {usage:.0f}%",
                    tooltip=usage_lines(usage, None)[0]
                )

                self.history.add_sample(
                    "cpu_percent",
                    usage,
                    now
                )

        elif current_cpu is not None:
            self.cpu.set_text(
                "CPU ...",
                tooltip="CPU: measuring…"
            )

        self.previous_cpu = current_cpu

        memory = get_memory_usage()

        if memory:
            used, total = memory

            self.memory.set_text(
                f"RAM {used:.1f}/{total:.1f}G",
                tooltip=usage_lines(None, memory)[0]
            )

            self.history.add_sample(
                "memory_used_gib",
                used,
                now
            )

        else:
            self.memory.set_text(
                "RAM ?",
                tooltip="Memory: unavailable"
            )

        return True

    # ---------- temperature history ----------

    def update_temperature_history(self):
        temperature = get_cpu_temperature()

        if temperature is not None:
            self.history.add_sample(
                "temperature_c",
                temperature,
                time.time()
            )

        return True

    # ---------- volume ----------

    def setup_volume_monitor(self):
        RUNTIME_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        try:
            result = subprocess.run(
                [
                    WPCTL,
                    "get-volume",
                    "@DEFAULT_AUDIO_SINK@"
                ],
                capture_output=True,
                text=True,
                timeout=2,
                env={
                    **os.environ,
                    "LC_ALL": "C"
                }
            )

            if result.returncode == 0:
                VOLUME_STATE.write_text(
                    result.stdout.strip()
                    + "\n"
                )

        except (
            OSError,
            subprocess.TimeoutExpired
        ):
            pass

        if not VOLUME_STATE.exists():
            VOLUME_STATE.touch()

        self.update_volume_from_state()

        volume_file = Gio.File.new_for_path(
            str(VOLUME_STATE)
        )

        self.volume_monitor = (
            volume_file.monitor_file(
                Gio.FileMonitorFlags.NONE,
                None
            )
        )

        self.volume_monitor.connect(
            "changed",
            self.on_volume_state_changed
        )

        # The mic-mute key's file need not exist yet; the monitor sees it created.
        self.microphone_monitor = Gio.File.new_for_path(
            str(MICROPHONE_STATE)
        ).monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.microphone_monitor.connect(
            "changed",
            self.on_microphone_state_changed
        )

    def on_volume_state_changed(
        self,
        *args
    ):
        if self.volume_refresh_source is None:
            self.volume_refresh_source = (
                GLib.timeout_add(
                    25,
                    self.refresh_volume_after_event
                )
            )

    def refresh_volume_after_event(self):
        self.volume_refresh_source = None
        self.update_volume_from_state(announce=True)

        return False

    def update_volume_from_state(self, announce=False):
        # announce: the file changed. The level overlay shows only if a key wrote
        # it: tinybar-volume ends a key's write with a "key" line; the popover and
        # changes made elsewhere (VolumeMenu.write_state) do not.
        output = read_path(
            VOLUME_STATE
        )

        level = parse_volume(output)

        if level is None:
            self.volume.set_text(
                "VOL ?",
                tooltip=volume_tooltip(None, self.volume.microphone)
            )
            return

        percent, muted = level

        # The state string picks the icon (IconLibrary.status_name); the
        # tooltip is the words.
        if muted:
            self.volume.set_text(
                "VOL MUTED",
                tooltip=volume_tooltip(level, self.volume.microphone)
            )

        else:
            self.volume.set_text(
                f"VOL {percent}%",
                tooltip=volume_tooltip(level, self.volume.microphone)
            )

        self.volume.show_volume(percent, muted)

        if announce and output.splitlines()[-1] == "key":
            self.level_overlay.show_level(
                volume_glyph(percent or 0, muted),
                percent or 0,
                "Muted" if muted else None,
                muted
            )

    def on_microphone_state_changed(self, *args):
        # Only the mic-mute key writes this file (tinybar-volume mic-mute); the popover
        # and the tooltip follow the change through VolumeMenu's pw-dump child.
        if self.microphone_refresh_source is None:
            self.microphone_refresh_source = GLib.timeout_add(
                25, self.show_microphone_key)

    def show_microphone_key(self):
        self.microphone_refresh_source = None
        output = read_path(MICROPHONE_STATE)
        level = parse_volume(output)

        if level is not None and output.splitlines()[-1] == "key":
            percent, muted = level
            self.level_overlay.show_level(
                microphone_glyph(percent, muted),
                percent,
                "Muted" if muted else None,
                muted
            )

        return False

    # ---------- brightness ----------

    def setup_brightness_monitor(self):
        self.update_brightness()

        brightness_file = Gio.File.new_for_path(
            str(BACKLIGHT / "brightness")
        )

        try:
            self.brightness_monitor = (
                brightness_file.monitor_file(
                    Gio.FileMonitorFlags.NONE,
                    None
                )
            )

            self.brightness_monitor.connect(
                "changed",
                self.on_brightness_changed
            )

        except GLib.Error:
            self.brightness.set_text(
                "BRI ?",
                tooltip=brightness_tooltip(None)
            )

    def on_brightness_changed(
        self,
        *args
    ):
        # sysfs emits several notifications for a single brightness
        # change. Coalesce them into one UI refresh.
        if self.brightness_refresh_source is None:
            self.brightness_refresh_source = (
                GLib.timeout_add(
                    30,
                    self.refresh_brightness_after_event
                )
            )

    def refresh_brightness_after_event(self):
        self.brightness_refresh_source = None
        self.update_brightness(announce=self.brightness.announce())

        return False

    def update_brightness(self, announce=False):
        # announce: the backlight changed, so also show the level overlay.
        if not HAS_BACKLIGHT:
            return
        percent = brightness_percent(read_path(BACKLIGHT / "brightness"),
                                     read_path(BACKLIGHT / "max_brightness"))

        if percent is None:
            self.brightness.set_text("BRI ?", tooltip=brightness_tooltip(None))
            return

        self.brightness.set_text(f"BRI {percent}%", tooltip=brightness_tooltip(percent))
        self.brightness.show(percent)

        if announce:
            self.level_overlay.show_level(brightness_glyph(percent), percent)

    # ---------- battery ----------

    def update_battery(self):
        if not HAS_BATTERY:
            return
        now = time.time()

        capacity = (
            read_battery_text(
                "capacity"
            )
            or "?"
        )

        status = (
            read_battery_text(
                "status"
            )
            or "Unknown"
        )

        charge_now = read_battery_int(
            "charge_now"
        )

        charge_full = read_battery_int(
            "charge_full"
        )

        current_now = read_battery_int(
            "current_now"
        )

        voltage_now = read_battery_int(
            "voltage_now"
        )

        # Batteries that report energy instead of charge give power_now (µW).
        power_now = read_battery_int(
            "power_now"
        )

        limit_end, limit_start = read_charge_limit()

        if status != self.last_battery_status:
            self.current_samples.clear()
            self.last_battery_status = status

        if (
            current_now is not None
            and current_now > 0
        ):
            self.current_samples.append(
                current_now
            )

        average_current = None

        if self.current_samples:
            average_current = (
                sum(self.current_samples)
                / len(self.current_samples)
            )

        # The state string IconLibrary.status_name picks the icon from: the
        # level, "+" while charging, "PLUG" while plugged in but not charging
        # (held by the charge limit). The hover words are battery_tooltip's.
        icon_state = f"BAT {capacity}%"
        smoothed_watts = None

        if status == "Charging":
            icon_state += " +"

        elif status == "Not charging":
            icon_state += " PLUG"

        elif status == "Full":
            icon_state += " FULL"

        if (
            status == "Discharging"
            and current_now is not None
            and current_now > 0
            and voltage_now is not None
        ):
            current_watts = (
                current_now
                * voltage_now
                / 1_000_000_000_000
            )

            self.history.add_sample(
                "power_w",
                current_watts,
                now
            )

        # The smoothed draw on battery, or the charge rate while charging.
        rate_watts = None

        if status in ("Discharging", "Charging"):
            if average_current and voltage_now is not None:
                rate_watts = (
                    average_current
                    * voltage_now
                    / 1_000_000_000_000
                )
            elif power_now:
                rate_watts = power_now / 1_000_000

        if status == "Discharging":
            smoothed_watts = rate_watts

        hours = None

        if average_current:
            if (
                status == "Discharging"
                and charge_now is not None
            ):
                hours = (
                    charge_now
                    / average_current
                )

            elif (
                status == "Charging"
                and charge_now is not None
                and charge_full is not None
            ):
                # To the charge limit when there is one, not to full.
                target = (
                    charge_full * limit_end / 100
                    if limit_end is not None
                    else charge_full
                )

                remaining = max(
                    target - charge_now,
                    0
                )

                hours = (
                    remaining
                    / average_current
                )

        runtime_text = format_runtime(
            hours
        )

        percent = int(capacity) if capacity.isdigit() else None
        # CPU and RAM ride along in the popover, sampled with the battery, so
        # they need no timer of their own and are not recorded. CPU is the
        # average since the previous battery sample.
        current_cpu = read_cpu_counters()
        usage = usage_rows(
            cpu_percent(self.battery_cpu, current_cpu),
            get_memory_usage()
        )
        self.battery_cpu = current_cpu

        self.battery.show_status(
            battery_rows(
                percent,
                status,
                runtime_text,
                rate_watts,
                limit_end,
                limit_start
            ) + usage
        )

        # Low-battery notifications, each threshold once per discharge.
        warning, self.battery_warned = battery_warning(
            percent,
            status,
            self.battery_warned
        )

        if warning is not None:
            self.send_battery_warning(
                capacity,
                warning,
                runtime_text
            )

        # The panel shows only the time left (to empty, or to full while
        # charging); the percentage is in the tooltip. Without an
        # estimate yet, or when full, the icon stands alone.
        remaining = None

        if status in ("Discharging", "Charging"):
            remaining = format_hours(hours)

        self.battery.set_text(
            icon_state,
            display_text=f"BAT {remaining or ''}",
            tooltip=battery_tooltip(
                percent,
                status,
                runtime_text,
                limit_end,
                limit_start
            )
        )

        load = (
            battery_load(smoothed_watts)
            if status == "Discharging"
            else None
        )

        if self.battery.get_popover().get_visible():
            self.battery.refresh()

        for _threshold, name in BATTERY_LOAD_LEVELS:
            if name == load:
                self.battery.icon.add_css_class(name)
            else:
                self.battery.icon.remove_css_class(name)

        return True

    def send_battery_warning(self, percent, threshold, runtime_text):
        """Post a low-battery notification (post_notification). Each warning
        replaces the previous one, so at most one stays on screen (Mako keeps
        urgent ones until dismissed); one already dismissed is simply posted anew."""

        urgent = threshold == BATTERY_CRITICAL_PERCENT
        summary, body = battery_warning_text(percent, threshold, runtime_text)

        def posted(notification_id):
            self.battery_notification = notification_id

        post_notification(
            summary,
            body,
            "battery-caution" if urgent else "battery-low",
            urgent=urgent,
            replaces=self.battery_notification,
            on_posted=posted
        )


def post_notification(summary, body, icon, urgent=False, replaces=0, on_posted=None,
                      on_click=None):
    """Post a notification through the session's notification service (Mako).
    Asynchronous, so a missing or slow service never stalls the panel; a failure is
    only logged. on_posted(id) gets its id, for replacing it later. With on_click,
    clicking the notification calls it (the "default" action)."""

    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    except GLib.Error as error:
        print(f"tinybar: notification not shown: {error.message}", flush=True)
        return

    def finished(bus, result):
        try:
            (notification_id,) = bus.call_finish(result).unpack()
        except GLib.Error as error:
            print(f"tinybar: notification not shown: {error.message}", flush=True)
            return

        if on_posted:
            on_posted(notification_id)

        if on_click:
            follow_notification_click(bus, notification_id, on_click)

    bus.call(
        MAKO_NAME,
        NOTIFICATIONS_PATH,
        NOTIFICATIONS_INTERFACE,
        "Notify",
        GLib.Variant(
            "(susssasa{sv}i)",
            (
                "Tinybar",
                replaces,
                icon,
                summary,
                body,
                ["default", "Open"] if on_click else [],
                {
                    "urgency": GLib.Variant(
                        "y",
                        NOTIFY_URGENCY_CRITICAL if urgent else NOTIFY_URGENCY_NORMAL
                    )
                },
                -1
            )
        ),
        GLib.VariantType.new("(u)"),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
        finished
    )


def follow_notification_click(bus, notification_id, on_click):
    """Call on_click when notification_id's default action is invoked; stop
    listening once it closes."""

    subscriptions = []

    def stop():
        for subscription in subscriptions:
            bus.signal_unsubscribe(subscription)
        subscriptions.clear()

    def on_action(_bus, _sender, _path, _interface, _signal, parameters):
        invoked_id, action = parameters.unpack()
        if invoked_id == notification_id and action == "default":
            stop()
            on_click()

    def on_closed(_bus, _sender, _path, _interface, _signal, parameters):
        if parameters.unpack()[0] == notification_id:
            stop()

    for signal, handler in (("ActionInvoked", on_action), ("NotificationClosed", on_closed)):
        subscriptions.append(bus.signal_subscribe(
            None, NOTIFICATIONS_INTERFACE, signal, NOTIFICATIONS_PATH, None,
            Gio.DBusSignalFlags.NONE, handler
        ))


# Guarded so the tests can import the pure helpers without starting a panel.
if __name__ == "__main__":
    app = TinyBar()
    raise SystemExit(app.run())
