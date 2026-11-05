"""Check Tinybar's pure display helpers. Imports the panel without starting it."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tinybar  # noqa: E402
from tinybar_icons import IconLibrary, brightness_glyph, signal_glyph, volume_glyph  # noqa: E402
from gi.repository import Gio, GLib  # noqa: E402


def point(ssid, strength, secured=False, frequency=2437):
    return {"ssid": ssid, "strength": strength, "secured": secured, "frequency": frequency}


class NetworkListTests(unittest.TestCase):
    def test_one_row_per_ssid_keeps_strongest(self):
        found = tinybar.visible_networks([
            point("Home", 40, frequency=2437),
            point("Home", 80, frequency=5180),
            point("Cafe", 60),
        ])
        self.assertEqual([n["ssid"] for n in found], ["Home", "Cafe"])
        self.assertEqual(found[0]["strength"], 80)
        self.assertEqual(found[0]["frequency"], 5180)

    def test_secured_if_any_access_point_is(self):
        found = tinybar.visible_networks([point("Home", 80), point("Home", 30, secured=True)])
        self.assertTrue(found[0]["secured"])

    def test_hidden_and_current_networks_are_left_out(self):
        found = tinybar.visible_networks(
            [point("", 90), point("Home", 70), point("Cafe", 20)],
            current_ssid="Home",
        )
        self.assertEqual([n["ssid"] for n in found], ["Cafe"])

    def test_input_is_not_modified(self):
        points = [point("Home", 40), point("Home", 80, secured=True)]
        tinybar.visible_networks(points)
        self.assertEqual(points[0], point("Home", 40))

    def test_equal_strength_sorts_by_name(self):
        found = tinybar.visible_networks([point("beta", 50), point("Alpha", 50)])
        self.assertEqual([n["ssid"] for n in found], ["Alpha", "beta"])

    def test_bands(self):
        self.assertEqual(tinybar.describe_frequency(2437), "2.4 GHz")
        self.assertEqual(tinybar.describe_frequency(5180), "5 GHz")
        self.assertEqual(tinybar.describe_frequency(5955), "6 GHz")
        self.assertIsNone(tinybar.describe_frequency(0))

    def test_ssid_bytes(self):
        self.assertEqual(tinybar.decode_ssid([72, 111, 109, 101]), "Home")
        self.assertEqual(tinybar.decode_ssid(b"\xff"), "�")


class SystemMenuTests(unittest.TestCase):
    def test_mode_row_offers_the_other_mode(self):
        self.assertEqual(tinybar.mode_action("prefer-dark"), ("sun", "Light mode", "light"))
        self.assertEqual(tinybar.mode_action("prefer-light"), ("moon", "Dark mode", "dark"))
        self.assertEqual(tinybar.mode_action("default")[2], "light")

    def test_mode_switch_passes_mode_as_an_argument(self):
        command = tinybar.mode_switch_command("light")
        self.assertEqual(command[:2], ["sh", "-c"])
        self.assertEqual(command[4], "light")
        self.assertIn('limde-appearance --apply --mode "$1"', command[2])
        # pkill -f would match the script's own command line and stop it halfway.
        self.assertNotIn("pkill -f", command[2])

    def test_lock_and_restart_are_shown_first(self):
        keys = [key for key, *_rest in tinybar.SystemMenu.ACTIONS]
        self.assertEqual(tinybar.SystemMenu.SHOWN_FIRST, ("lock", "restart"))
        self.assertLessEqual(set(tinybar.SystemMenu.SHOWN_FIRST), set(keys))

    def test_session_actions_in_order(self):
        commands = {key: command for key, *_rest, command in tinybar.SystemMenu.ACTIONS}
        self.assertEqual(list(commands), ["lock", "suspend", "log-out", "restart", "power-off"])
        self.assertEqual(commands["lock"], ["loginctl", "lock-session"])
        self.assertEqual(commands["suspend"], ["systemctl", "suspend"])
        self.assertEqual(commands["log-out"], ["labwc", "--exit"])
        self.assertEqual(commands["restart"], ["systemctl", "reboot"])
        self.assertEqual(commands["power-off"], ["systemctl", "poweroff"])

    def test_only_ending_the_session_asks_again(self):
        asking = [key for key, _glyph, _title, confirm, _command in tinybar.SystemMenu.ACTIONS
                  if confirm]
        self.assertEqual(asking, ["log-out", "restart", "power-off"])

    def test_second_click_on_the_same_row_acts(self):
        question = "Click again to restart"
        self.assertTrue(tinybar.needs_second_click(None, "restart", question))
        self.assertFalse(tinybar.needs_second_click("restart", "restart", question))
        # Another row asking moves the question; it does not count as the first click.
        self.assertTrue(tinybar.needs_second_click("power-off", "restart", question))
        self.assertFalse(tinybar.needs_second_click(None, "lock", None))
        self.assertFalse(tinybar.needs_second_click("restart", "suspend", None))

    def test_a_double_click_is_not_the_second_click(self):
        too_soon = tinybar.confirms_too_soon
        interval = 400_000  # 400 ms in microseconds
        armed_at = 10_000_000
        self.assertTrue(too_soon("power-off", "power-off", armed_at, armed_at + 150_000, interval))
        self.assertTrue(too_soon("power-off", "power-off", armed_at, armed_at + 399_999, interval))
        self.assertFalse(too_soon("power-off", "power-off", armed_at, armed_at + 400_000, interval))
        self.assertFalse(too_soon("power-off", "power-off", armed_at, armed_at + 2_000_000, interval))
        # Only the row asking waits; a quick click elsewhere is handled as before.
        self.assertFalse(too_soon("power-off", "restart", armed_at, armed_at + 100_000, interval))
        self.assertFalse(too_soon(None, "power-off", 0, armed_at, interval))

    def test_double_click_time_falls_back_to_gtk_default(self):
        with mock.patch.object(tinybar.Gtk.Settings, "get_default", return_value=None):
            self.assertEqual(tinybar.double_click_microseconds(), 400_000)


class BatteryTests(unittest.TestCase):
    def test_decimal_hours(self):
        self.assertEqual(tinybar.format_hours(3.5), "3.5h")
        self.assertEqual(tinybar.format_hours(0.5), "0.5h")
        self.assertEqual(tinybar.format_hours(3 + 20 / 60), "3.3h")
        self.assertIsNone(tinybar.format_hours(None))
        self.assertIsNone(tinybar.format_hours(0))
        self.assertIsNone(tinybar.format_hours(150))

    def test_load_levels(self):
        self.assertIsNone(tinybar.battery_load(None))
        self.assertIsNone(tinybar.battery_load(11.9))
        self.assertEqual(tinybar.battery_load(12), "load-moderate")
        self.assertEqual(tinybar.battery_load(19.9), "load-moderate")
        self.assertEqual(tinybar.battery_load(20), "load-high")
        self.assertEqual(tinybar.battery_load(30), "load-severe")
        self.assertEqual(tinybar.battery_load(55), "load-severe")

    def test_cpu_percent_between_readings(self):
        self.assertIsNone(tinybar.cpu_percent(None, (100, 50)))
        self.assertIsNone(tinybar.cpu_percent((100, 50), None))
        self.assertIsNone(tinybar.cpu_percent((100, 50), (100, 50)))
        self.assertEqual(tinybar.cpu_percent((100, 50), (200, 125)), 25.0)
        self.assertEqual(tinybar.cpu_percent((100, 50), (200, 50)), 100.0)
        self.assertEqual(tinybar.cpu_percent((100, 50), (200, 160)), 0.0)

    def test_usage_lines(self):
        self.assertEqual(
            tinybar.usage_lines(7.4, (2.94, 14.79)),
            ["CPU 7%", "Memory 2.9 of 14.8 GiB"])
        self.assertEqual(tinybar.usage_lines(None, (2.94, 14.79)), ["Memory 2.9 of 14.8 GiB"])
        self.assertEqual(tinybar.usage_lines(12.0, None), ["CPU 12%"])
        self.assertEqual(tinybar.usage_lines(None, None), [])

    def test_usage_rows_for_the_popover(self):
        self.assertEqual(tinybar.usage_rows(7.4, (2.94, 14.79)),
                         [("microchip", "CPU 7%"), ("memory", "Memory 2.9 of 14.8 GiB")])
        self.assertEqual(tinybar.usage_rows(None, None), [])


def warnings_over(readings, warned=None):
    """The thresholds announced over a run of (percent, status) battery readings."""
    announced = []
    for percent, status in readings:
        level, warned = tinybar.battery_warning(percent, status, warned)
        if level is not None:
            announced.append(level)
    return announced


class BatteryWarningTests(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(tinybar.battery_warning(11, "Discharging", None), (None, None))
        self.assertEqual(tinybar.battery_warning(10, "Discharging", None), (10, 10))
        self.assertEqual(tinybar.battery_warning(6, "Discharging", 10), (None, 10))
        self.assertEqual(tinybar.battery_warning(5, "Discharging", 10), (5, 5))

    def test_once_per_discharge(self):
        steps = [(12, "Discharging"), (10, "Discharging"), (10, "Discharging"),
                 (9, "Discharging"), (5, "Discharging"), (4, "Discharging"),
                 (6, "Discharging"), (1, "Discharging")]
        self.assertEqual(warnings_over(steps), [10, 5])

    def test_reset_once_charged_past_the_threshold(self):
        steps = [(9, "Discharging"), (12, "Charging"), (14, "Charging"),
                 (10, "Discharging")]
        self.assertEqual(warnings_over(steps), [10, 10])
        for status in ("Charging", "Full", "Not charging"):
            self.assertEqual(tinybar.battery_warning(14, status, 5), (None, None))
            self.assertEqual(tinybar.battery_warning(4, status, 5), (None, 5))

    def test_charging_past_only_the_critical_one_resets_only_it(self):
        self.assertEqual(tinybar.battery_warning(8, "Charging", 5), (None, 5))
        self.assertEqual(tinybar.battery_warning(9, "Charging", 5), (None, 10))
        steps = [(4, "Discharging"), (9, "Charging"), (5, "Discharging")]
        self.assertEqual(warnings_over(steps), [5, 5])

    def test_a_flapping_charger_does_not_repeat_a_warning(self):
        flapping = [(4, "Discharging"), (4, "Charging"), (4, "Discharging"),
                    (5, "Not charging"), (4, "Discharging"), (5, "Charging"),
                    (4, "Discharging")]
        self.assertEqual(warnings_over(flapping), [5])
        steps = [(10, "Discharging"), (11, "Charging"), (9, "Discharging"),
                 (12, "Charging"), (8, "Discharging")]
        self.assertEqual(warnings_over(steps), [10])

    def test_jump_below_both_gives_only_the_critical_one(self):
        self.assertEqual(warnings_over([(12, "Discharging"), (4, "Discharging")]), [5])

    def test_unknown_status_or_percent_keeps_the_state(self):
        self.assertEqual(tinybar.battery_warning(4, "Unknown", 10), (None, 10))
        self.assertEqual(tinybar.battery_warning(None, "Discharging", 10), (None, 10))
        self.assertEqual(tinybar.battery_warning(None, "Full", 10), (None, 10))
        steps = [(9, "Discharging"), (9, "Unknown"), (9, "Discharging")]
        self.assertEqual(warnings_over(steps), [10])

    def test_text(self):
        self.assertEqual(tinybar.battery_warning_text("10", 10, "25m"),
                         ("Battery at 10%", "About 25m left."))
        self.assertEqual(tinybar.battery_warning_text("10", 10, None),
                         ("Battery at 10%", "Plug in soon."))
        self.assertEqual(tinybar.battery_warning_text("4", 5, None),
                         ("Battery at 4%", "Plug in now."))


def power_record(start, avg, low=None, high=None, coverage=300):
    return {
        "start_epoch": start,
        "duration_seconds": 300,
        "metrics": {"power_w": {
            "avg": avg,
            "min": avg if low is None else low,
            "max": avg if high is None else high,
            "coverage_seconds": coverage,
        }},
    }


class PowerGraphTests(unittest.TestCase):
    NOW = 1_800_000_000 - 1  # one second before a 15-minute boundary

    def test_bins_end_with_the_one_in_progress(self):
        bins, start, end, _summary = tinybar.power_series([], self.NOW, 3600, 900)
        self.assertEqual(end, self.NOW + 1)
        self.assertEqual(start, end - 3600)
        self.assertEqual(bins, [None] * 4)

    def test_records_fill_their_bin_and_gaps_stay_empty(self):
        end = self.NOW + 1
        records = [
            power_record(end - 900, 6.0, 5.0, 9.0),
            power_record(end - 600, 8.0, 7.0, 14.0),
            power_record(end - 3600, 10.0),
        ]
        bins, _start, _end, summary = tinybar.power_series(records, self.NOW, 3600, 900)
        self.assertEqual(bins[0], (10.0, 10.0, 10.0))
        self.assertIsNone(bins[1])
        self.assertIsNone(bins[2])
        self.assertEqual(bins[3], (7.0, 5.0, 14.0))
        avg, peak, covered = summary
        self.assertAlmostEqual(avg, 8.0)
        self.assertEqual(peak, 14.0)
        self.assertEqual(covered, 900)

    def test_average_weights_by_time_on_battery(self):
        end = self.NOW + 1
        records = [
            power_record(end - 900, 6.0, coverage=300),
            power_record(end - 600, 12.0, coverage=100),
        ]
        bins, *_ = tinybar.power_series(records, self.NOW, 900, 900)
        self.assertAlmostEqual(bins[0][0], 7.5)

    def test_unflushed_samples_count(self):
        end = self.NOW + 1
        bins, *_rest, summary = tinybar.power_series(
            [], self.NOW, 900, 900, (end - 300, [4.0, 8.0])
        )
        self.assertEqual(bins[0], (6.0, 4.0, 8.0))
        self.assertEqual(summary[2], 2 * tinybar.BATTERY_SAMPLE_SECONDS)

    def test_old_and_other_records_are_ignored(self):
        records = [
            power_record(self.NOW - 2 * 86400, 9.0),
            {"start_epoch": self.NOW - 300, "metrics": {"temperature_c": {"avg": 50}}},
        ]
        _bins, _start, _end, summary = tinybar.power_series(records, self.NOW, 3600, 300)
        self.assertEqual(summary, (None, None, 0))
        self.assertEqual(
            tinybar.power_summary(summary, "3 hours"),
            "No battery use in the last 3 hours",
        )

    def test_summary_text(self):
        self.assertEqual(
            tinybar.power_summary((6.84, 14.2, 9600), "24 hours"),
            "Avg 6.8 W · Peak 14.2 W · 2h 40m on battery",
        )

    def test_grid_on_local_hours_and_midnights(self):
        start = self.NOW - 7 * 86400
        days = tinybar.power_grid(start, self.NOW, 24)
        self.assertEqual(len(days), 7)
        for moment, label in days:
            local = tinybar.datetime.datetime.fromtimestamp(moment)
            self.assertEqual((local.hour, local.minute), (0, 0))
            self.assertEqual(label, local.strftime("%a"))
        hours = tinybar.power_grid(self.NOW - 3 * 3600, self.NOW, 1)
        self.assertEqual(len(hours), 3)
        self.assertTrue(all(label.endswith(":00") for _moment, label in hours))


class GlyphTests(unittest.TestCase):
    def test_brightness_steps(self):
        self.assertEqual(brightness_glyph(1), "brightness-low")
        self.assertEqual(brightness_glyph(33), "brightness-low")
        self.assertEqual(brightness_glyph(34), "brightness")
        self.assertEqual(brightness_glyph(66), "brightness")
        self.assertEqual(brightness_glyph(67), "sun-bright")
        self.assertEqual(brightness_glyph(100), "sun-bright")

    def test_volume_steps(self):
        self.assertEqual(volume_glyph(0), "volume-off")
        self.assertEqual(volume_glyph(49), "volume-low")
        self.assertEqual(volume_glyph(50), "volume-high")
        self.assertEqual(volume_glyph(80, muted=True), "volume-xmark")

    def test_signal_steps(self):
        self.assertEqual(signal_glyph(34), "wifi-weak")
        self.assertEqual(signal_glyph(35), "wifi-fair")
        self.assertEqual(signal_glyph(65), "wifi")


class TailscaleViewTests(unittest.TestCase):
    def test_connected_and_off_icons_and_actions(self):
        self.assertEqual(tinybar.tailscale_view("Running")[::2], ("tailscale", "down"))
        self.assertEqual(tinybar.tailscale_view("Stopped")[::2], ("tailscale-slash", "up"))

    def test_states_a_click_cannot_fix_do_nothing(self):
        for state in ("NeedsLogin", "NeedsMachineAuth", None, "NoState"):
            self.assertIsNone(tinybar.tailscale_view(state)[2], state)

    def test_error_follows_the_state_in_the_tooltip(self):
        tooltip = tinybar.tailscale_view("Stopped", "Not allowed")[1]
        self.assertEqual(tooltip.splitlines(), ["Tailscale: off (click to turn on)", "Not allowed"])

    def test_error_reasons(self):
        self.assertIn("--operator", tinybar.tailscale_error(
            "Access denied: prefs write access denied\nUse 'sudo tailscale up'"))
        self.assertIn("keeps trying", tinybar.tailscale_error("", timed_out=True))
        self.assertEqual(tinybar.tailscale_error("a\nlast line"), "last line")
        self.assertEqual(tinybar.tailscale_error(""), "The tailscale command failed.")


class IdleHideTests(unittest.TestCase):
    def window(self, wid, app_id, **state):
        return {"id": wid, "app_id": app_id, "title": "", **state}

    def test_hides_bottom_of_the_stack_first(self):
        windows = [self.window(1, "foot"), self.window(2, "firefox"), self.window(3, "pcmanfm")]
        order = tinybar.idle_hide_order(windows, focus_order=[3, 1], keep=set())
        self.assertEqual([w["id"] for w in order], [2, 3, 1])

    def test_leaves_kept_minimised_dialog_and_panel_windows(self):
        windows = [
            self.window(1, "com.freerdp.client.sdl3"),
            self.window(2, "foot", minimized=True),
            self.window(3, "firefox", parent=True),
            self.window(4, "tinybar"),
            self.window(5, "firefox"),
        ]
        order = tinybar.idle_hide_order(windows, [], keep={"com.freerdp.client.sdl3"})
        self.assertEqual([w["id"] for w in order], [5])

    def test_leaves_the_panel_whatever_the_case_of_its_app_id(self):
        windows = [self.window(1, "limde.Tinybar"), self.window(2, "LIMDE.TINYBAR"),
                   self.window(3, "foot")]
        order = tinybar.idle_hide_order(windows, [], keep=set())
        self.assertEqual([w["id"] for w in order], [3])


class TaskListTests(unittest.TestCase):
    def snapshot(self, windows):
        # apply_toplevel_snapshot without a running panel: only the state it reads and writes.
        panel = mock.Mock(focus_order=[], last_active_toplevel={})
        tinybar.TinyBar.apply_toplevel_snapshot(panel, windows)
        panel.render_task_list.assert_called_once_with()
        return panel

    def test_app_ids_are_stored_casefolded(self):
        # Both checks casefold the window's app ID, so a capital here never matches.
        self.assertEqual(tinybar.TINYBAR_APP_IDS, {i.casefold() for i in tinybar.TINYBAR_APP_IDS})

    def test_panel_windows_are_not_listed(self):
        panel = self.snapshot([
            {"id": 1, "app_id": "limde.Tinybar", "title": "Panel"},
            {"id": 2, "app_id": "Tinybar", "title": ""},
            {"id": 3, "app_id": "something", "title": "tinybar"},
            {"id": 4, "app_id": "foot", "title": "Terminal", "active": True},
            {"id": 5, "app_id": "foot", "title": "Dialog", "parent": 4},
        ])
        self.assertEqual(list(panel.toplevel_groups), ["foot"])
        self.assertEqual([w["id"] for w in panel.toplevel_groups["foot"]], [4])
        self.assertEqual(panel.active_toplevel["id"], 4)
        self.assertEqual(panel.last_active_toplevel, {"foot": 4})


class WifiJoinTests(unittest.TestCase):
    def test_security_kinds(self):
        security = tinybar.wifi_security
        self.assertEqual(security(0, 0, 0), "open")
        self.assertEqual(security(1, 0, 0), "wep")
        self.assertEqual(security(1, 0, 0x100), "psk")
        self.assertEqual(security(1, 0, 0x500), "psk")  # WPA2/WPA3 transition
        self.assertEqual(security(1, 0, 0x400), "sae")
        self.assertEqual(security(1, 0, 0x200), "enterprise")
        self.assertEqual(security(0, 0, 0x800), "owe")

    def test_settings_for_new_networks(self):
        self.assertEqual(tinybar.wifi_settings("open"), {})
        self.assertEqual(
            tinybar.wifi_settings("psk", "hunter22"),
            {"802-11-wireless-security": {"key-mgmt": "wpa-psk", "psk": "hunter22"}},
        )
        self.assertEqual(
            tinybar.wifi_settings("sae", "x")["802-11-wireless-security"]["key-mgmt"], "sae"
        )
        self.assertIsNone(tinybar.wifi_settings("enterprise", "x"))
        self.assertIsNone(tinybar.wifi_settings("wep", "x"))

    def test_password_checks(self):
        problem = tinybar.password_problem
        self.assertEqual(problem("psk", ""), "Enter the password")
        self.assertIsNotNone(problem("psk", "short"))
        self.assertIsNone(problem("psk", "eight888"))
        self.assertIsNone(problem("psk", "a" * 64))  # a raw 64-hex-digit key
        self.assertIsNotNone(problem("psk", "g" * 64))
        self.assertIsNone(problem("sae", "short"))

    def test_failure_words(self):
        self.assertEqual(tinybar.connect_failure(9), "Wrong password")
        self.assertEqual(tinybar.connect_failure(10), "Wrong password")
        self.assertEqual(tinybar.connect_failure(6), "The network did not answer")
        self.assertEqual(tinybar.connect_failure(3), "Could not connect")
        self.assertEqual(tinybar.device_failure(7), "Wrong password")
        self.assertEqual(tinybar.device_failure(53), "The network is out of range")
        self.assertEqual(tinybar.device_failure(8), "Could not connect")

    def test_strongest_access_point_is_the_one_joined(self):
        weak = dict(point("Home", 30, secured=True), path="/ap/1", security="psk")
        strong = dict(point("Home", 70, secured=False), path="/ap/2", security="psk")
        found = tinybar.visible_networks([weak, strong])
        self.assertEqual(found[0]["path"], "/ap/2")
        self.assertTrue(found[0]["secured"])


# `pw-dump --monitor --no-colors` output, cut down to the fields that matter: the first
# batch (a laptop's card with speakers and HDMI, a playing stream, a client, two metadata
# objects), the default output moving to HDMI, then HDMI and the client going away.
PW_DUMP = b"""[
  { "id": 44, "type": "PipeWire:Interface:Device", "version": 3, "info": { "change-mask": [ "props", "params" ],
    "props": { "device.api": "alsa", "device.description": "Built-in Audio", "media.class": "Audio/Device" },
    "params": { "Route": [ { "index": 0, "direction": "Output", "name": "analog-output-speaker" } ] } } },
  { "id": 59, "type": "PipeWire:Interface:Node", "version": 3, "info": { "state": "suspended", "error": null,
    "props": { "device.id": 44, "media.class": "Audio/Sink", "node.description": "Built-in Audio Analog Stereo",
      "node.name": "alsa_output.pci-0000_00_1f.3.analog-stereo", "node.nick": "ALC289 Analog" },
    "params": { "Props": [ { "volume": 1.0, "mute": false, "channelVolumes": [ 1.0, 1.0 ] } ] } } },
  { "id": 61, "type": "PipeWire:Interface:Node", "version": 3, "info": { "state": "suspended", "props": {
    "media.class": "Audio/Sink", "node.description": "Built-in Audio Digital Stereo (HDMI)",
    "node.name": "alsa_output.pci-0000_00_1f.3.hdmi-stereo" } } },
  { "id": 70, "type": "PipeWire:Interface:Node", "version": 3, "info": { "state": "running",
    "props": { "application.name": "Firefox", "media.class": "Stream/Output/Audio", "node.name": "Firefox" } } },
  { "id": 65, "type": "PipeWire:Interface:Client", "version": 3, "info": { "change-mask": [ "props" ],
    "props": { "application.name": "wpctl" } } },
  { "id": 32, "type": "PipeWire:Interface:Metadata", "version": 3, "props": { "metadata.name": "settings" },
    "metadata": [ { "subject": 0, "key": "clock.rate", "type": "", "value": 48000 } ] },
  { "id": 41, "type": "PipeWire:Interface:Metadata", "version": 3, "props": { "metadata.name": "default" },
    "metadata": [
      { "subject": 0, "key": "default.audio.sink", "type": "Spa:String:JSON",
        "value": { "name": "alsa_output.pci-0000_00_1f.3.analog-stereo" } },
      { "subject": 0, "key": "default.audio.source", "type": "Spa:String:JSON",
        "value": { "name": "alsa_input.pci-0000_00_1f.3.analog-stereo" } } ] }
]
[
  { "id": 41, "type": "PipeWire:Interface:Metadata", "version": 3, "props": { "metadata.name": "default" },
    "metadata": [ { "subject": 0, "key": "default.audio.sink", "type": "Spa:String:JSON",
      "value": { "name": "alsa_output.pci-0000_00_1f.3.hdmi-stereo" } } ] }
]
[
  {
    "id": 61,
    "info": null
  },
  {
    "id": 65,
    "info": null
  }
]
"""


class VolumeTests(unittest.TestCase):
    def test_wpctl_get_volume(self):
        self.assertEqual(tinybar.parse_volume("Volume: 0.40"), (40, False))
        self.assertEqual(tinybar.parse_volume("Volume: 0.10 [MUTED]\nkey"), (10, True))
        self.assertEqual(tinybar.parse_volume("Volume: 1.00"), (100, False))
        self.assertIsNone(tinybar.parse_volume(None))
        self.assertIsNone(tinybar.parse_volume("Translate ID error: default sink not found"))

    def test_batches_split_wherever_the_pipe_breaks(self):
        whole, rest = tinybar.split_dump(PW_DUMP)
        self.assertEqual((rest, [item["id"] for item in whole]),
                         (b"", [44, 59, 61, 70, 65, 32, 41, 41, 61, 65]))
        for size in (1, 7, 100, 4096):
            objects, rest = [], b""
            for start in range(0, len(PW_DUMP), size):
                found, rest = tinybar.split_dump(rest + PW_DUMP[start:start + size])
                objects += found
            self.assertEqual(objects, whole, size)

    def test_unfinished_and_broken_batches(self):
        self.assertEqual(tinybar.split_dump(b'[\n  { "id": 1'), ([], b'[\n  { "id": 1'))
        self.assertEqual(tinybar.split_dump(b'[\n  {\n]\n[\n  { "id": 2, "info": null }\n]\n['),
                         ([{"id": 2, "info": None}], b"["))

    def test_outputs_and_default_follow_the_batches(self):
        first, moved, removed = (tinybar.split_dump(part + b"\n]\n")[0]
                                 for part in PW_DUMP.split(b"\n]\n")[:3])
        audio = tinybar.new_audio_state()
        self.assertTrue(tinybar.apply_audio_objects(audio, first))
        self.assertEqual(audio["watched"], {44, 41})
        self.assertEqual(tinybar.audio_outputs(audio), [
            (59, "Built-in Audio Analog Stereo", True),
            (61, "Built-in Audio Digital Stereo (HDMI)", False),
        ])
        self.assertTrue(tinybar.apply_audio_objects(audio, moved))
        self.assertEqual([output[2] for output in tinybar.audio_outputs(audio)], [False, True])
        self.assertTrue(tinybar.apply_audio_objects(audio, removed))
        self.assertEqual(tinybar.audio_outputs(audio), [(59, "Built-in Audio Analog Stereo", False)])

    def test_clients_streams_and_other_metadata_change_nothing(self):
        audio = tinybar.new_audio_state()
        others = [item for item in tinybar.split_dump(PW_DUMP)[0] if item["id"] in (70, 65, 32)]
        self.assertFalse(tinybar.apply_audio_objects(audio, others))
        self.assertFalse(tinybar.apply_audio_objects(audio, [{"id": 65, "info": None}]))
        self.assertEqual(audio, tinybar.new_audio_state())

    def test_microphones_leave_out_monitors_and_follow_the_default(self):
        def node(key, media_class, name, description=None, **props):
            props.update({"media.class": media_class, "node.name": name})
            if description:
                props["node.description"] = description
            return {"id": key, "type": "PipeWire:Interface:Node", "info": {"props": props}}

        audio = tinybar.new_audio_state()
        self.assertTrue(tinybar.apply_audio_objects(audio, [
            node(80, "Audio/Source", "alsa_input.pci-0000_00_1f.3.analog-stereo",
                 "Built-in Audio Analog Stereo"),
            node(81, "Audio/Source/Virtual", "testmic"),
            node(82, "Audio/Source", "alsa_output.hdmi-stereo.monitor", "Monitor of HDMI"),
            node(83, "Audio/Source", "loopback", "Loopback", **{"stream.monitor": "true"}),
            node(84, "Stream/Input/Audio", "Firefox"),
        ]))
        self.assertEqual(tinybar.audio_inputs(audio), [
            (80, "Built-in Audio Analog Stereo", False),
            (81, "testmic", False),
        ])
        self.assertEqual(tinybar.audio_outputs(audio), [])

        # The first dump's default metadata names both defaults.
        default = [item for item in tinybar.split_dump(PW_DUMP)[0] if item["id"] == 41][0]
        tinybar.apply_audio_objects(audio, [default])
        self.assertEqual([mic[2] for mic in tinybar.audio_inputs(audio)], [True, False])
        self.assertEqual(audio["default"], "alsa_output.pci-0000_00_1f.3.analog-stereo")

        self.assertEqual(tinybar.default_microphone(audio), 80)

        self.assertTrue(tinybar.apply_audio_objects(audio, [{"id": 80, "info": None}]))
        self.assertEqual(tinybar.audio_inputs(audio), [(81, "testmic", False)])
        self.assertIsNone(tinybar.default_microphone(audio))

    def test_an_output_monitor_as_default_source_is_no_microphone(self):
        # WirePlumber's choice with no microphone: the output's name, i.e. its monitor.
        audio = tinybar.new_audio_state()
        tinybar.apply_audio_objects(audio, [
            {"id": 40, "type": "PipeWire:Interface:Node", "info": {"props": {
                "media.class": "Audio/Sink", "node.name": "auto_null",
                "node.description": "Dummy Output"}}},
            {"id": 53, "type": "PipeWire:Interface:Node", "info": {"props": {
                "media.class": "Audio/Source/Virtual", "node.name": "testmic"}}},
            {"id": 41, "type": "PipeWire:Interface:Metadata", "props": {"metadata.name": "default"},
             "metadata": [{"subject": 0, "key": "default.audio.source",
                           "value": {"name": "auto_null"}}]},
        ])
        self.assertIsNone(tinybar.default_microphone(audio))
        self.assertEqual(tinybar.audio_inputs(audio), [(53, "testmic", False)])

    def test_picking_a_microphone_names_it_in_the_metadata(self):
        self.assertEqual(tinybar.default_source_command('my "mic"'), [
            "/usr/bin/pw-metadata", "-n", "default", "0", "default.configured.audio.source",
            '{"name": "my \\"mic\\""}', "Spa:String:JSON"])

    def test_microphone_glyph(self):
        self.assertEqual(tinybar.microphone_glyph(80), "microphone")
        self.assertEqual(tinybar.microphone_glyph(80, muted=True), "microphone-slash")

    def test_monitor_retries_back_off_and_never_give_up(self):
        delays, delay = [], 0
        # PipeWire stays down: every pw-dump quits at once.
        for _attempt in range(7):
            delay = tinybar.audio_monitor_delay(0.1, delay)
            delays.append(delay)
        self.assertEqual(delays, [5, 10, 20, 40, 60, 60, 60])
        # Once one runs a while, the next restart waits the base time again.
        self.assertEqual(tinybar.audio_monitor_delay(600, 60), 5)
        self.assertEqual(tinybar.audio_monitor_delay(600, 0), 5)


class FakeJoinMenu:
    """NetworkMenu's joining code on a stand-in with no widgets: the form is a record
    of what it would show, and NetworkManager a list of connect calls to answer."""

    on_network_clicked = tinybar.NetworkMenu.on_network_clicked
    join = tinybar.NetworkMenu.join
    on_joined = tinybar.NetworkMenu.on_joined
    on_popover_hidden = tinybar.NetworkMenu.on_popover_hidden

    def __init__(self, saved):
        self.saved = saved
        self.state = {"wifi_device": "/dev/wlan0"}
        self.target = None
        self.busy = False
        self.visible = True
        self.form = None
        self.joins = []
        self.control = mock.Mock()
        self.control.connect.side_effect = lambda *args, **kwargs: self.joins.append(kwargs)

    def get_popover(self):
        return mock.Mock(get_visible=lambda: self.visible)

    def get_root(self):
        return None

    def show_form(self, row, asking, message=None):
        self.form = (row, asking, message)

    def close_form(self):
        self.form = None
        self.target = None

    def read_saved(self):
        pass

    def refresh(self):
        pass


def wifi_network(ssid, security="psk"):
    return dict(point(ssid, 70, secured=security != "open"), path=f"/ap/{ssid}",
                security=security)


class WifiJoinRaceTests(unittest.TestCase):
    def setUp(self):
        layer_shell = mock.patch.object(tinybar, "Gtk4LayerShell")
        layer_shell.start()
        self.addCleanup(layer_shell.stop)
        self.menu = FakeJoinMenu({"Home": "/saved/home"})
        self.home, self.work = wifi_network("Home"), wifi_network("Work")

    def test_closing_the_popover_keeps_the_join_and_its_result(self):
        menu = self.menu
        menu.on_network_clicked("home-row", self.home)
        menu.visible = False
        menu.on_popover_hidden(None)
        self.assertTrue(menu.busy)
        self.assertEqual(menu.form, ("home-row", False, "Connecting to Home…"))

        # Reopened mid-join: another network cannot be started over it.
        menu.visible = True
        menu.on_network_clicked("work-row", self.work)
        self.assertEqual(len(menu.joins), 1)

        menu.joins[0]["on_done"](False, "Wrong password")
        self.assertFalse(menu.busy)
        self.assertEqual(menu.target["network"]["ssid"], "Home")
        self.assertEqual(menu.target["replaces"], "/saved/home")
        self.assertEqual(menu.form[:2], ("home-row", True))

    def test_a_result_after_the_popover_closed_resets_the_form(self):
        menu = self.menu
        menu.on_network_clicked("home-row", self.home)
        menu.visible = False
        menu.on_popover_hidden(None)
        menu.joins[0]["on_done"](False, "Wrong password")
        self.assertEqual((menu.busy, menu.target, menu.form), (False, None, None))

    def test_a_stale_result_touches_nothing(self):
        menu = self.menu
        menu.saved["Work"] = "/saved/work"
        menu.on_network_clicked("home-row", self.home)
        # The Wi-Fi switch closes the form; its call's end clears busy.
        menu.close_form()
        menu.busy = False
        menu.on_network_clicked("work-row", self.work)
        work = menu.target
        self.assertEqual(len(menu.joins), 2)

        for ok, message in ((False, "Wrong password"), (True, None)):
            menu.joins[0]["on_done"](ok, message)
            self.assertIs(menu.target, work)
            self.assertTrue(menu.busy)
            self.assertIsNone(work["replaces"])
            self.assertEqual(menu.form, ("work-row", False, "Connecting to Work…"))

        menu.joins[1]["on_done"](True, None)
        self.assertEqual((menu.busy, menu.target), (False, None))


def network(wifi=None, wifi_connected=False, wired=None, device="/d/1", enabled=True,
            hardware=True, portal=None):
    """A NetworkMenu.read_state result."""
    return {"wifi": wifi, "wifi_connected": wifi_connected or wifi is not None,
            "wired": wired, "wifi_device": device, "enabled": enabled,
            "hardware_enabled": hardware, "nearby": [], "portal": portal}


class CaptivePortalTests(unittest.TestCase):
    CHECK = "http://connectivity-check.ubuntu.com/"

    def test_sign_in_page_is_the_check_address_over_http(self):
        self.assertEqual(tinybar.portal_url(self.CHECK), self.CHECK)
        self.assertEqual(tinybar.portal_url("https://check.example/hotspot.txt"),
                         "http://check.example/hotspot.txt")
        self.assertEqual(tinybar.portal_url("HTTP://check.example/"), "http://check.example/")
        for unusable in ("", None, "check.example", "ftp://check.example/", "http://"):
            self.assertIsNone(tinybar.portal_url(unusable))

    def test_tooltip_says_so(self):
        hotel = {**point("Hotel", 70), "address": None}
        self.assertEqual(tinybar.network_tooltip(network(hotel, portal=self.CHECK)),
                         "Wi-Fi: Hotel, 70% signal, sign-in needed")
        self.assertEqual(tinybar.network_tooltip(network(wired={"address": None},
                                                         portal=self.CHECK)),
                         "Wired: connected, sign-in needed")
        # Not connected: nothing to sign in to.
        self.assertEqual(tinybar.network_tooltip(network(portal=self.CHECK)),
                         "Wi-Fi: not connected")

    def test_notice_names_the_network(self):
        hotel = {**point("Hotel", 70), "address": None}
        summary, body = tinybar.portal_notice(network(hotel, portal=self.CHECK))
        self.assertEqual(summary, "Sign-in needed")
        self.assertTrue(body.startswith("Hotel asks you to sign in"))
        self.assertEqual(tinybar.portal_name(network({**hotel, "ssid": ""})),
                         "The Wi-Fi network")
        self.assertEqual(tinybar.portal_name(network(wired={"address": None})),
                         "The wired network")


class BrightnessSliderTests(unittest.TestCase):
    def test_percent_from_sysfs(self):
        self.assertEqual(tinybar.brightness_percent("38400", "96000"), 40)
        self.assertEqual(tinybar.brightness_percent("960", "96000"), 1)
        self.assertEqual(tinybar.brightness_percent("0", "96000"), 0)
        self.assertEqual(tinybar.brightness_percent("97000", "96000"), 100)
        self.assertIsNone(tinybar.brightness_percent(None, "96000"))
        self.assertIsNone(tinybar.brightness_percent("5", "0"))
        self.assertIsNone(tinybar.brightness_percent("x", "96000"))

    def test_slider_changes_show_no_overlay(self):
        # The keys' changes do; the slider's (while sending, and just after) do not.
        self.assertTrue(tinybar.brightness_change_announced(10.0, 0.0, False))
        self.assertFalse(tinybar.brightness_change_announced(10.0, 0.0, True))
        self.assertFalse(tinybar.brightness_change_announced(10.0, 10.4, False))
        self.assertTrue(tinybar.brightness_change_announced(10.5, 10.4, False))

    def test_slider_needs_brightnessctl(self):
        with mock.patch.object(tinybar, "BRIGHTNESSCTL", "/nonexistent/brightnessctl"):
            self.assertFalse(tinybar.can_set_brightness())
        with mock.patch.object(tinybar, "BRIGHTNESSCTL", "/bin/sh"):
            self.assertTrue(tinybar.can_set_brightness())

    def test_command_is_the_keys_command(self):
        self.assertEqual(Path(tinybar.brightness_command()).name, "tinybar-brightness")
        with mock.patch.object(tinybar, "BRIGHTNESS_COMMAND", Path("/nonexistent/tinybar-brightness")), \
                mock.patch.object(tinybar.shutil, "which", return_value=None):
            self.assertEqual(tinybar.brightness_command(), "/usr/local/bin/tinybar-brightness")


class FakeMenu:
    """A panel menu button for PanelMenus: popup and popdown report back as GTK's
    show and hide signals do."""

    def __init__(self, menus):
        self.menus = menus
        self.showing = False

    def popup(self):
        self.showing = True
        self.menus.shown(self)

    def popdown(self):
        if self.showing:
            self.showing = False
            self.menus.hidden(self)

    def get_has_tooltip(self):
        return False

    def get_first_child(self):
        return None

    def get_native(self):
        return None

    def get_popover(self):
        return self


class PanelMenuTests(unittest.TestCase):
    """One click on another panel button swaps popovers (PanelMenus)."""

    def setUp(self):
        self.pending = []
        self.menus = tinybar.PanelMenus(
            later=lambda _seconds, callback: self.pending.append(callback))
        self.cog, self.battery = FakeMenu(self.menus), FakeMenu(self.menus)

    def run_later(self):
        for callback in self.pending:
            callback()
        self.pending.clear()

    def click(self, menu):
        """A click on menu's button: GTK closes the open popover and drops the press;
        with nothing open, the button opens its own."""
        self.menus.entered(menu)
        if self.menus.open is not None:
            self.menus.open.popdown()
        else:
            menu.popup()
        self.run_later()

    def test_one_click_swaps(self):
        self.click(self.cog)
        self.click(self.battery)
        self.assertFalse(self.cog.showing)
        self.assertTrue(self.battery.showing)

    def test_clicking_the_open_buttons_closes(self):
        self.click(self.cog)
        self.click(self.cog)
        self.assertFalse(self.cog.showing)

    def test_pointing_opens_nothing(self):
        self.click(self.cog)
        self.menus.entered(self.battery)
        self.run_later()
        self.assertTrue(self.cog.showing)
        self.assertFalse(self.battery.showing)

    def test_closing_elsewhere_opens_nothing(self):
        self.click(self.cog)
        self.menus.entered(self.battery)
        self.menus.left(self.battery)
        self.cog.popdown()  # a click in another window
        self.run_later()
        self.assertFalse(self.battery.showing)

    def test_escape_opens_nothing(self):
        self.click(self.cog)
        self.menus.entered(self.battery)
        self.menus.escaping = True
        self.cog.popdown()
        self.run_later()
        self.assertFalse(self.battery.showing)

    def test_pointer_gone_before_the_switch_opens_nothing(self):
        self.click(self.cog)
        self.menus.entered(self.battery)
        self.cog.popdown()
        self.menus.left(self.battery)
        self.run_later()
        self.assertFalse(self.battery.showing)


class CalendarTests(unittest.TestCase):
    def test_heading(self):
        import datetime
        self.assertEqual(tinybar.calendar_heading(datetime.date(2026, 11, 2)),
                         "Monday, November 2, 2026")

    def test_today_button_only_away_from_today(self):
        import datetime
        today = datetime.date(2026, 11, 2)
        self.assertTrue(tinybar.calendar_shows_today(2026, 11, 2, today))
        self.assertFalse(tinybar.calendar_shows_today(2026, 12, 2, today))
        self.assertFalse(tinybar.calendar_shows_today(2027, 11, 2, today))
        self.assertFalse(tinybar.calendar_shows_today(2026, 11, 3, today))


class TooltipTests(unittest.TestCase):
    """Hover words are plain phrases, never the state strings the icons are picked from."""

    def test_network(self):
        home = {**point("Home", 61), "address": "192.0.2.5"}
        self.assertEqual(tinybar.network_tooltip(network(home)), "Wi-Fi: Home, 61% signal")
        self.assertEqual(tinybar.network_tooltip(network({**home, "ssid": ""})),
                         "Wi-Fi: hidden network, 61% signal")
        self.assertEqual(tinybar.network_tooltip(network(home, wired={"address": None})),
                         "Wi-Fi: Home, 61% signal")
        self.assertEqual(tinybar.network_tooltip(network(wifi_connected=True)), "Wi-Fi: connected")
        self.assertEqual(tinybar.network_tooltip(network(wired={"address": None}, enabled=False)),
                         "Wired: connected")
        self.assertEqual(tinybar.network_tooltip(network(enabled=False)), "Wi-Fi: off")
        self.assertEqual(tinybar.network_tooltip(network(hardware=False)),
                         "Wi-Fi: off by the hardware switch")
        self.assertEqual(tinybar.network_tooltip(network()), "Wi-Fi: not connected")
        self.assertEqual(tinybar.network_tooltip(network(device=None)), "Wi-Fi: no Wi-Fi device")
        self.assertEqual(tinybar.network_tooltip(None), "Network: status unavailable")

    def test_volume_and_brightness(self):
        self.assertEqual(tinybar.volume_tooltip((65, False)), "Volume 65%")
        self.assertEqual(tinybar.volume_tooltip((65, True)), "Volume: muted")
        self.assertEqual(tinybar.volume_tooltip(None), "Volume: unavailable")
        # The microphone is named only while muted.
        self.assertEqual(tinybar.volume_tooltip((65, False), (80, False)), "Volume 65%")
        self.assertEqual(tinybar.volume_tooltip((65, False), (80, True)),
                         "Volume 65%, microphone muted")
        self.assertEqual(tinybar.volume_tooltip((65, True), (80, True)),
                         "Volume: muted, microphone muted")
        self.assertEqual(tinybar.volume_tooltip(None, (0, False)), "Volume: unavailable")
        self.assertEqual(tinybar.brightness_tooltip(40), "Brightness 40%")
        self.assertEqual(tinybar.brightness_tooltip(None), "Brightness: unavailable")

    def test_battery_level_and_time(self):
        tooltip = tinybar.battery_tooltip
        self.assertEqual(tooltip(64, "Discharging", "2h 10m"), "Battery 64%, 2h 10m left")
        self.assertEqual(tooltip(64, "Discharging"), "Battery 64%, discharging")
        self.assertEqual(tooltip(64, "Charging", "1h 05m"), "Battery 64%, charging, full in 1h 05m")
        self.assertEqual(tooltip(64, "Charging"), "Battery 64%, charging")
        self.assertEqual(tooltip(100, "Full"), "Battery 100%, charged")
        self.assertEqual(tooltip(80, "Not charging"), "Battery 80%, plugged in, not charging")
        self.assertEqual(tooltip(80, "Unknown"), "Battery 80%")
        self.assertEqual(tooltip(None, "Unknown"), "Battery level unknown")

    def test_charge_limit_text(self):
        text = tinybar.charge_limit_text
        # Keith's laptop: plugged in, held at its 80 % limit (start 50).
        self.assertEqual(text("Not charging", 80, 80, 50), "Held at 80%")
        self.assertEqual(text("Not charging", 79, 80, 50), "Held at 80%")
        self.assertEqual(text("Not charging", 78, 80), "Held at 80%")
        self.assertEqual(text("Full", 80, 80), "Held at 80%")
        self.assertEqual(text("Charging", 64, 80, 50), "Charging to 80%")
        # Between the thresholds the firmware waits for the start one.
        self.assertEqual(text("Not charging", 70, 80, 50), "Not charging until below 50%")
        # Well below the limit with no start threshold (or under it): some other
        # cause, so the limit is only stated.
        self.assertEqual(text("Not charging", 60, 80), "Charge limit 80%")
        self.assertEqual(text("Not charging", 40, 80, 50), "Charge limit 80%")
        self.assertEqual(text("Not charging", None, 80), "Charge limit 80%")
        self.assertEqual(text("Discharging", 64, 80, 50), "Charge limit 80%")
        # No threshold file: nothing.
        for status in ("Not charging", "Charging", "Discharging", "Full"):
            self.assertIsNone(text(status, 80, None))

    def test_read_charge_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            battery = Path(folder)
            with mock.patch.object(tinybar, "BATTERY", battery):
                self.assertEqual(tinybar.read_charge_limit(), (None, None))
                (battery / "charge_control_end_threshold").write_text("80\n")
                self.assertEqual(tinybar.read_charge_limit(), (80, None))
                (battery / "charge_control_start_threshold").write_text("50\n")
                self.assertEqual(tinybar.read_charge_limit(), (80, 50))
                # 100 % is no limit; a start at or over the end is ignored.
                (battery / "charge_control_end_threshold").write_text("100\n")
                self.assertEqual(tinybar.read_charge_limit(), (None, None))
                (battery / "charge_control_end_threshold").write_text("50\n")
                self.assertEqual(tinybar.read_charge_limit(), (50, None))

    def test_battery_tooltip_with_charge_limit(self):
        # One line; what the limit is doing is in the popover (battery_rows).
        tooltip = tinybar.battery_tooltip
        self.assertEqual(tooltip(80, "Not charging", end=80, start=50), "Battery 80%, plugged in")
        self.assertEqual(tooltip(64, "Charging", "40m", end=80),
                         "Battery 64%, charging to 80% in 40m")
        self.assertEqual(tooltip(64, "Charging", end=80), "Battery 64%, charging to 80%")
        self.assertEqual(tooltip(64, "Discharging", "2h 10m", end=80), "Battery 64%, 2h 10m left")
        self.assertEqual(tooltip(60, "Not charging", end=80),
                         "Battery 60%, plugged in, not charging")

    def test_battery_rows(self):
        rows = tinybar.battery_rows
        self.assertEqual(rows(80, "Not charging", end=80, start=50),
                         [("battery-plug", "Battery 80%, plugged in"), ("shield-check", "Held at 80%")])
        self.assertEqual(rows(64, "Charging", "40m", 25.04, end=80),
                         [("battery-bolt", "Battery 64%, charging to 80%"),
                          ("bolt", "Charging at 25.0 W"), ("clock", "80% in 40m")])
        self.assertEqual(rows(64, "Charging", "1h 05m"),
                         [("battery-bolt", "Battery 64%, charging"), ("clock", "Full in 1h 05m")])
        self.assertEqual(rows(64, "Discharging", "2h 10m", 9.84, end=80),
                         [("battery-half", "Battery 64%, on battery"), ("bolt", "Drawing 9.8 W"),
                          ("clock", "2h 10m left"), ("shield-check", "Charge limit 80%")])
        self.assertEqual(rows(64, "Discharging"), [("battery-half", "Battery 64%, on battery")])
        self.assertEqual(rows(100, "Full"), [("battery-full", "Battery 100%, charged")])
        self.assertEqual(rows(None, "Unknown"),
                         [("battery-exclamation", "Battery level unknown")])

    def test_notifications(self):
        self.assertEqual(tinybar.notification_tooltip(0), "No notifications")
        self.assertEqual(tinybar.notification_tooltip(1), "1 notification")
        self.assertEqual(tinybar.notification_tooltip(3), "3 notifications")
        self.assertEqual(tinybar.notification_tooltip(0, quiet=True),
                         "No notifications, do not disturb on")
        self.assertEqual(tinybar.notification_tooltip(2, quiet=True),
                         "2 notifications, do not disturb on")

    def test_do_not_disturb_modes(self):
        mode = tinybar.DO_NOT_DISTURB_MODE
        self.assertEqual(tinybar.with_mode(["default"], mode, True), ["default", mode])
        self.assertEqual(tinybar.with_mode(["default", mode], mode, True), ["default", mode])
        self.assertEqual(tinybar.with_mode([mode, "away"], mode, False), ["away"])
        self.assertEqual(tinybar.with_mode([], mode, False), [])

    def test_task_buttons(self):
        self.assertEqual(tinybar.task_tooltip("Foot", ["~/code"]), "Foot\n~/code")
        self.assertEqual(tinybar.task_tooltip("Foot", ["foot"]), "Foot")
        self.assertEqual(tinybar.task_tooltip("Foot", [""]), "Foot")
        self.assertEqual(tinybar.task_tooltip("Foot", []), "Foot")
        self.assertEqual(tinybar.task_tooltip("Firefox", ["a", "b", "c"]), "Firefox\n3 windows")
        self.assertEqual(tinybar.task_tooltip("Foot", ["x" * 80], limit=10), "Foot\nxxxxxxxxx\u2026")
        self.assertEqual(tinybar.task_close_label(1), "Close")
        self.assertEqual(tinybar.task_close_label(3), "Close 3 windows")


def task_window(window_id, active=False, minimized=False):
    return {"id": window_id, "app_id": "foot", "active": active, "minimized": minimized}


class TaskClickTests(unittest.TestCase):
    def action(self, windows, last=None):
        verb, target = tinybar.task_click_action(windows, last)
        return verb, target["id"]

    def test_focused_only_window_is_minimised(self):
        self.assertEqual(self.action([task_window(1, active=True)]), ("minimize", 1))

    def test_unfocused_window_is_raised(self):
        self.assertEqual(self.action([task_window(1)]), ("activate", 1))

    def test_minimised_window_comes_back(self):
        # Some compositors keep the activated state on a minimised window.
        self.assertEqual(self.action([task_window(1, active=True, minimized=True)]), ("activate", 1))
        self.assertEqual(self.action([task_window(1, minimized=True)]), ("activate", 1))

    def test_several_windows_cycle_and_never_minimise(self):
        windows = [task_window(1), task_window(2, active=True), task_window(3)]
        self.assertEqual(self.action(windows), ("activate", 3))
        windows = [task_window(1), task_window(2), task_window(3, active=True)]
        self.assertEqual(self.action(windows), ("activate", 1))

    def test_unfocused_app_raises_its_last_focused_window(self):
        windows = [task_window(1), task_window(2), task_window(3)]
        self.assertEqual(self.action(windows, last=2), ("activate", 2))
        self.assertEqual(self.action(windows, last=9), ("activate", 1))

    def test_state_strings_still_pick_the_icons(self):
        # The indicators' first argument is parsed for the icon; the words are not.
        library = IconLibrary.__new__(IconLibrary)
        cases = [
            ("volume", "VOL MUTED", "volume-xmark"), ("volume", "VOL 65%", "volume-high"),
            ("volume", "VOL 20%", "volume-low"), ("wifi", "WIFI OFF", "wifi-slash"),
            ("wifi", "WIFI ?", "wifi-slash"), ("wifi", "WIFI ON", "wifi"),
            ("brightness", "BRI 40%", "brightness"), ("battery", "BAT 64% +", "battery-bolt"),
            ("battery", "BAT 64%", "battery-half"), ("battery", "BAT 100% FULL", "battery-full"),
            ("battery", "BAT ?%", "battery-exclamation"),
        ]
        for kind, state, icon in cases:
            self.assertEqual(library.status_name(kind, state), icon, state)

    def test_plugged_in_battery_shows_a_plug_when_the_theme_has_one(self):
        library = IconLibrary.__new__(IconLibrary)
        with mock.patch.object(IconLibrary, "has", lambda _self, name: True):
            self.assertEqual(library.status_name("battery", "BAT 61% PLUG"), "battery-plug")
        with mock.patch.object(IconLibrary, "has", lambda _self, name: False):
            self.assertEqual(library.status_name("battery", "BAT 61% PLUG"), "battery-half")


HCI0, HCI1 = "/org/bluez/hci0", "/org/bluez/hci1"
DEVICE, BATTERY = tinybar.BLUEZ_DEVICE, tinybar.BLUEZ_BATTERY


def bluez_device(adapter, alias, name=True, **values):
    return {DEVICE: {"Adapter": adapter, "Alias": alias, **({"Name": alias} if name else {}),
                     **values}}


class BluetoothTests(unittest.TestCase):
    def tree(self):
        return {
            HCI1: {tinybar.BLUEZ_ADAPTER: {"Powered": True}},
            HCI0: {tinybar.BLUEZ_ADAPTER: {"Powered": True}},
            HCI0 + "/dev_A": bluez_device(HCI0, "Zed phones", Paired=True, Icon="audio-headphones"),
            HCI0 + "/dev_B": {**bluez_device(HCI0, "keyboard", Paired=True, Connected=True),
                              BATTERY: {"Percentage": 80}},
            HCI0 + "/dev_C": bluez_device(HCI0, "Speaker"),
            HCI0 + "/dev_D": bluez_device(HCI0, "11-22-33-44-55-66", name=False),
            HCI1 + "/dev_E": bluez_device(HCI1, "On the other adapter", Paired=True),
        }

    def names(self, devices):
        return [device["name"] for device in devices]

    def test_the_first_adapter_is_used(self):
        self.assertEqual(tinybar.bluetooth_adapter(self.tree()), HCI0)
        self.assertIsNone(tinybar.bluetooth_adapter({}))

    def test_connected_first_and_nearby_only_with_a_name(self):
        paired, nearby = tinybar.bluetooth_devices(self.tree(), HCI0)
        self.assertEqual(self.names(paired), ["keyboard", "Zed phones"])
        self.assertEqual(self.names(nearby), ["Speaker"])
        self.assertEqual(tinybar.bluetooth_detail(paired[0]), "Connected · 80% battery")
        self.assertEqual(tinybar.bluetooth_detail(paired[1]), "Not connected")
        self.assertEqual([paired[1]["icon"], nearby[0]["icon"]], ["audio-headphones", "bluetooth"])

    def test_signals_keep_the_tree_current(self):
        tree, apply = self.tree(), tinybar.apply_bluez_signal
        apply(tree, "InterfacesAdded", "/", (HCI0 + "/dev_F", bluez_device(HCI0, "Mouse")))
        apply(tree, "PropertiesChanged", HCI0 + "/dev_A", (DEVICE, {"Connected": True}, ["Icon"]))
        apply(tree, "PropertiesChanged", HCI0 + "/dev_X", (DEVICE, {"Connected": True}, []))
        apply(tree, "InterfacesRemoved", "/", (HCI0 + "/dev_B", [DEVICE, BATTERY]))
        apply(tree, "InterfacesRemoved", "/", (HCI0 + "/dev_C", [BATTERY]))
        paired, nearby = tinybar.bluetooth_devices(tree, HCI0)
        self.assertEqual(self.names(paired), ["Zed phones"])
        self.assertEqual((paired[0]["connected"], paired[0]["icon"]), (True, "bluetooth"))
        self.assertEqual(self.names(nearby), ["Mouse", "Speaker"])
        self.assertNotIn(HCI0 + "/dev_B", tree)
        self.assertNotIn(HCI0 + "/dev_X", tree)

    def test_panel_view(self):
        paired = tinybar.bluetooth_devices(self.tree(), HCI0)[0]
        view = tinybar.bluetooth_view
        self.assertEqual(view(None, []), ("bluetooth-slash", "Bluetooth: no adapter"))
        self.assertEqual(view({"Powered": False}, paired), ("bluetooth-slash", "Bluetooth: off"))
        self.assertEqual(view({"Powered": True}, paired), ("bluetooth", "Bluetooth: connected to keyboard"))
        self.assertEqual(view({"Powered": True}, paired[1:])[1], "Bluetooth: on")
        both = [dict(device, connected=True) for device in paired]
        self.assertEqual(view({"Powered": True}, both)[1], "Bluetooth: 2 devices connected")

    def test_words(self):
        failure, prompt = tinybar.bluetooth_failure, tinybar.pairing_prompt
        self.assertEqual(failure("org.bluez.Error.AuthenticationRejected", "x"), "Pairing was refused")
        self.assertEqual(failure("org.bluez.Error.BREDR.ProfileUnavailable", "x"),
                         "Nothing on this device to connect to")
        self.assertEqual(failure("org.bluez.Error.Failed", "Could not connect"), "Could not connect")
        self.assertEqual(prompt("confirm", "Phones", 42), "Does Phones show 000042?")
        self.assertEqual(prompt("display", "Keys", 123456), "Type 123456 on Keys, then press Enter")
        self.assertEqual(prompt("display", "Keys", "0000"), "Type 0000 on Keys, then press Enter")
        self.assertEqual(prompt("pin", "Old mouse"), "Old mouse needs a PIN. Use Other device… below.")

    def test_an_open_form_keeps_its_list_and_the_ones_above(self):
        fill = tinybar.bluetooth_lists_to_fill
        self.assertEqual(fill(None), {"paired", "nearby"})
        # The nearby list, below a paired device's form, still fills while searching.
        self.assertEqual(fill({"device": {"paired": True}}), {"nearby"})
        self.assertEqual(fill({"device": {"paired": False}}), set())


class FakeBlueZ:
    """BluetoothControl's actions; each waits in self.calls until a test ends it with
    its on_done."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, action):
        return lambda *args: self.calls.append((action, args[-1]))


