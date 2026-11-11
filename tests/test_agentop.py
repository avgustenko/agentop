#!/usr/bin/env python3
"""Unit and smoke tests for AgentOp. Run: python3 -m unittest discover -s tests -v"""

import copy
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "agentop"

loader = importlib.machinery.SourceFileLoader("agentop_mod", str(SCRIPT))
spec = importlib.util.spec_from_loader("agentop_mod", loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)


class DemoSpeed:
    def __init__(self):
        self._buckets = [3, 9, 14, 22, 18, 31, 44, 52, 61, 48, 39, 58, 72, 64, 51,
                         43, 66, 83, 91, 74, 62, 55, 71, 88, 96, 79, 63, 57, 69, 81]

    def events(self):
        return [(0.0, v, "demo") for v in self._buckets]

    def rate(self, seconds):
        return 118.4

    def peak(self, bucket=60, total=900):
        return 241.7

    def snapshot(self):
        return {"now": 118.4, "avg1": 124.2, "avg5": 104.2,
                "peak": 241.7, "buckets": self._buckets}


def demo_data():
    cores = [(f"cpu{i}", v) for i, v in enumerate([42, 18, 7, 3, 61, 12, 5, 2, 24, 9, 6, 1])]
    return {
        "limits": {
            "five_hour": {"utilization": 42.0, "resets_at": "2099-01-01T00:00:00+00:00"},
            "seven_day": {"utilization": 68.0, "resets_at": "2099-01-02T00:00:00+00:00"},
            "_fetched_at": 0,
        },
        "claude": {"totals": {"input": 1_240_000, "output": 45_200,
                              "cache_read": 12_400_000, "cache_write": 1_100_000,
                              "messages": 128}},
        "opencode": {"today": {"input": 890_000, "output": 78_000, "reasoning": 42_000,
                                "cache_read": 45_000_000, "cache_write": 0,
                                "cost": 0.84, "messages": 96},
                     "all_cost": 12.40},
        "speed": DemoSpeed(),
        "pcts": [("cpu", 37.0)] + cores,
        "load": (0.82, 0.65, 0.51),
        "mem": (15.5, 6.8, 4.0, 0.0),
        "temp": 54.0,
        "gpu": 12,
        "gpu_temp": 48.0,
        "bat": {"cap": 84, "status": "Discharging", "ac": False,
                "power": 9_500_000, "energy": 46_200_000, "full": 55_000_000},
        "disk": (1_200_000, 340_000),
        "net": (1_400_000, 120_000),
        "iface": "wlan0",
        "root": (210_000_000_000, 38_000_000_000, 150_000_000_000),
        "procs": [(12.0, 2.0, "browser"), (8.0, 1.0, "editor"),
                  (5.0, 1.0, "terminal"), (3.0, 2.0, "agent")],
        "uptime": 3 * 3600 + 12 * 60,
        "hist_cpu": [18, 22, 35, 51, 47, 62, 58, 44, 39, 55],
        "hist_load": [0.5, 0.6, 0.7, 0.9, 1.1, 0.8, 0.7, 0.6, 0.8, 1.0],
        "hist_temp": [46, 47, 48, 50, 52, 54, 53, 51, 50, 52],
        "hist_io": [0, 0, 2, 8, 14, 3, 0, 1, 6, 12],
    }


def make_app(view="dashboard"):
    cfg = copy.deepcopy(mod.DEFAULT_CONFIG)
    cfg["theme"] = "mono"
    cfg["view"] = view
    return mod.App(cfg, threaded=False)


