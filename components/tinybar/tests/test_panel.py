"""Check Tinybar's pure display helpers. Imports the panel without starting it."""
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tinybar  # noqa: E402
from tinybar_icons import IconLibrary, brightness_glyph, signal_glyph, volume_glyph  # noqa: E402


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
            hardware=True):
    """A NetworkMenu.read_state result."""
    return {"wifi": wifi, "wifi_connected": wifi_connected or wifi is not None,
            "wired": wired, "wifi_device": device, "enabled": enabled,
            "hardware_enabled": hardware, "nearby": []}


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
        self.assertEqual(tinybar.network_tooltip(network(device=None)), "Network: not connected")
        self.assertEqual(tinybar.network_tooltip(None), "Network: status unavailable")

    def test_volume_and_brightness(self):
        self.assertEqual(tinybar.volume_tooltip((65, False)), "Volume 65%")
        self.assertEqual(tinybar.volume_tooltip((65, True)), "Volume: muted")
        self.assertEqual(tinybar.volume_tooltip(None), "Volume: unavailable")
        self.assertEqual(tinybar.brightness_tooltip(40), "Brightness 40%")
        self.assertEqual(tinybar.brightness_tooltip(None), "Brightness: unavailable")

    def test_battery_level_and_time(self):
        self.assertEqual(tinybar.battery_lines(64, "Discharging", "2h 10m", 9.84),
                         ["Battery 64%, 2h 10m left", "Drawing 9.8 W"])
        self.assertEqual(tinybar.battery_lines(64, "Discharging"),
                         ["Battery 64%, discharging", "Power draw unavailable"])
        self.assertEqual(tinybar.battery_lines(64, "Charging", "1h 05m"),
                         ["Battery 64%, charging, full in 1h 05m"])
        self.assertEqual(tinybar.battery_lines(64, "Charging"), ["Battery 64%, charging"])
        self.assertEqual(tinybar.battery_lines(100, "Full"), ["Battery 100%, charged"])
        self.assertEqual(tinybar.battery_lines(80, "Not charging"),
                         ["Battery 80%, plugged in, not charging"])
        self.assertEqual(tinybar.battery_lines(80, "Unknown"), ["Battery 80%"])
        self.assertEqual(tinybar.battery_lines(None, "Unknown"), ["Battery level unknown"])

    def test_battery_average(self):
        window = tinybar.HISTORY_WINDOW_SECONDS
        self.assertEqual(tinybar.battery_lines(64, "Full", average=(9.84, window))[1:],
                         ["3-hour average 9.8 W"])
        self.assertEqual(tinybar.battery_lines(64, "Full", average=(9.84, 45 * 60))[1:],
                         ["Average 9.8 W over 45m on battery"])
        self.assertEqual(tinybar.battery_lines(64, "Full", average=(None, 0)), ["Battery 64%, charged"])
        self.assertEqual(tinybar.battery_lines(64, "Full", average=(9.84, 59)), ["Battery 64%, charged"])

    def test_notifications(self):
        self.assertEqual(tinybar.notification_tooltip(0), "No notifications")
        self.assertEqual(tinybar.notification_tooltip(1), "1 notification")
        self.assertEqual(tinybar.notification_tooltip(3), "3 notifications")

    def test_task_buttons(self):
        self.assertEqual(tinybar.task_tooltip("Foot", ["~/code"]), "Foot\n~/code")
        self.assertEqual(tinybar.task_tooltip("Foot", ["foot"]), "Foot")
        self.assertEqual(tinybar.task_tooltip("Foot", [""]), "Foot")
        self.assertEqual(tinybar.task_tooltip("Foot", []), "Foot")
        self.assertEqual(tinybar.task_tooltip("Firefox", ["a", "b", "c"]), "Firefox\n3 windows")
        self.assertEqual(tinybar.task_tooltip("Foot", ["x" * 80], limit=10), "Foot\nxxxxxxxxx\u2026")

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


if __name__ == "__main__":
    unittest.main()