class FakeWidget:
    def get_parent(self):
        return None

    def set_label(self, _label):
        pass


class WidgetlessBluetoothMenu:
    """BluetoothMenu's device actions with stand-ins for its widgets and for BlueZ: the
    form records what it shows, and refresh() counts."""

    on_device_clicked = tinybar.BluetoothMenu.on_device_clicked
    on_connect_clicked = tinybar.BluetoothMenu.on_connect_clicked
    on_forget_clicked = tinybar.BluetoothMenu.on_forget_clicked
    done_for = tinybar.BluetoothMenu.done_for
    on_done = tinybar.BluetoothMenu.on_done
    close_form = tinybar.BluetoothMenu.close_form
    on_switch_set = tinybar.BluetoothMenu.on_switch_set
    on_pair_new_clicked = tinybar.BluetoothMenu.on_pair_new_clicked
    on_popover_hidden = tinybar.BluetoothMenu.on_popover_hidden

    def __init__(self):
        self.control, self.adapter = FakeBlueZ(), HCI0
        self.target, self.busy, self.searching, self.updating_switch = None, False, False, False
        self.form = self.connect_button = self.forget_button = FakeWidget()
        self.shown, self.refreshes = None, 0

    def show_form(self, message=None, buttons=()):
        self.shown = message

    def refresh(self):
        self.refreshes += 1