class FormatTests(unittest.TestCase):
    def test_tokens(self):
        self.assertEqual(mod.fmt_tokens(0), "0")
        self.assertEqual(mod.fmt_tokens(999), "999")
        self.assertEqual(mod.fmt_tokens(1500), "1.5K")
        self.assertEqual(mod.fmt_tokens(1_500_000), "1.5M")

    def test_bytes(self):
        self.assertEqual(mod.fmt_bytes(0), "0B")
        self.assertEqual(mod.fmt_bytes(1024), "1.0K")
        self.assertEqual(mod.fmt_bytes(1024 * 1024), "1.0M")

    def test_human_left(self):
        self.assertEqual(mod.human_left(-1), "0м")
        self.assertEqual(mod.human_left(59), "0м")
        self.assertEqual(mod.human_left(60), "1м")
        self.assertEqual(mod.human_left(3600), "1ч 00м")
        self.assertEqual(mod.human_left(86400), "1д 0ч")

    def test_age_label(self):
        self.assertEqual(mod.age_label(5), "5с")
        self.assertEqual(mod.age_label(89), "89с")
        self.assertEqual(mod.age_label(90), "1м")
        self.assertEqual(mod.age_label(3600), "60м")


class TextTests(unittest.TestCase):
    def setUp(self):
        self._color = mod.COLOR
        mod.COLOR = False

    def tearDown(self):
        mod.COLOR = self._color

    def test_vlen(self):
        self.assertEqual(mod.vlen("\x1b[38;5;1mabc\x1b[0m"), 3)

    def test_clip(self):
        out = mod.clip("abcdef", 3)
        self.assertEqual(mod.vlen(out), 3)
        self.assertTrue(out.endswith("…"))

    def test_pad(self):
        self.assertEqual(mod.pad("ab", 4), "ab  ")
        self.assertEqual(len(mod.pad("abcd", 2)), 4)

    def test_sparkline(self):
        t = mod.Theme("mono")
        s = mod.sparkline([1, 2, 3, 4], t, "gradient")
        self.assertEqual(mod.vlen(s), 4)
        self.assertNotIn("\x1b", s)

    def test_braille(self):
        t = mod.Theme("mono")
        rows = mod.braille_graph([1, 2, 3, 4], 20, 3, t)
        self.assertEqual(len(rows), 3)
        for r in rows:
            self.assertLessEqual(mod.vlen(r), 20)


class ThemeTests(unittest.TestCase):
    def test_bar_plain(self):
        old = mod.COLOR
        mod.COLOR = False
        try:
            b = mod.Theme("mono").bar(50, 10)
            self.assertEqual(mod.vlen(b), 10)
            self.assertEqual(b.count("█"), 5)
            self.assertNotIn("\x1b", b)
        finally:
            mod.COLOR = old

    def test_bar_color(self):
        old = mod.COLOR
        mod.COLOR = True
        try:
            b = mod.Theme("dracula").bar(100, 8)
            self.assertIn("\x1b[38;5;", b)
            self.assertEqual(mod.vlen(b), 8)
        finally:
            mod.COLOR = old


class SettingsTests(unittest.TestCase):
    def test_items(self):
        keys = [x[0] for x in mod.settings_items({})]
        for k in ("interval", "theme", "view", "history", "history_interval",
                  "limit_decimals", "clock_ms", "show.network", "show.disk",
                  "show.processes", "show.gpu", "show.per_core"):
            self.assertIn(k, keys)

    def test_choice_index(self):
        self.assertEqual(mod.choice_index([0.01, 0.1, 1, 300], 0.1), 1)
        self.assertEqual(mod.choice_index([0.01, 0.1, 1, 300], 0.15), 1)
        self.assertEqual(mod.choice_index([0.01, 0.1, 1, 300], 1000), 3)
        self.assertEqual(mod.choice_index(["auto", "nord"], "auto"), 0)

    def test_get_set(self):
        cfg = {"show": {"network": True}, "interval": 1.0}
        self.assertTrue(mod.setting_get(cfg, "show.network"))
        mod.setting_set(cfg, "show.network", False)
        self.assertFalse(mod.setting_get(cfg, "show.network"))
        mod.setting_set(cfg, "interval", 2.0)
        self.assertEqual(cfg["interval"], 2.0)

    def test_fmt(self):
        self.assertEqual(mod.fmt_setting("interval", 0.01), "0.01 с")
        self.assertEqual(mod.fmt_setting("interval", 1.0), "1 с")
        self.assertEqual(mod.fmt_setting("interval", 300), "300 с")
        self.assertEqual(mod.fmt_setting("history", 120), "120 точек")
        self.assertEqual(mod.fmt_setting("clock_ms", False), "выкл")

    def test_apply(self):
        app = make_app()
        old_save = mod.save_config
        mod.save_config = lambda cfg: None
        try:
            mod.apply_setting(app, "interval", 2.0)
            self.assertEqual(app.cfg["interval"], 2.0)
            mod.apply_setting(app, "view", "focus")
            self.assertEqual(app.view, "focus")
            mod.apply_setting(app, "history", 60)
            self.assertEqual(app.h_cpu.maxlen, 60)
            mod.apply_setting(app, "show.network", False)
            self.assertFalse(app.cfg["show"]["network"])
        finally:
            mod.save_config = old_save


