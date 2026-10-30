#!/usr/bin/env python3

import datetime
import json
import os
import re
import shutil
import signal
import subprocess
import time
import tomllib
from collections import OrderedDict, deque
from pathlib import Path

import gi
from tinybar_icons import (
    IconLibrary,
    StatusIndicator,
    brightness_glyph,
    desktop_entry,
    glyph_widget,
    layered_glyph,
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


BATTERY = first_device("power_supply/BAT*", "power_supply/BAT0")
BACKLIGHT = first_device("backlight/*", "backlight/none")
HAS_BATTERY = (BATTERY / "capacity").exists()
HAS_BACKLIGHT = (BACKLIGHT / "brightness").exists()

RUNTIME_DIR = Path(
    f"/run/user/{os.getuid()}/tinybar"
)

VOLUME_STATE = RUNTIME_DIR / "volume"
# tinybar-idle reads this to signal the panel: SIGUSR1 hides, SIGUSR2 restores.
PID_FILE = RUNTIME_DIR / "tinybar.pid"

CONFIG_DIR = Path.home() / ".config/tinybar"
STYLE_FILE = CONFIG_DIR / "style.css"
# The window-list helper is installed beside this file.
TOPLEVEL_HELPER = Path(__file__).resolve().with_name("toplevel-helper")

STATE_DIR = Path.home() / ".local/state/tinybar"
HISTORY_FILE = STATE_DIR / "history.jsonl"
OLD_HISTORY_FILE = STATE_DIR / "history.json"

BATTERY_SAMPLE_SECONDS = 5
USAGE_SAMPLE_SECONDS = 2
TEMP_SAMPLE_SECONDS = 30
NOTIFICATION_SAMPLE_SECONDS = 2

# CPU and RAM readouts are off in the panel until they show something more
# useful. The sampling code stays; with this off it is never scheduled, so
# those two metrics also stop being added to the history file. The battery's
# hover text shows both anyway (see update_battery).
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

HISTORY_BUCKET_SECONDS = 300
HISTORY_WINDOW_SECONDS = 3 * 60 * 60
HISTORY_RETENTION_SECONDS = 7 * 24 * 60 * 60
HISTORY_PRUNE_SECONDS = 24 * 60 * 60

MAKO_NAME = "org.freedesktop.Notifications"
MAKO_PATH = "/fr/emersion/Mako"
MAKO_INTERFACE = "fr.emersion.Mako"

# Mako answers immediately; a short ceiling keeps a wedged daemon from
# stalling the panel's main loop on every poll.
MAKO_TIMEOUT_MS = 500

NOTIFICATION_SUMMARY_CHARS = 44
NOTIFICATION_BODY_CHARS = 60
NOTIFICATION_LIST_HEIGHT = 320

# Space between the panel's bottom edge and a popover's top edge.
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
NM_CONNECT_SECONDS = 45
NM_ACTION_TIMEOUT_MS = 10000
# "Other network…": hidden networks, enterprise logins and anything else nmtui handles.
OTHER_NETWORK_COMMAND = ["foot", "nmtui"]
NM_TIMEOUT_MS = 1000

NETWORK_LIST_HEIGHT = 320

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


def format_coverage(seconds):
    total_minutes = int(seconds / 60)

    if total_minutes < 1:
        return "<1m"

    h, m = divmod(total_minutes, 60)

    if h:
        return f"{h}h {m:02d}m"

    return f"{m}m"


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
    """Hover-text lines for CPU and RAM; an unavailable reading is left out."""
    lines = []

    if cpu is not None:
        lines.append(f"CPU {cpu:.0f}%")

    if memory:
        used, total = memory
        lines.append(f"RAM {used:.1f}/{total:.1f} GiB")

    return lines


class HistoryStore:
    def __init__(self):
        STATE_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        self.records = deque()
        self.current_start = None

        self.current = {
            metric: []
            for metric in METRIC_INTERVALS
        }

        self.last_prune = time.time()

        self.load()

    def load(self):
        cutoff = (
            time.time()
            - HISTORY_RETENTION_SECONDS
        )

        if HISTORY_FILE.exists():
            try:
                for line in HISTORY_FILE.read_text().splitlines():
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if record.get("schema_version") != 1:
                        continue

                    if record.get("start_epoch", 0) >= cutoff:
                        self.records.append(record)

            except OSError:
                pass

            return

        # One-time migration of v0.4 power history.
        if OLD_HISTORY_FILE.exists():
            try:
                old = json.loads(
                    OLD_HISTORY_FILE.read_text()
                )

                if old.get("version") == 1:
                    for bucket in old.get(
                        "power",
                        {}
                    ).get("buckets", []):
                        start_epoch = bucket.get(
                            "start_epoch",
                            0
                        )

                        if start_epoch < cutoff:
                            continue

                        metric = {
                            "sample_count": bucket.get(
                                "samples",
                                0
                            ),
                            "coverage_seconds": bucket.get(
                                "coverage_seconds",
                                0
                            ),
                            "avg": bucket.get(
                                "avg_w"
                            ),
                            "min": bucket.get(
                                "min_w"
                            ),
                            "max": bucket.get(
                                "max_w"
                            ),
                        }

                        record = {
                            "schema_version": 1,
                            "start": bucket.get(
                                "start"
                            ),
                            "start_epoch": start_epoch,
                            "duration_seconds":
                                HISTORY_BUCKET_SECONDS,
                            "metrics": {
                                "power_w": metric
                            }
                        }

                        self.records.append(record)

            except (
                OSError,
                json.JSONDecodeError
            ):
                pass

        self.rewrite()

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

    def flush(self):
        if self.current_start is None:
            return

        metrics = {}

        for metric, samples in self.current.items():
            if not samples:
                continue

            interval = METRIC_INTERVALS[metric]

            coverage = min(
                len(samples) * interval,
                HISTORY_BUCKET_SECONDS
            )

            metrics[metric] = {
                "sample_count": len(samples),
                "coverage_seconds": coverage,
                "avg": round(
                    sum(samples) / len(samples),
                    3
                ),
                "min": round(
                    min(samples),
                    3
                ),
                "max": round(
                    max(samples),
                    3
                ),
            }

        if metrics:
            start_datetime = (
                datetime.datetime
                .fromtimestamp(self.current_start)
                .astimezone()
            )

            record = {
                "schema_version": 1,
                "start": start_datetime.isoformat(
                    timespec="seconds"
                ),
                "start_epoch": self.current_start,
                "duration_seconds":
                    HISTORY_BUCKET_SECONDS,
                "metrics": metrics,
            }

            self.records.append(record)

            try:
                with HISTORY_FILE.open("a") as file:
                    file.write(
                        json.dumps(
                            record,
                            separators=(",", ":")
                        )
                        + "\n"
                    )
            except OSError:
                pass

        self.current = {
            metric: []
            for metric in METRIC_INTERVALS
        }

        self.prune_if_needed()

    def prune_if_needed(self):
        now = time.time()

        if (
            now - self.last_prune
            < HISTORY_PRUNE_SECONDS
        ):
            return

        cutoff = (
            now
            - HISTORY_RETENTION_SECONDS
        )

        self.records = deque(
            record
            for record in self.records
            if record.get(
                "start_epoch",
                0
            ) >= cutoff
        )

        self.rewrite()

        self.last_prune = now

    def rewrite(self):
        temp = HISTORY_FILE.with_suffix(
            ".jsonl.tmp"
        )

        try:
            with temp.open("w") as file:
                for record in self.records:
                    file.write(
                        json.dumps(
                            record,
                            separators=(",", ":")
                        )
                        + "\n"
                    )

            os.replace(
                temp,
                HISTORY_FILE
            )

        except OSError:
            try:
                temp.unlink()
            except OSError:
                pass

    def trailing_average(
        self,
        metric,
        now=None,
        window=HISTORY_WINDOW_SECONDS
    ):
        if now is None:
            now = time.time()

        cutoff = now - window

        weighted_sum = 0.0
        coverage_total = 0.0

        for record in self.records:
            start = record.get(
                "start_epoch"
            )

            if start is None:
                continue

            end = (
                start
                + record.get(
                    "duration_seconds",
                    HISTORY_BUCKET_SECONDS
                )
            )

            overlap = max(
                0,
                min(now, end)
                - max(cutoff, start)
            )

            if overlap <= 0:
                continue

            data = record.get(
                "metrics",
                {}
            ).get(metric)

            if not data:
                continue

            avg = data.get("avg")
            coverage = data.get(
                "coverage_seconds",
                0
            )

            if avg is None or coverage <= 0:
                continue

            effective_coverage = min(
                float(coverage),
                float(overlap)
            )

            weighted_sum += (
                float(avg)
                * effective_coverage
            )

            coverage_total += (
                effective_coverage
            )

        samples = self.current.get(
            metric,
            []
        )

        if (
            samples
            and self.current_start is not None
        ):
            interval = METRIC_INTERVALS[metric]

            overlap = max(
                0,
                now
                - max(
                    cutoff,
                    self.current_start
                )
            )

            coverage = min(
                len(samples) * interval,
                overlap,
                HISTORY_BUCKET_SECONDS
            )

            if coverage > 0:
                avg = (
                    sum(samples)
                    / len(samples)
                )

                weighted_sum += (
                    avg
                    * coverage
                )

                coverage_total += coverage

        if coverage_total <= 0:
            return None, 0

        return (
            weighted_sum / coverage_total,
            coverage_total
        )


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


def open_below_panel(button):
    """Open a panel button's popover without an arrow, clear of the panel.

    GTK anchors a popover to the button itself, so by default its arrow and top
    edge sit over the lower part of the bar. The offset is measured when the
    popover opens, so it follows font and margin changes.
    """

    popover = button.get_popover()
    popover.set_has_arrow(False)

    def on_show(_popover):
        root = button.get_root()
        found, bounds = button.compute_bounds(root)

        if not found:
            return

        below = root.get_height() - (
            bounds.get_y() + bounds.get_height()
        )

        popover.set_offset(0, round(below) + POPOVER_GAP)

    popover.connect("show", on_show)


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
    """

    def __init__(self, library):
        super().__init__()

        self.library = library
        self.proxy = None
        self.entries = []
        self.acknowledged = set()
        self.last_count = None

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

        self.clear = Gtk.Button(label="Clear all")
        self.clear.add_css_class("notification-clear")
        self.clear.connect("clicked", self.on_clear_clicked)

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6
        )

        content.add_css_class("notification-popover")
        content.append(self.empty)
        content.append(scroller)
        content.append(self.clear)

        popover = Gtk.Popover()
        popover.set_child(content)
        popover.connect("show", self.on_popover_shown)

        self.set_popover(popover)
        open_below_panel(self)

        if self.library.set_glyph(self.icon, "bell"):
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

        known = {entry["id"] for entry in found}
        self.acknowledged &= known

        self.entries = [
            entry for entry in found
            if entry["id"] not in self.acknowledged
        ]

        count = len(self.entries)

        if count != self.last_count:
            self.last_count = count
            self.count.set_text(str(count) if count else "")
            self.count.set_visible(bool(count))

            if count:
                self.icon.remove_css_class("icon-only")
            else:
                self.icon.add_css_class("icon-only")

            label = (
                f"{count} notifications" if count != 1
                else "1 notification"
            )

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

        close = Gtk.Button()
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
        self.button = Gtk.Button()
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

        self.switch = Gtk.Switch()
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

        self.heading = Gtk.Label(label="Available networks")
        self.heading.set_xalign(0)
        self.heading.add_css_class("panel-heading")

        self.available = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2
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

        other = Gtk.Button()
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
        button = Gtk.Button(label=label)
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
            self.indicator.set_text("WIFI ?")
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
            self.indicator.set_text("WIFI ?")
            return

        self.state = state
        wifi = state["wifi"]

        if wifi and wifi["ssid"]:
            self.indicator.set_text(
                f"WIFI {wifi['ssid']}",
                icon=signal_glyph(wifi["strength"])
            )

        elif state["wifi_connected"]:
            self.indicator.set_text("WIFI ON")

        elif state["wired"]:
            # Online by cable (desktops, VMs, docks): show that rather than Wi-Fi off.
            self.indicator.set_text("WIRED Connected", icon="network-wired")

        else:
            self.indicator.set_text("WIFI OFF")

        if listing:
            self.rebuild(state)

    def rebuild(self, state):
        clear_box(self.current)

        self.updating_switch = True
        self.switch.set_active(state["enabled"])
        self.switch.set_sensitive(state["hardware_enabled"] and state["wifi_device"] is not None)
        self.updating_switch = False

        wifi = state["wifi"]

        if wifi:
            detail = ["Connected", f"{wifi['strength']}%"]
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
                panel_row(self.library, "wifi", "Wi-Fi", "Connected")
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
            detail = "Connected"

            if state["wired"]["address"]:
                detail += f" · {state['wired']['address']}"

            self.current.append(
                panel_row(self.library, "network-wired", "Wired", detail)
            )

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

        button = Gtk.Button()
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
        self.target = {"network": network, "row": row, "replaces": None}
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
        network = self.target["network"]
        self.busy = True
        self.show_form(
            self.target["row"],
            settings is not None and needs_password(network["security"]),
            f"Connecting to {network['ssid']}…"
        )

        self.control.connect(
            network.get("device") or self.state["wifi_device"],
            network["path"],
            saved_path=saved_path,
            settings=settings,
            replaces=self.target["replaces"],
            on_done=lambda ok, message: self.on_joined(ok, message, saved_path)
        )

    def on_joined(self, ok, message, saved_path):
        self.busy = False

        if self.target is None:
            return

        if ok:
            self.close_form()
            self.read_saved()
            self.refresh()
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

    def on_popover_hidden(self, _popover):
        Gtk4LayerShell.set_keyboard_mode(
            self.get_root(),
            Gtk4LayerShell.KeyboardMode.NONE
        )

        # A join in progress carries on and its result shows in the panel glyph.
        self.close_form()
        self.busy = False


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
    """Battery icon and time left. The popover graphs the draw over the last 3
    hours, 24 hours or 7 days from Tinybar's history file; its arrows (or the
    Left and Right keys) cycle through the three and wrap around."""

    def __init__(self, library, history):
        super().__init__()

        self.library = library
        self.history = history
        self.view = 0

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

        content.add_css_class("notification-popover")
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
        button = Gtk.Button()
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

        self.previous_cpu = None
        self.battery_cpu = None

        self.volume_monitor = None
        self.volume_refresh_source = None

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

        overlay = Gtk.Overlay()

        row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12
        )

        row.set_margin_start(12)
        row.set_margin_end(12)
        row.set_margin_top(5)
        row.set_margin_bottom(5)

        left = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8
        )

        left.set_hexpand(True)

        self.task_list = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4
        )

        self.task_list.add_css_class("task-list")
        left.append(self.task_list)

        self.system_info = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12
        )

        self.system_info.set_halign(
            Gtk.Align.END
        )

        self.icons = IconLibrary()
        self.notifications = NotificationCenter(self.icons)
        self.cpu = StatusIndicator(self.icons, "cpu")
        self.memory = StatusIndicator(self.icons, "memory")
        self.wifi = NetworkMenu(self.icons)
        self.tailscale = None
        if TAILSCALE is True or (TAILSCALE == "auto" and shutil.which("tailscale")):
            self.tailscale = TailscaleButton(self.icons)
        self.brightness = StatusIndicator(
            self.icons,
            "brightness",
            show_value=False
        )
        self.volume = StatusIndicator(
            self.icons,
            "volume",
            show_value=False
        )
        self.battery = BatteryMenu(self.icons, self.history)
        # Desktops and VMs have no battery or backlight: leave those indicators out.
        self.battery.set_visible(HAS_BATTERY)
        self.brightness.set_visible(HAS_BACKLIGHT)

        self.level_overlay = LevelOverlay(self, self.icons)

        widgets = [self.notifications]

        if SHOW_USAGE:
            widgets += [self.cpu, self.memory]

        if self.tailscale:
            widgets.append(self.tailscale)

        widgets += [
            self.wifi,
            self.brightness,
            self.volume,
            self.battery
        ]

        for widget in widgets:
            widget.add_css_class("system-info")
            self.system_info.append(widget)

        row.append(left)
        row.append(self.system_info)

        overlay.set_child(row)

        self.clock = Gtk.Label()
        self.clock.add_css_class("clock")

        self.clock.set_halign(
            Gtk.Align.CENTER
        )

        self.clock.set_valign(
            Gtk.Align.CENTER
        )

        self.clock.set_can_target(False)

        overlay.add_overlay(
            self.clock
        )

        window.set_child(overlay)

        css = Gtk.CssProvider()

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
        self.setup_brightness_monitor()
        self.wifi.setup()

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

            self.task_list.remove(
                self.task_buttons.pop(app_id)
            )

        for position, (app_id, windows) in enumerate(
            self.toplevel_groups.items()
        ):
            button = self.task_buttons.get(app_id)

            if button is None:
                button = Gtk.Button()
                button.add_css_class("task-label")
                button.connect(
                    "clicked",
                    self.on_task_clicked,
                    app_id
                )
                content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                icon = self.icons.application_widget(app_id)
                if icon is not None:
                    content.append(icon)
                button.name_label = Gtk.Label()
                # The first app shows its icon alone when it has one.
                icon_only = app_id == FIRST_APP_ID and icon is not None
                button.name_label.set_visible(not icon_only)
                if icon_only:
                    icon.add_css_class("icon-only")
                content.append(button.name_label)
                button.set_child(content)
                self.task_buttons[app_id] = button
                # A None sibling inserts at the start of the box.
                self.task_list.insert_child_after(
                    button,
                    None if app_id == FIRST_APP_ID
                    else self.task_list.get_last_child()
                )

            count = len(windows)
            label = self.display_name_for_app(app_id)

            if count > 1:
                label = f"{label} ({count})"

            button.name_label.set_text(label)
            button.set_tooltip_text(app_id)

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

        target_id = self.last_active_toplevel.get(app_id)
        target = next(
            (
                window
                for window in windows
                if window["id"] == target_id
            ),
            windows[0]
        )

        if (
            self.active_toplevel is not None
            and self.active_toplevel["app_id"] == app_id
            and len(windows) > 1
        ):
            try:
                index = windows.index(self.active_toplevel)
            except ValueError:
                index = -1

            target = windows[(index + 1) % len(windows)]

        try:
            self.toplevel_helper.stdin.write(
                f"activate {target['id']}\n"
            )
            self.toplevel_helper.stdin.flush()
        except (AttributeError, BrokenPipeError, OSError):
            return

        self.last_active_toplevel[app_id] = target["id"]

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
                    f"CPU {usage:.0f}%"
                )

                self.history.add_sample(
                    "cpu_percent",
                    usage,
                    now
                )

        elif current_cpu is not None:
            self.cpu.set_text(
                "CPU ..."
            )

        self.previous_cpu = current_cpu

        memory = get_memory_usage()

        if memory:
            used, total = memory

            self.memory.set_text(
                f"RAM {used:.1f}/{total:.1f}G"
            )

            self.history.add_sample(
                "memory_used_gib",
                used,
                now
            )

        else:
            self.memory.set_text(
                "RAM ?"
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
                    "/usr/bin/wpctl",
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
        # announce: a key press changed it, so also show the level overlay.
        output = read_path(
            VOLUME_STATE
        )

        if not output:
            self.volume.set_text(
                "VOL ?"
            )
            return

        match = re.search(
            r"Volume:\s+([0-9.]+)",
            output
        )

        muted = "[MUTED]" in output
        percent = None

        if match:
            percent = round(
                float(match.group(1))
                * 100
            )

        if muted:
            self.volume.set_text(
                "VOL MUTED"
            )

        elif percent is not None:
            self.volume.set_text(
                f"VOL {percent}%"
            )

        else:
            self.volume.set_text(
                "VOL ?"
            )
            return

        if announce:
            self.level_overlay.show_level(
                volume_glyph(percent or 0, muted),
                percent or 0,
                "Muted" if muted else None,
                muted
            )

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
                "BRI ?"
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
        self.update_brightness(announce=True)

        return False

    def update_brightness(self, announce=False):
        # announce: the backlight changed, so also show the level overlay.
        if not HAS_BACKLIGHT:
            return
        current = read_path(
            BACKLIGHT / "brightness"
        )

        maximum = read_path(
            BACKLIGHT / "max_brightness"
        )

        try:
            current = int(current)
            maximum = int(maximum)

            if maximum <= 0:
                raise ValueError

            percent = round(
                current / maximum * 100
            )

            percent = max(
                0,
                min(
                    percent,
                    100
                )
            )

            self.brightness.set_text(
                f"BRI {percent}%"
            )

            if announce:
                self.level_overlay.show_level(
                    brightness_glyph(percent),
                    percent
                )

        except (
            TypeError,
            ValueError
        ):
            self.brightness.set_text(
                "BRI ?"
            )


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

        parts = [
            f"BAT {capacity}%"
        ]
        power_text = "— W"
        smoothed_watts = None

        if status == "Charging":
            parts[0] += " +"

        elif status == "Full":
            parts[0] += " FULL"

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

        if (
            status == "Discharging"
            and average_current
            and voltage_now is not None
        ):
            smoothed_watts = (
                average_current
                * voltage_now
                / 1_000_000_000_000
            )

            power_text = f"{smoothed_watts:.1f} W"
            parts.append(power_text)

        trailing_avg, coverage = (
            self.history.trailing_average(
                "power_w",
                now
            )
        )

        if trailing_avg is not None:
            if coverage >= (
                HISTORY_WINDOW_SECONDS
                - BATTERY_SAMPLE_SECONDS
            ):
                parts.append(
                    f"3H {trailing_avg:.1f} W"
                )

            else:
                parts.append(
                    f"AVG {trailing_avg:.1f} W"
                    f" / {format_coverage(coverage)}"
                )

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
                remaining = max(
                    charge_full - charge_now,
                    0
                )

                hours = (
                    remaining
                    / average_current
                )

        runtime_text = format_runtime(
            hours
        )

        if runtime_text:
            if status == "Charging":
                parts.append(
                    f"{runtime_text} to full"
                )

            elif status == "Discharging":
                parts.append(
                    runtime_text
                )

        # CPU and RAM ride along in the hover text, sampled with the battery,
        # so they need no timer of their own and are not recorded. CPU is the
        # average since the previous battery sample.
        current_cpu = read_cpu_counters()
        parts += usage_lines(
            cpu_percent(self.battery_cpu, current_cpu),
            get_memory_usage()
        )
        self.battery_cpu = current_cpu

        parts.append(f"Status: {status}")
        if power_text == "— W":
            parts.append("Battery discharge power unavailable.")

        # The panel shows only the time left (to empty, or to full while
        # charging); percentage and watts stay in the tooltip. Without an
        # estimate yet, or when full, the icon stands alone.
        remaining = None

        if status in ("Discharging", "Charging"):
            remaining = format_hours(hours)

        self.battery.set_text(
            "\n".join(parts),
            display_text=f"BAT {remaining or ''}"
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


# Guarded so the tests can import the pure helpers without starting a panel.
if __name__ == "__main__":
    app = TinyBar()
    raise SystemExit(app.run())