class BluetoothMenuTests(unittest.TestCase):
    PHONES = {"path": HCI0 + "/dev_A", "name": "Headphones", "paired": True, "connected": False}
    KEYBOARD = {"path": HCI0 + "/dev_B", "name": "Keyboard", "paired": True, "connected": True}

    def end(self, menu, call, ok, message=None):
        menu.control.calls[call][1](ok, message)

    def test_a_late_result_stays_with_the_form_it_came_from(self):
        for ok, message in ((False, "Could not connect"), (True, None)):
            menu = WidgetlessBluetoothMenu()
            menu.on_device_clicked("phones row", self.PHONES)
            menu.on_connect_clicked(None)  # call 0, still running when the popover closes
            menu.on_popover_hidden(None)
            menu.on_device_clicked("keyboard row", self.KEYBOARD)
            menu.on_connect_clicked(None)  # call 1
            self.assertEqual([action for action, _ in menu.control.calls],
                             ["connect", "disconnect"])
            self.end(menu, 0, ok, message)
            self.assertTrue(menu.busy)
            self.assertIs(menu.target["device"], self.KEYBOARD)
            self.assertEqual(menu.shown, "Disconnecting…")
            self.end(menu, 1, False, "Could not disconnect")
            self.assertFalse(menu.busy)
            self.assertEqual(menu.shown, "Could not disconnect")

    def test_closing_a_form_ends_its_wait(self):
        menu = WidgetlessBluetoothMenu()
        menu.on_device_clicked("phones row", self.PHONES)
        menu.on_connect_clicked(None)
        menu.on_switch_set(None, False)
        self.assertEqual((menu.target, menu.busy), (None, False))
        menu.on_device_clicked("keyboard row", self.KEYBOARD)
        self.assertIs(menu.target["device"], self.KEYBOARD)

    def test_pair_new_device_folds_a_form_with_nothing_running(self):
        menu = WidgetlessBluetoothMenu()
        menu.on_device_clicked("phones row", self.PHONES)
        menu.on_pair_new_clicked(None)
        self.assertIsNone(menu.target)
        self.assertTrue(menu.searching)
        menu.on_device_clicked("phones row", self.PHONES)
        menu.on_connect_clicked(None)
        menu.on_pair_new_clicked(None)
        self.assertIs(menu.target["device"], self.PHONES)  # It waits for its result.

    def test_the_switch_goes_back_only_when_bluez_refuses(self):
        menu = WidgetlessBluetoothMenu()
        menu.on_switch_set(None, False)
        self.end(menu, 0, True)  # BlueZ's PropertiesChanged redraws it, not the reply.
        self.assertEqual(menu.refreshes, 0)
        menu.on_switch_set(None, True)
        self.end(menu, 1, False, "Could not switch Bluetooth")
        self.assertEqual(menu.refreshes, 1)


