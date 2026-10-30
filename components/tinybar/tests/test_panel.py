"""Check Tinybar's pure display helpers. Imports the panel without starting it."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tinybar  # noqa: E402
from tinybar_icons import brightness_glyph, signal_glyph, volume_glyph  # noqa: E402


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
            ["CPU 7%", "RAM 2.9/14.8 GiB"])
        self.assertEqual(tinybar.usage_lines(None, (2.94, 14.79)), ["RAM 2.9/14.8 GiB"])
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

    def test_reset_on_charge(self):
        steps = [(9, "Discharging"), (9, "Charging"), (9, "Discharging")]
        self.assertEqual(warnings_over(steps), [10, 10])
        for status in ("Charging", "Full", "Not charging"):
            self.assertEqual(tinybar.battery_warning(4, status, 5), (None, None))

    def test_jump_below_both_gives_only_the_critical_one(self):
        self.assertEqual(warnings_over([(12, "Discharging"), (4, "Discharging")]), [5])

    def test_unknown_status_or_percent_keeps_the_state(self):
        self.assertEqual(tinybar.battery_warning(4, "Unknown", 10), (None, 10))
        self.assertEqual(tinybar.battery_warning(None, "Discharging", 10), (None, 10))
        steps = [(9, "Discharging"), (9, "Unknown"), (9, "Discharging")]
        self.assertEqual(warnings_over(steps), [10])

    def test_text(self):
        self.assertEqual(tinybar.battery_warning_text("10", 10, "25m"),
                         ("Battery at 10 %", "About 25m left."))
        self.assertEqual(tinybar.battery_warning_text("10", 10, None),
                         ("Battery at 10 %", "Plug in soon."))
        self.assertEqual(tinybar.battery_warning_text("4", 5, None),
                         ("Battery at 4 %", "Plug in now."))


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


if __name__ == "__main__":
    unittest.main()
