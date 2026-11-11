#!/usr/bin/env python3
"""Unit and smoke tests for AgentOp. Run: python3 -m unittest discover -s tests -v"""

import copy
import importlib.machinery
import importlib.util
import json
import os
import atexit
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Изоляция: тесты не читают настоящие логи/токен и не трогают ~/.cache и ~/.config,
# а CLI-запуски не ходят в API Anthropic с вашим токеном.
TMP_HOME = tempfile.mkdtemp(prefix="agentop-test-")
os.environ["HOME"] = TMP_HOME
atexit.register(shutil.rmtree, TMP_HOME, True)

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


class ReviewFixTests(unittest.TestCase):
    """Регрессии из ревизии 1.2.2."""

    def key(self, raw):
        r, w = os.pipe()
        try:
            os.write(w, raw)
            os.close(w)
            w = None
            return mod.read_key(r)
        finally:
            os.close(r)
            if w is not None:
                os.close(w)

    def test_read_key_russian_layout(self):
        # раньше: пустая строка → живой режим завершался
        self.assertEqual(self.key("к".encode()), "r")
        self.assertEqual(self.key("й".encode()), "q")
        self.assertEqual(self.key("ы".encode()), "s")

    def test_read_key_eof_and_arrows(self):
        self.assertIsNone(self.key(b""))
        self.assertEqual(self.key(b"\x1b[A"), "UP")
        self.assertEqual(self.key(b"\x1bOB"), "DOWN")
        self.assertEqual(self.key(b"q"), "q")
        self.assertEqual(self.key("ж".encode()), "ж")

    def test_age_label_long(self):
        self.assertEqual(mod.age_label(3 * 3600), "3ч")
        self.assertEqual(mod.age_label(3 * 86400), "3д")

    def test_window_expired(self):
        past = {"utilization": 100, "resets_at": "2000-01-01T00:00:00+00:00"}
        future = {"utilization": 100, "resets_at": "2999-01-01T00:00:00+00:00"}
        self.assertTrue(mod.window_expired(past))
        self.assertFalse(mod.window_expired(future))
        self.assertFalse(mod.window_expired({}))
        t = mod.Theme("mono")
        lines = mod.limits_lines({"five_hour": past, "seven_day": future}, t, 100)
        text = "\n".join(lines)
        self.assertIn("окно сброшено", text)
        self.assertNotIn("5h лимит исчерпан", text)
        self.assertIn("7d лимит исчерпан", text)

    def test_procs_current_cpu(self):
        p = mod.Procs()
        self.assertTrue(p.prev)
        end = __import__("time").time() + 0.3
        while __import__("time").time() < end:
            pass  # нагружаем CPU тестовым процессом
        others = mod.Procs()
        others.prev = p.prev
        others.last = p.last
        top = others.top(50)
        self.assertTrue(all(len(x) == 3 for x in top))
        self.assertTrue(all(x[0] >= 0 for x in top))

    def test_persist_does_not_leak_overrides(self):
        saved = {}
        old_load, old_save = mod.load_config, mod.save_config
        mod.load_config = lambda: copy.deepcopy(mod.DEFAULT_CONFIG)
        mod.save_config = lambda cfg: saved.update(copy.deepcopy(cfg))
        try:
            app = make_app()
            app.cfg["theme"] = "nord"  # разовый --theme
            mod.apply_setting(app, "view", "focus")
        finally:
            mod.load_config, mod.save_config = old_load, old_save
        self.assertEqual(saved["view"], "focus")
        self.assertEqual(saved["theme"], mod.DEFAULT_CONFIG["theme"])

    def test_root_disk_in_diskstats(self):
        dev = mod.DiskIO._root_disk()
        if Path("/proc/diskstats").exists():
            names = [l.split()[2] for l in Path("/proc/diskstats").read_text().splitlines()]
            self.assertIn(dev, names)

    def test_bad_theme_exit_code(self):
        env = dict(os.environ, NO_COLOR="1")
        for args in (["--set-theme", "nope"], ["--theme", "nope", "--once"]):
            r = subprocess.run([sys.executable, str(SCRIPT), *args],
                               capture_output=True, text=True, env=env, timeout=30)
            self.assertEqual(r.returncode, 2, args)


