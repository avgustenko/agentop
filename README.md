# AgentOp

**A terminal dashboard for AI coding agents** — Claude limits, token spend, token speed and system health in one live TUI. Think `top`, but for your agents + machine.

```
╭─ ● AGENTOP 1.3.0 · catppuccin-mocha ─────────────── 15:42:07 · 88% · 46°C · up 30м ─╮
│ ▐ LIMITS ───────────────────────────────────── │ ▐ CPU ────────────────────────────────────── │
│   5h  ░░░░░░░░░░░░ 0.000%  ↻ 4ч 32м            │   total ██░░░░░░░░░░  15%  ▁                  │
│   7d  ███░░░░░░░░░ 23.000%  ↻ 14ч 02м          │   C0 █████ 100  C1 ░░░░░   2  C2 ░░░░░   9   │
│ ▐ ТОКЕНЫ · СЕГОДНЯ ─────────────────────────── │   C3 ░░░░░   0  C4 █░░░░  30  C5 ░░░░░   2   │
│   Claude   0 in · 0 out · 0 cache              │   C6 ░░░░░   7  C7 ░░░░░   0  C8 █░░░░  14   │
│   opencode 140.2K in · 47.3K out · $0.401      │   load 0.51 0.53 0.40  ▁                     │
│ ▐ СКОРОСТЬ ТОКЕНОВ ─────────────────────────── │ ▐ ПАМЯТЬ · ТЕМПЕРАТУРА · GPU ─────────────── │
│   now 101.13 tok/s  peak 173.42                │   RAM  ██░░░░░░░░  19%  2.8/14.9G  swap 0.0/4 │
│   ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▃▂▁█▁▁▅▂▄▄▄▄▃              │   temp ███░░░░░░░  49°C  ▁                   │
│                                                │   GPU  ░░░░░░░░░░   0%  gpu 47°C             │
│                                                │ ▐ ПИТАНИЕ ─────────────────────────────────── │
│                                                │   BAT ███████████████░  93%  разряд          │
│                                                │ ▐ ДИСК · СЕТЬ ─────────────────────────────── │
│                                                │   disk ██░░░░░░░░░░ 38/196G  r 0B/s  w 0B/s  │
│                                                │   net  ↓ 7.7K/s  ↑ 5.4K/s  wlp2s0            │
╰─ [r] обновить   [t] тема   [p] пауза   [q] выход ─────────────────────────────────╯
```

## Features