@unittest.skipUnless(shutil.which("dbus-daemon"), "needs dbus-daemon")
class BluetoothAgentTests(unittest.TestCase):
    """The pairing agent's D-Bus side, called as BlueZ would on a private bus."""

    PATH = HCI0 + "/dev_A"
    REFUSED = "org.bluez.Error.Rejected"

    @classmethod
    def setUpClass(cls):
        cls.dbus = Gio.TestDBus.new(Gio.TestDBusFlags.NONE)
        cls.dbus.up()
        cls.bus = Gio.DBusConnection.new_for_address_sync(
            cls.dbus.get_bus_address(),
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
        cls.requests, cls.yes = [], True
        cls.control = tinybar.BluetoothControl(cls.bus, lambda: None, cls.on_request)

    @classmethod
    def tearDownClass(cls):
        cls.bus.close_sync(None)
        cls.dbus.down()

    @classmethod
    def on_request(cls, kind, device, code, answer):
        cls.requests.append((kind, device, code))
        if answer:
            answer(cls.yes)

    def ask(self, method, signature, *args):
        """The D-Bus error name the agent answers with, or None for a yes."""
        result = []

        def finished(bus, reply):
            try:
                bus.call_finish(reply)
                result.append(None)
            except GLib.Error as error:
                result.append(Gio.DBusError.get_remote_error(error))

        self.bus.call(self.bus.get_unique_name(), tinybar.BLUEZ_AGENT_PATH, "org.bluez.Agent1",
                      method, GLib.Variant(signature, args), None, Gio.DBusCallFlags.NONE,
                      2000, None, finished)
        while not result:  # The call times out after 2 s at most.
            GLib.MainContext.default().iteration(True)
        return result[0]

    def test_a_number_to_compare_follows_the_answer(self):
        type(self).yes = True
        self.assertIsNone(self.ask("RequestConfirmation", "(ou)", self.PATH, 123456))
        type(self).yes = False
        self.assertEqual(self.ask("RequestConfirmation", "(ou)", self.PATH, 123456), self.REFUSED)
        self.assertEqual(self.requests[-1], ("confirm", self.PATH, 123456))

    def test_a_pin_to_type_here_is_refused_and_said_so(self):
        self.requests.clear()
        self.assertEqual(self.ask("RequestPinCode", "(o)", self.PATH), self.REFUSED)
        self.assertEqual(self.ask("RequestPasskey", "(o)", self.PATH), self.REFUSED)
        self.assertEqual(self.requests, [("pin", self.PATH, None)] * 2)

    def test_a_passkey_to_type_on_the_device_is_shown(self):
        self.assertIsNone(self.ask("DisplayPasskey", "(ouq)", self.PATH, 1234, 0))
        self.assertEqual(self.requests[-1], ("display", self.PATH, 1234))

    def test_only_paired_devices_connect_by_themselves(self):
        uuid = "0000110b"  # A2DP sink, short form
        self.control.objects = {self.PATH: {DEVICE: {"Paired": True}}}
        self.assertIsNone(self.ask("AuthorizeService", "(os)", self.PATH, uuid))
        self.control.objects = {}
        self.assertEqual(self.ask("AuthorizeService", "(os)", self.PATH, uuid), self.REFUSED)


if __name__ == "__main__":
    unittest.main()