class FeatureTests(unittest.TestCase):
    """Доработки 1.3.0."""

    def setUp(self):
        for f in (mod.HISTORY_FILE, mod.NOTIFY_STATE, mod.CLAUDE_CACHE):
            try:
                f.unlink()
            except FileNotFoundError:
                pass
        mod._hist_cache.update(stamp=None, rows=[])

    def test_isolated_home(self):
        self.assertTrue(str(mod.HOME).startswith(TMP_HOME))

    def test_model_price(self):
        self.assertEqual(mod.model_price("claude-opus-5-5"), (4.0, 20.0, 5.0, 0.20))
        self.assertEqual(mod.model_price("claude-opus-5")[0], 5.0)
        self.assertEqual(mod.model_price("claude-sonnet-4-5-20250929")[0], 3.0)
        self.assertIsNone(mod.model_price("gpt-x"))
        self.assertEqual(mod.model_price("claude-opus-5-5", {"claude-opus-5-5": [1, 2, 3, 4]}),
                         (1.0, 2.0, 3.0, 4.0))

    def test_usage_cost(self):
        u = {"input_tokens": 1_000_000, "output_tokens": 1_000_000,
             "cache_creation_input_tokens": 2_000_000,
             "cache_creation": {"ephemeral_1h_input_tokens": 1_000_000},
             "cache_read_input_tokens": 10_000_000}
        # 4 + 20 + 5 (5м) + 8 (1ч = 2×4) + 2 (чтение)
        self.assertAlmostEqual(mod.usage_cost("claude-opus-5-5", u), 39.0)
        u["speed"] = "fast"
        self.assertAlmostEqual(mod.usage_cost("claude-opus-5-5", u), 78.0)
        self.assertIsNone(mod.usage_cost("unknown", u))

    def test_claude_today_models(self):
        proj = Path(TMP_HOME, ".claude/projects/p")
        proj.mkdir(parents=True, exist_ok=True)
        now = mod.datetime.now().astimezone().isoformat()
        line = lambda i, model: json.dumps({
            "type": "assistant", "timestamp": now, "requestId": f"r{i}",
            "message": {"id": f"m{i}", "model": model,
                        "usage": {"input_tokens": 1000, "output_tokens": 2000}}})
        (proj / "s.jsonl").write_text("\n".join([
            line(1, "claude-opus-5-5"), line(1, "claude-opus-5-5"),  # дубль
            line(2, "claude-sonnet-5-5"), line(3, "<synthetic>")]) + "\n")
        try:
            res = mod.claude_today(ttl=0)
        finally:
            shutil.rmtree(Path(TMP_HOME, ".claude"))
        self.assertEqual(res["totals"]["messages"], 2)
        self.assertEqual(set(res["models"]), {"claude-opus-5-5", "claude-sonnet-5-5"})
        self.assertAlmostEqual(res["models"]["claude-opus-5-5"]["cost_api"], 0.044)
        self.assertAlmostEqual(res["totals"]["cost_api"], 0.044 + 0.022)

    def lim(self, u5, reset5):
        iso = lambda ts: mod.datetime.fromtimestamp(ts).astimezone().isoformat()
        return {"five_hour": {"utilization": u5, "resets_at": iso(reset5)},
                "seven_day": {"utilization": 1, "resets_at": iso(reset5 + 86400)}}

    def test_history_and_trend(self):
        t0 = 1_800_000_000.0
        reset = t0 + 3 * 3600
        self.assertTrue(mod.record_limits(self.lim(10, reset), now=t0))
        self.assertFalse(mod.record_limits(self.lim(10, reset), now=t0 + 60))  # без изменений
        self.assertTrue(mod.record_limits(self.lim(20, reset), now=t0 + 1200))
        pts = mod.window_history(self.lim(20, reset), "5h", "five_hour")
        self.assertEqual([u for _, u in pts], [10.0, 20.0])
        rate = mod.recent_rate(pts)
        self.assertAlmostEqual(rate * 1200, 10.0)
        # другое окно (другой сброс) — пусто
        self.assertEqual(mod.window_history(self.lim(20, reset + 3600), "5h", "five_hour"), [])
        self.assertIsNone(mod.recent_rate(pts[:1]))

    def test_history_prunes_old(self):
        t0 = 1_800_000_000.0
        mod.record_limits(self.lim(10, t0 + 100), now=t0)
        mod.record_limits(self.lim(50, t0 + 100), now=t0 + 9 * 86400)
        self.assertEqual(len(mod.load_history()), 1)

    def test_notify_once_per_window(self):
        sent = []
        sender = lambda title, body, urg: sent.append((title, urg))
        now = __import__("time").time()
        cfg = {"notify": True, "notify_thresholds": [80, 95]}
        self.assertEqual(mod.maybe_notify(self.lim(50, now + 3600), cfg, now, sender), [])
        mod.maybe_notify(self.lim(85, now + 3600), cfg, now, sender)
        mod.maybe_notify(self.lim(86, now + 3600), cfg, now, sender)  # повтор — тихо
        mod.maybe_notify(self.lim(97, now + 3600), cfg, now, sender)
        self.assertEqual([u for _, u in sent], ["normal", "critical"])
        mod.maybe_notify(self.lim(97, now + 3600), {"notify": False}, now, sender)
        self.assertEqual(len(sent), 2)

    def test_models_lines(self):
        t = mod.Theme("mono")
        cl = {"totals": {"cost_api": 1.5},
              "models": {"claude-opus-5-5": {"output": 5000, "cache_read": 1, "messages": 3,
                                             "cost_api": 1.5}}}
        oc = {"models": {"deepseek-flash": {"cost": 0.25, "output": 10, "reasoning": 5,
                                            "cache_read": 0, "messages": 1}}}
        text = "\n".join(mod.models_lines(cl, oc, t, 80))
        self.assertIn("opus-5-5", text)
        self.assertIn("≈$1.50", text)
        self.assertIn("$0.250", text)
        self.assertIn("1.50", mod.models_title(cl))
        self.assertIn("нет данных", mod.models_lines(None, None, t, 80)[0])

    def test_limits_trend_line(self):
        t = mod.Theme("mono")
        now = __import__("time").time()
        lim = self.lim(40, now + 3600)
        hist = {"5h": [(now - 1500, 10.0), (now - 300, 35.0)]}  # 72%/ч → 112% к сбросу
        text = "\n".join(mod.limits_lines(lim, t, 100, 0, hist))
        self.assertIn("тренд 30м", text)
        self.assertIn("хватит на", text)

    def test_bar_outputs(self):
        app = make_app()
        data = app.sample()
        now = __import__("time").time()
        data["limits"] = self.lim(90, now + 3600)
        w = json.loads(mod.waybar_out(app, data))
        self.assertEqual(w["class"], "warning")
        self.assertIn("5h 90%", w["text"])
        a = mod.argos_out(app, data).splitlines()
        self.assertIn("5h 90%", a[0])
        self.assertIn("---", a)