- **Claude limits** — the official 5-hour and weekly windows, with reset countdown and a `pace` forecast (how much of the quota you will have used by reset at the current rate).
- **Token spend today** — input / output / cache tokens and cost for [Claude Code](https://claude.com/claude-code) and [opencode](https://opencode.ai).
- **Token speed** — now / 1 min / 5 min / peak, with a gradient sparkline or a multi-line Braille graph on tall terminals.
- **System** — total + per-core CPU, load average, RAM/swap, CPU temp, GPU load/temp, battery (charge, power, time left), disk usage + I/O, network throughput.
- **Themes** — `catppuccin-mocha`, `catppuccin-latte`, `dracula`, `nord`, `gruvbox`, `tokyo-night`, `solarized-dark`, `matrix`, `mono`, plus `auto` (follows the GNOME light/dark scheme).
- **Two layouts** — a two-column dashboard on wide terminals (≥96 cols), a single clean column on narrow ones.
- **Low overhead** — ~0.4 % CPU, ~40 MB RAM, one wakeup per second, redraws only when data changes. Press `p` to pause (0 % CPU).
- **Per-model spend** — today's usage per model (opus/sonnet, deepseek-flash/v4-pro); for Claude, what it would cost at API prices (5 min / 1 h cache writes and fast mode included).
- **Limit trend** — a limits log (`~/.cache/agentop/limits_history.jsonl`, 8 days) drives a sparkline of the current window and a forecast at reset based on the last 30 minutes.
- **Notifications** — `notify-send` at 80 % and 95 % of a window, once per window.
- **Machine-readable** — `--short` (one line), `--json`, `--waybar` (Waybar custom module) and `--argos` (GNOME top bar via the Argos extension).
- **Russian keyboard layout** — hotkeys work on ЙЦУКЕН too (`к` = `r`, `й` = `q`, …).

## Views

Switch views with `v` (saved to config) or `--view`:

| View | What it shows |
|---|---|
| `dashboard` | agents + system; two columns on wide terminals, one on narrow |
| `focus` | only limits, tokens and token speed |
| `system` | only hardware: CPU, memory/temp/GPU, power, disk/network, processes |
| `compact` | single column, total CPU only — good for small panes |
| `minimal` | 5–6 lines: limits, tok/s, load, CPU, battery |

```bash
agentop --view focus
agentop --list-views
```

## Settings

Press `s` in the live view. Change the refresh interval from **0.01 s to 300 s**, theme, view, sparkline history, decimals and which sections to show. Changes are saved to `~/.config/agentop/config.json` immediately.

![](docs/settings.png)

## Themes

`auto` follows the GNOME light/dark scheme. Switch with `t`, `--theme` or `--set-theme`.

| | |
|---|---|
| **Catppuccin Mocha**<br>![](docs/themes/catppuccin-mocha.png) | **Catppuccin Latte**<br>![](docs/themes/catppuccin-latte.png) |
| **Dracula**<br>![](docs/themes/dracula.png) | **Nord**<br>![](docs/themes/nord.png) |
| **Gruvbox**<br>![](docs/themes/gruvbox.png) | **Tokyo Night**<br>![](docs/themes/tokyo-night.png) |
| **Matrix**<br>![](docs/themes/matrix.png) | **Mono**<br>![](docs/themes/mono.png) |

## Requirements

- Linux (reads `/proc` and `/sys`), Python 3.9+
- `ps` from `procps` (for the top-processes section)
- Optional: Claude Code (`~/.claude`) for limits/tokens, opencode for its stats, `gsettings` for `auto` theme

## Install

```bash
git clone https://github.com/avgustenko/agentop.git
cd agentop
./install.sh
```

The installer copies `agentop` to `~/.local/bin` and adds a desktop entry. Make sure `~/.local/bin` is in your `PATH`.

### Manual

```bash
install -m 755 agentop ~/.local/bin/agentop
agentop
```

## Usage

```bash
agentop                 # live dashboard
agentop --short         # one line (status bar / prompt)
agentop --json          # machine-readable snapshot
agentop --waybar        # Waybar custom module JSON
agentop --argos         # GNOME top bar (Argos extension)
agentop --once          # render once and exit
agentop -i 2            # refresh every 2 s (default 1 s)
agentop --theme nord    # theme for this run
agentop --set-theme nord
agentop --list-themes
agentop --view focus    # view for this run
agentop --list-views
agentop --refresh       # drop caches, refetch limits
agentop --config        # show config path + contents
agentop --ms            # centisecond clock, ~100 FPS (heavy)
agentop --version
```

In the live view:

| Key | Action |
|---|---|
| `r` | refresh now (caches + limits) |
| `t` | next theme (saved to config) |
| `v` | next view (saved to config) |
| `s` | settings screen (interval 0.01–300 s) |
| `p` | pause / resume (0 % CPU while paused) |
| `q` | quit |

## Configuration

`~/.config/agentop/config.json` is created on first run. See [`config.example.json`](config.example.json):

```json
{
  "theme": "auto",
  "view": "dashboard",
  "interval": 1.0,
  "history": 120,
  "history_interval": 2.0,
  "limit_decimals": 3,
  "clock_ms": false,
  "notify": true,
  "notify_thresholds": [80, 95],
  "show": {"network": true, "disk": true, "processes": true, "gpu": true, "per_core": true,
           "models": true}
}
```

- `interval` — UI tick, seconds.
- `history` × `history_interval` — length of sparkline history.
- `limit_decimals` — decimals for limit percentages (the API currently returns whole percents, so you'll see `.000`).
- `show.*` — toggle sections.
- `notify`, `notify_thresholds` — limit notifications (thresholds in %).
- `prices` — override built-in prices: `{"claude-opus-5-5": [input, output, cache write 5m, cache read]}`, USD per 1M tokens.

### GNOME top bar (Argos)

Install the [Argos](https://github.com/p-e-w/argos) extension and create `~/.config/argos/agentop.30s.sh`:

```bash
#!/usr/bin/env bash
exec ~/.local/bin/agentop --argos
```

### Waybar

```json
"custom/agentop": {"exec": "agentop --waybar", "return-type": "json", "interval": 30}
```

## How it works

| Data | Source |
|---|---|
| Claude limits | `https://api.anthropic.com/api/oauth/usage` using your local Claude Code OAuth token (the same endpoint `/usage` uses). Fetched every 30 s in a background thread; `r` forces an immediate refresh. The LIMITS title shows the data age. |
| Claude tokens | `~/.claude/projects/**/*.jsonl` (incremental tail, deduplicated by `requestId` + `message.id`) |
| opencode tokens/cost | `~/.local/share/opencode/opencode.db` (SQLite, read-only) |
| Hardware | `/proc/stat`, `/proc/meminfo`, `/proc/diskstats`, `/proc/net/route`, `/sys/class/*` |

**Privacy:** no telemetry. The OAuth token is read locally and sent only to Anthropic; it is never printed or written to the cache. Caches contain numbers only and are created with `0600` permissions.

## Notes

- The TUI labels are currently in Russian. The code and docs are English-friendly; PRs for i18n are welcome.
- The limit API returns whole percents, so `xxx.xxx%` currently shows `.000` after the dot.
- On `HTTP 429` the widget keeps the last successful limits response and backs off.
- The Claude "API price" figure is an estimate for comparison with your subscription, not a bill.
- Claude log parsing and the limits request are the only non-trivial operations; both are cached and/or backgrounded.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

43 tests: formatting, ANSI/clip/pad, theme bars, sparklines, Braille graphs, settings, all views, key input (UTF-8, Russian layout, EOF), pricing, the limits log and trend, notifications, Waybar/Argos output and CLI smoke tests. Tests run with a temporary `HOME`, so they never read your logs or call the API with your token. CI runs them on every push.

## License

[MIT](LICENSE)
