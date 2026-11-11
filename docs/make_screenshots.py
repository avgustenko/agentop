#!/usr/bin/env python3
"""Скриншоты видов AgentOp для README — на примерных данных, без ваших логов и процессов.

    python3 docs/make_screenshots.py      # нужен Pillow; пишет docs/views/*.png
"""
import importlib.machinery
import importlib.util
import os
import random
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["HOME"] = tempfile.mkdtemp(prefix="agentop-shots-")   # никаких настоящих данных
os.environ.pop("NO_COLOR", None)
loader = importlib.machinery.SourceFileLoader("agentop_mod", str(ROOT / "agentop"))
spec = importlib.util.spec_from_loader("agentop_mod", loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)
m.COLOR = True

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"   # точки Брайля
SIZE = 15
OUT = ROOT / "docs" / "views"


def x256(n):
    base = [(0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0), (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
            (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255)]
    if n < 16:
        return base[n]
    if n < 232:
        n -= 16
        lv = [0, 95, 135, 175, 215, 255]
        return lv[n // 36], lv[n // 6 % 6], lv[n % 6]
    v = 8 + (n - 232) * 10
    return v, v, v


def to_png(lines, path, bg=(30, 30, 46), fg=(208, 208, 208)):
    font = ImageFont.truetype(FONT, SIZE)
    fb = ImageFont.truetype(FONT_FALLBACK, SIZE)
    cw = font.getlength("M")
    lh = int(SIZE * 1.3)
    cols = max(m.vlen(x) for x in lines)
    img = Image.new("RGB", (int(cols * cw) + 32, len(lines) * lh + 28), bg)
    d = ImageDraw.Draw(img)
    for row, line in enumerate(lines):
        x, col, back = 0, fg, None
        for tok in re.split(r"(\x1b\[[0-9;]*m)", line):
            if tok.startswith("\x1b["):
                codes = [int(c) for c in tok[2:-1].split(";") if c]
                if codes in ([0], []):
                    col, back = fg, None
                for i in range(len(codes) - 2):
                    if codes[i] == 38 and codes[i + 1] == 5:
                        col = x256(codes[i + 2])
                    if codes[i] == 48 and codes[i + 1] == 5:
                        back = x256(codes[i + 2])
                continue
            for ch in tok:
                px, py = 16 + x * cw, 14 + row * lh
                if back:
                    d.rectangle([px, py, px + cw + 1, py + lh], fill=back)
                d.text((px, py), ch, font=fb if 0x2800 <= ord(ch) <= 0x28FF else font, fill=col)
                x += 1
    img.save(path, optimize=True)


def demo_data(app):
    now = time.time()
    iso = lambda ts: m.datetime.fromtimestamp(ts).astimezone().isoformat()
    data = app.sample()
    data["limits"] = {"five_hour": {"utilization": 64, "resets_at": iso(now + 2 * 3600 + 35 * 60)},
                      "seven_day": {"utilization": 23, "resets_at": iso(now + 4 * 86400 + 5 * 3600)},
                      "_fetched_at": now - 12}
    data["limits_hist"] = {"5h": [(now - 8400 + i * 300, round(64 * (i / 28) ** 1.25)) for i in range(28)], "7d": []}
    data["claude"] = {"totals": {"input": 1840, "output": 523400, "cache_read": 141_200_000, "cache_write": 2_300_000,
                                 "messages": 412, "cost_api": 58.73},
                      "models": {"claude-opus-5-5": {"output": 498000, "cache_read": 138_000_000, "messages": 398, "cost_api": 56.10},
                                 "claude-sonnet-5-5": {"output": 25400, "cache_read": 3_200_000, "messages": 14, "cost_api": 2.63}}}
    data["opencode"] = {"today": {"cost": 1.284, "input": 812000, "output": 402000, "reasoning": 51000, "cache_read": 96_000_000},
                        "models": {"deepseek-flash": {"cost": 0.71, "output": 380000, "reasoning": 40000, "cache_read": 80_000_000, "messages": 61},
                                   "deepseek-v4-pro": {"cost": 0.574, "output": 22000, "reasoning": 11000, "cache_read": 16_000_000, "messages": 9}},
                        "all_cost": 14.92}
    random.seed(4)
    sp = []
    v = 120
    for i in range(400):
        v = max(0, min(320, v + random.uniform(-60, 60)))
        sp.append((now - 1800 + i * 4.5, int(v * 4.5), "claude-opus-5-5"))
    app.speed.claude.events = sp
    app.speed.oc = []
    app.speed._snap = None
    data["pcts"] = [("cpu", 18.0)] + [(f"cpu{i}", random.uniform(3, 60)) for i in range(12)]
    data["hist_cpu"] = [random.uniform(8, 30) for _ in range(60)]
    data["hist_load"] = [random.uniform(0.8, 2.4) for _ in range(60)]
    data["hist_temp"] = [random.uniform(48, 56) for _ in range(60)]
    data["hist_io"] = [random.uniform(0, 400000) for _ in range(60)]
    data.update(load=(1.84, 1.52, 1.21), mem=(15.6, 7.4, 4.0, 0.0), temp=52.0, gpu=14, gpu_temp=46.0,
                bat={"cap": 82, "status": "Discharging", "ac": False, "power": 9_800_000, "energy": 44_000_000, "full": 54_000_000},
                disk=(18_000, 220_000), net=(42_000, 9_000), iface="wlan0", root=(210e9, 88e9, 122e9), uptime=5400,
                procs=[(31.0, 9.1, "firefox"), (14.2, 2.0, "gnome-shell"), (8.0, 1.1, "ghostty"), (5.5, 3.2, "code")])
    apps = [("firefox", 31.2, 2.4e9, 14), ("code", 12.4, 1.1e9, 9), ("gnome-shell", 9.8, 3.2e8, 1), ("claude", 7.1, 9.4e8, 2),
            ("ghostty", 4.0, 2.0e8, 1), ("opencode", 3.2, 3.1e8, 1), ("telegram-desktop", 1.4, 6.0e8, 1), ("pipewire", 0.8, 3.0e7, 1),
            ("Xwayland", 0.6, 9.7e7, 1), ("postgres", 0.3, 9.1e7, 6), ("sshd", 0.0, 8.0e6, 1)]
    tasks, pid = [], 4100
    for name, cpu, rss, n in apps:
        for k in range(n):
            pid += 7
            tasks.append({"pid": pid, "name": name, "app": name, "cpu": cpu / n, "mem": rss / n / 16.7e9 * 100, "rss": rss / n,
                          "state": "S", "threads": 8, "uid": os.getuid(), "user": "postgres" if name == "postgres" else "you", "ppid": 1})
    data["tasks"] = tasks
    app.cache["week"] = {"ts": now, "start": now - 6 * 86400,
                         "grid": [[(0 if 1 <= h <= 8 else int(random.uniform(0.2, 1) * 90000 * (1 if 10 <= h <= 20 else 0.3)))
                                   for h in range(24)] for _ in range(7)]}
    app.speed.claude.feed = [{"ts": now - 600 + i * 40, "model": random.choice(["claude-opus-5-5"] * 5 + ["claude-sonnet-5-5"]),
                              "out": random.randint(200, 2600), "cache": random.randint(80, 700) * 1000,
                              "cost": random.uniform(0.02, 0.18), "api": True} for i in range(14)]
    app.cache["oc_feed"] = [{"ts": now - 500 + i * 120, "model": "deepseek-flash", "out": random.randint(300, 2000),
                             "cache": 120000, "cost": random.uniform(0.002, 0.01), "api": False} for i in range(4)]
    return data


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = dict(m.DEFAULT_CONFIG)
    cfg["theme"] = "catppuccin-mocha"
    app = m.App(cfg, threaded=False)
    time.sleep(0.3)
    sizes = {"dashboard": (118, 30), "sidebar": (36, 28), "beacon": (60, 14), "brief": (90, 20), "tasks": (110, 22),
             "minimal": (72, 8), "cockpit": (90, 16), "gauges": (100, 20), "timeline": (100, 20), "tiles": (110, 20)}
    for view in m.VIEWS:
        app.view = view
        data = demo_data(app)
        if view == "tasks":
            app.tasks.rows = []
        W, H = sizes.get(view, (100, 26))
        lines = m.render(app, data, W, H)
        while lines and not m.ANSI_RE.sub("", lines[-1]).strip():
            lines.pop()
        to_png(lines, OUT / f"{view}.png")
        print("✓", view)
    # верхняя панель: все стили индикатора
    print("готово:", OUT)


if __name__ == "__main__":
    sys.exit(main())
