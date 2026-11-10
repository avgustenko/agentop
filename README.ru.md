# AgentOp

**Терминальный дашборд для AI-агентов**: лимиты Claude, расход токенов, скорость токенов и здоровье системы в одном живом TUI. Этакий `top`, но для агентов и железа.

```
╭─ ● AGENTOP 1.1.0 · catppuccin-mocha ─────────────── 15:42:07 · 88% · 46°C · up 30м ─╮
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
╰─ [r] обновить   [t] тема   [p] пауза   [q] выход ─────────────────────────────────╯
```

## Возможности

- **Лимиты Claude** — официальные 5-часовое и недельное окна, время сброса и `pace` — прогноз расхода к моменту сброса.
- **Токены за сегодня** — in/out/cache и стоимость для [Claude Code](https://claude.com/claude-code) и [opencode](https://opencode.ai).
- **Скорость токенов** — now / 1 мин / 5 мин / peak, градиентный спарклайн или многострочный Braille-график.
- **Система** — CPU (общий и по ядрам), load average, RAM/swap, температура, GPU, батарея, диск, сеть.
- **Темы** — 9 штук + `auto` по схеме GNOME.
- **Два макета** — две колонки на широких терминалах (≥96), одна на узких.
- **Низкая нагрузка** — ~0.4 % CPU, ~40 МБ RAM, 1 пробуждение/с. `p` — пауза (0 % CPU).
- **Машинный вывод** — `--short` и `--json`.

## Виды

Переключение клавишей `v` (сохраняется в конфиг) или флагом `--view`:

| Вид | Что показывает |
|---|---|
| `dashboard` | агенты + система; две колонки на широких, одна на узких |
| `focus` | только лимиты, токены и скорость |
| `system` | только железо: CPU, память/температура/GPU, питание, диск/сеть, процессы |
| `compact` | одна колонка, CPU только общий — для маленьких панелей |
| `minimal` | 5–6 строк: лимиты, tok/s, load, CPU, батарея |

```bash
agentop --view focus
agentop --list-views
```

## Установка

```bash
git clone https://github.com/avgustenko/agentop.git
cd agentop
./install.sh
```

Или вручную:

```bash
install -m 755 agentop ~/.local/bin/agentop
agentop
```

## Использование

```bash
agentop                 # живой дашборд
agentop --short         # одна строка для статус-бара
agentop --json          # JSON
agentop --once          # один кадр
agentop -i 2            # обновление раз в 2 с (по умолчанию 1 с)
agentop --theme nord
agentop --set-theme nord
agentop --list-themes
agentop --view focus
agentop --list-views
agentop --refresh
agentop --config
agentop --ms            # сантисекунды, ~100 FPS (нагружает)
agentop --version
```

Клавиши: `r` — обновить, `t` — тема, `v` — вид, `p` — пауза, `q` — выход.

## Конфиг

`~/.config/agentop/config.json` (см. [`config.example.json`](config.example.json)):

```json
{
  "theme": "auto",
  "view": "dashboard",
  "interval": 1.0,
  "history": 120,
  "history_interval": 2.0,
  "limit_decimals": 3,
  "clock_ms": false,
  "show": {"network": true, "disk": true, "processes": true, "gpu": true, "per_core": true}
}
```

## Откуда данные

| Данные | Источник |
|---|---|
| Лимиты Claude | `api.anthropic.com/api/oauth/usage` с локальным OAuth-токеном Claude Code |
| Токены Claude | `~/.claude/projects/**/*.jsonl` |
| opencode | `~/.local/share/opencode/opencode.db` (read-only) |
| Железо | `/proc`, `/sys` |

**Приватность:** телеметрии нет. Токен читается локально и отправляется только Anthropic; в кэш не пишется (кэши — только цифры, права `0600`).

## Замечания

- Интерфейс сейчас на русском.
- API лимитов отдаёт целые проценты, поэтому `xxx.xxx%` показывает `.000`.
- При `429` виджет сохраняет последний удачный ответ и не долбит API.

## Лицензия

[MIT](LICENSE)