class TaskManagerTests(unittest.TestCase):
    """Диспетчер задач 1.4.0."""

    def key(self, raw, translate=True):
        r, w = os.pipe()
        try:
            os.write(w, raw)
            os.close(w)
            w = None
            return mod.read_key(r, translate)
        finally:
            os.close(r)
            if w is not None:
                os.close(w)

    def test_special_keys(self):
        self.assertEqual(self.key(b"\x1b[3~"), "DEL")
        self.assertEqual(self.key(b"\x1b[5~"), "PGUP")
        self.assertEqual(self.key(b"\x1b[6~"), "PGDN")
        self.assertEqual(self.key(b"\x1b[H"), "HOME")
        self.assertEqual(self.key(b"\x1bOF"), "END")
        self.assertEqual(self.key("в".encode()), "d")
        self.assertEqual(self.key("ч".encode()), "x")
        self.assertEqual(self.key("в".encode(), translate=False), "в")

    def test_snapshot(self):
        pr = mod.Procs()
        __import__("time").sleep(1.05)
        snap = pr.snapshot()
        me = [p for p in snap if p["pid"] == os.getpid()]
        self.assertEqual(len(me), 1)
        for k in ("pid", "name", "app", "cpu", "mem", "rss", "threads", "uid", "user", "ppid"):
            self.assertIn(k, me[0])
        self.assertIs(pr.snapshot(), snap)  # чаще раза в секунду — из кэша
        self.assertTrue(pr.top(3))

    def test_risks(self):
        me = {"pid": os.getpid(), "name": "python", "uid": os.getuid(), "ppid": os.getppid()}
        self.assertEqual(mod.proc_risk(me)[0], "block")
        self.assertEqual(mod.proc_risk({"pid": 1, "name": "systemd", "uid": 0, "ppid": 0})[0], "block")
        parent = {"pid": os.getppid(), "name": "bash", "uid": os.getuid(), "ppid": 1}
        self.assertEqual(mod.proc_risk(parent)[0], "warn")
        shell = {"pid": 999999, "name": "gnome-shell", "uid": os.getuid(), "ppid": 1}
        self.assertEqual(mod.proc_risk(shell)[0], "warn")
        other = {"pid": 999998, "name": "x", "uid": os.getuid() + 1, "user": "root", "ppid": 1}
        self.assertIn("root", mod.proc_risk(other)[1])
        normal = {"pid": 999997, "name": "sleep", "uid": os.getuid(), "ppid": 1}
        self.assertIsNone(mod.proc_risk(normal))

    def test_rows_group_sort_filter(self):
        st = mod.TaskState()
        procs = [
            {"pid": 10, "name": "Web Content", "app": "firefox", "cpu": 5.0, "mem": 1, "rss": 100, "threads": 3, "uid": 1, "user": "u", "ppid": 1},
            {"pid": 11, "name": "firefox", "app": "firefox", "cpu": 7.0, "mem": 2, "rss": 200, "threads": 9, "uid": 1, "user": "u", "ppid": 1},
            {"pid": 12, "name": "vim", "app": "vim", "cpu": 9.0, "mem": 1, "rss": 50, "threads": 1, "uid": 1, "user": "u", "ppid": 1},
        ]
        rows = mod.task_rows(procs, st)
        self.assertEqual([r["name"] for r in rows], ["firefox", "vim"])
        self.assertEqual(sorted(rows[0]["pids"]), [10, 11])
        self.assertAlmostEqual(rows[0]["cpu"], 12.0)
        st.group = False
        self.assertEqual([r["pid"] for r in mod.task_rows(procs, st)], [12, 11, 10])
        st.filter = "vim"
        self.assertEqual([r["pid"] for r in mod.task_rows(procs, st)], [12])

    def test_kill_flow(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        try:
            app = make_app()
            st = app.tasks
            st.rows = [{"pid": child.pid, "pids": [child.pid], "name": "sleeper", "app": "sleeper",
                        "uid": os.getuid(), "user": "me", "ppid": os.getpid()}]
            self.assertTrue(mod.tasks_key(app, "x"))
            self.assertIsNotNone(st.confirm)
            self.assertTrue(mod.tasks_key(app, "n"))  # отмена
            self.assertIsNone(st.confirm)
            self.assertIsNone(child.poll())
            mod.tasks_key(app, "x")
            mod.tasks_key(app, "y")  # SIGTERM
            child.wait(timeout=5)
            self.assertEqual(child.returncode, -15)
            st.pending["deadline"] = 0
            mod.task_check_pending(st)
            self.assertIn("завершён", st.message[0])
        finally:
            if child.poll() is None:
                child.kill()

    def test_force_kill_offer(self):
        # процесс игнорирует SIGTERM → через 3 с предлагается принудительное завершение
        child = subprocess.Popen([sys.executable, "-c",
                                  "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ok', flush=True); time.sleep(60)"],
                                 stdout=subprocess.PIPE)
        try:
            child.stdout.readline()
            app = make_app()
            st = app.tasks
            st.rows = [{"pid": child.pid, "pids": [child.pid], "name": "stubborn", "app": "stubborn",
                        "uid": os.getuid(), "user": "me", "ppid": os.getpid()}]
            mod.tasks_key(app, "x")
            mod.tasks_key(app, "y")
            st.pending["deadline"] = 0
            mod.task_check_pending(st)
            self.assertTrue(st.confirm and st.confirm["force"])
            mod.tasks_key(app, "y")  # SIGKILL
            child.wait(timeout=5)
            self.assertEqual(child.returncode, -9)
        finally:
            if child.poll() is None:
                child.kill()
            child.stdout.close()

    def test_block_self(self):
        app = make_app()
        st = app.tasks
        st.rows = [{"pid": os.getpid(), "pids": [os.getpid()], "name": "me", "app": "me",
                    "uid": os.getuid(), "user": "me", "ppid": os.getppid()}]
        mod.tasks_key(app, "x")
        self.assertIsNone(st.confirm)
        self.assertIn("AgentOp", st.message[0])

    def test_navigation_and_filter_typing(self):
        app = make_app()
        st = app.tasks
        st.rows = [{"pid": i, "pids": [i], "name": f"p{i}"} for i in range(30)]
        mod.tasks_key(app, "DOWN")
        mod.tasks_key(app, "j")
        self.assertEqual(st.sel, 2)
        mod.tasks_key(app, "END")
        self.assertEqual(st.sel, 29)
        mod.tasks_key(app, "HOME")
        self.assertEqual(st.sel, 0)
        mod.tasks_key(app, "/")
        for ch in "фай":
            mod.tasks_key(app, ch)
        self.assertEqual(st.filter, "фай")
        mod.tasks_key(app, "\x7f")
        self.assertEqual(st.filter, "фа")
        mod.tasks_key(app, "ENTER")
        self.assertFalse(st.typing)
        mod.tasks_key(app, "m")
        self.assertEqual(st.sort, "mem")
        app.view = "tasks"
        st.back_view = "gauges"
        mod.tasks_key(app, "ESC")  # сначала сбрасывает поиск
        self.assertEqual(st.filter, "")
        mod.tasks_key(app, "ESC")  # потом возвращает к прошлому виду
        self.assertEqual(app.view, "gauges")


class ViewsTests(unittest.TestCase):
    def test_all_views_all_sizes(self):
        app = make_app()
        data = app.sample()
        data["tasks"] = app.procs.snapshot()
        now = __import__("time").time()
        iso = lambda ts: mod.datetime.fromtimestamp(ts).astimezone().isoformat()
        data["limits"] = {"five_hour": {"utilization": 63, "resets_at": iso(now + 7200)},
                          "seven_day": {"utilization": 12, "resets_at": iso(now + 3 * 86400)}}
        data["limits_hist"] = {"5h": [(now - 3000, 30.0), (now - 1500, 45.0), (now - 300, 60.0)], "7d": []}
        app.cache["week"] = {"ts": now, "start": now - 6 * 86400,
                             "grid": [[(d * 24 + h) % 7 * 100 for h in range(24)] for d in range(7)]}
        for view in mod.VIEWS:
            app.view = view
            for W, H in ((120, 40), (80, 24), (52, 18), (30, 12)):
                lines = mod.render(app, data, W, H)
                self.assertLessEqual(len(lines), H, (view, W, H))
                for ln in lines:
                    self.assertLessEqual(mod.vlen(ln), W, (view, W, H, ln))

    def test_narrow_falls_back_to_sidebar(self):
        app = make_app("gauges")
        data = app.sample()
        text = "\n".join(mod.render(app, data, 34, 30))
        self.assertIn("ЛИМИТЫ", text)

    def test_brief_sentences(self):
        app = make_app()
        data = app.sample()
        now = __import__("time").time()
        iso = lambda ts: mod.datetime.fromtimestamp(ts).astimezone().isoformat()
        data["limits"] = {"five_hour": {"utilization": 60, "resets_at": iso(now + 3600)},
                          "seven_day": {"utilization": 5, "resets_at": iso(now + 86400)}}
        data["limits_hist"] = {"5h": [(now - 1500, 20.0)]}
        text = "\n".join(mod.brief_lines(data, mod.Theme("mono")))
        self.assertIn("Окно 5 часов заполнено на 60%", text)
        self.assertIn("Лимит закончится", text)

    def test_panel_styles_and_png(self):
        app = make_app()
        data = app.sample()
        now = __import__("time").time()
        iso = lambda ts: mod.datetime.fromtimestamp(ts).astimezone().isoformat()
        data["limits"] = {"five_hour": {"utilization": 85, "resets_at": iso(now + 3600)},
                          "seven_day": {"utilization": 5, "resets_at": iso(now + 86400)}}
        for style in mod.PANEL_STYLES:
            out = mod.argos_out(app, data, style)
            first = out.splitlines()[0]
            self.assertIn("useMarkup=true", first, style)
            if style in ("ring", "bars"):
                self.assertIn("image=", first)
        self.assertTrue(mod.ring_png(50).startswith(b"\x89PNG"))
        self.assertTrue(mod.bars_png(10, 90).startswith(b"\x89PNG"))
        self.assertIn("&lt;", mod._pango("<b>"))

    def test_feed_from_tail(self):
        proj = Path(TMP_HOME, ".claude/projects/f")
        proj.mkdir(parents=True, exist_ok=True)
        now = mod.datetime.now().astimezone().isoformat()
        (proj / "s.jsonl").write_text(json.dumps({
            "type": "assistant", "timestamp": now, "requestId": "r1",
            "message": {"id": "m1", "model": "claude-opus-5-5",
                        "usage": {"input_tokens": 10, "output_tokens": 1000}}}) + "\n")
        try:
            tail = mod.ClaudeTail(1800)
            tail.poll(force=True)
        finally:
            shutil.rmtree(Path(TMP_HOME, ".claude"))
        self.assertEqual(len(tail.feed), 1)
        self.assertEqual(tail.feed[0]["out"], 1000)
        self.assertAlmostEqual(tail.feed[0]["cost"], (10 * 4 + 1000 * 20) / 1e6)