class RenderTests(unittest.TestCase):
    def setUp(self):
        self._color = mod.COLOR
        mod.COLOR = False
        self.app = make_app()
        self.data = demo_data()

    def tearDown(self):
        mod.COLOR = self._color

    def test_limits(self):
        lines = mod.limits_lines(self.data["limits"], self.app.theme, 80, 3)
        text = "\n".join(lines)
        self.assertIn("42.000%", text)
        self.assertIn("68.000%", text)

    def test_views(self):
        for view in mod.VIEWS:
            with self.subTest(view=view):
                self.app.view = view
                lines = mod.render(self.app, self.data, 100, 30)
                self.assertTrue(lines)
                self.assertLessEqual(len(lines), 30)
                for line in lines:
                    self.assertLessEqual(mod.vlen(line), 100)

    def test_view_content(self):
        self.app.view = "focus"
        text = "\n".join(mod.render(self.app, self.data, 100, 40))
        self.assertIn("СКОРОСТЬ ТОКЕНОВ", text)
        self.assertNotIn("ТОП ПРОЦЕССОВ", text)
        self.app.view = "system"
        text = "\n".join(mod.render(self.app, self.data, 100, 40))
        self.assertIn("CPU", text)
        self.assertIn("ТОП ПРОЦЕССОВ", text)
        self.app.view = "minimal"
        text = "\n".join(mod.render(self.app, self.data, 100, 20))
        self.assertIn("tok/s", text)

    def test_settings_screen(self):
        lines = mod.render_settings(self.app, 100, 30, 0)
        text = "\n".join(lines)
        self.assertIn("НАСТРОЙКИ", text)
        self.assertIn("0.01", text)
        self.assertIn("300", text)
        for line in lines:
            self.assertLessEqual(mod.vlen(line), 100)


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ)
        env["COLUMNS"] = "100"
        env["LINES"] = "30"
        env["NO_COLOR"] = "1"
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True, env=env, timeout=30)

    def test_version(self):
        r = self.run_cli("--version")
        self.assertEqual(r.returncode, 0)
        self.assertIn("agentop", r.stdout)

    def test_list(self):
        self.assertEqual(self.run_cli("--list-themes").returncode, 0)
        self.assertEqual(self.run_cli("--list-views").returncode, 0)

    def test_once(self):
        r = self.run_cli("--once")
        self.assertEqual(r.returncode, 0)
        self.assertIn("AGENTOP", r.stdout)
        self.assertNotIn("\x1b", r.stdout)

    def test_json(self):
        r = self.run_cli("--json")
        self.assertEqual(r.returncode, 0)
        data = json.loads(r.stdout)
        self.assertIn("limits", data)
        self.assertIn("system", data)

    def test_short(self):
        r = self.run_cli("--short")
        self.assertEqual(r.returncode, 0)
        self.assertIn("tok/s", r.stdout)


if __name__ == "__main__":
    unittest.main()
