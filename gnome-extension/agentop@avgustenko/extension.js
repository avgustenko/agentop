// AgentOp — индикатор лимитов Claude в верхней панели GNOME Shell (45+).
// Данные: `agentop --json` раз в 30 секунд (блок "panel"). Сеть и токены
// расширение не трогает — всё делает сам agentop.

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const REFRESH_S = 30;
const TICK_S = 3;
const STYLE_NAMES = {
    text: 'Текст', forecast: 'Прогноз', dot: 'Только точка', cells: 'Ячейки батареи',
    countdown: 'Обратный отсчёт', pulse: 'Пульс', rotate: 'Карусель', ring: 'Кольцо', bars: 'Два столбика',
};
const SPARK = '▁▂▃▄▅▆▇█';
const COLORS = {good: [0.65, 0.89, 0.63], warn: [0.98, 0.89, 0.69], crit: [0.95, 0.55, 0.66],
    accent: [0.80, 0.65, 0.97], dim: [0.55, 0.55, 0.63]};

// ── чистые функции (проверяются тестами без GNOME) ──
export function level(p) {
    return p >= 95 ? 'crit' : p >= 80 ? 'warn' : 'good';
}

export function humanLeft(sec) {
    sec = Math.max(0, Math.floor(sec || 0));
    const d = Math.floor(sec / 86400), h = Math.floor(sec % 86400 / 3600), m = Math.floor(sec % 3600 / 60);
    if (d)
        return `${d}д ${h}ч`;
    if (h)
        return `${h}ч ${String(m).padStart(2, '0')}м`;
    return `${m}м`;
}

function win(panel, label) {
    const w = panel && panel[label];
    return w && !w.expired ? w : null;
}

// Текст индикатора: [{text, cls}] — части с цветом.
export function indicatorParts(panel, style, tick = 0) {
    const w5 = win(panel, '5h'), w7 = win(panel, '7d');
    if (!panel || panel.error || !w5) {
        if (style === 'pulse' && panel && panel.speed)
            return pulseParts(panel);
        return [{text: panel && panel['5h'] && panel['5h'].expired ? '5h reset' : 'claude --', cls: 'dim'}];
    }
    const u5 = w5.used, u7 = w7 ? w7.used : null, lv = level(u5);
    const pct = v => `${Math.round(v)}%`;
    switch (style) {
    case 'forecast': {
        const p = w5.proj ?? u5;
        return [{text: '5h '}, {text: '→ ', cls: 'dim'},
            {text: pct(Math.min(999, p)), cls: p >= 100 ? 'crit' : p >= 85 ? 'warn' : 'good'}];
    }
    case 'dot':
        return u5 >= 80 ? [{text: `● 5h ${pct(u5)}`, cls: lv}] : [{text: '●', cls: 'good'}];
    case 'cells': {
        const f = Math.round((100 - u5) / 10);
        return [{text: '▮'.repeat(f), cls: lv}, {text: '▯'.repeat(10 - f), cls: 'dim'}];
    }
    case 'countdown': {
        const r = Math.max(0, Math.floor(w5.rem || 0));
        return [{text: '● ', cls: lv}, {text: `↻ ${Math.floor(r / 3600)}:${String(Math.floor(r % 3600 / 60)).padStart(2, '0')}`}];
    }
    case 'pulse':
        return pulseParts(panel);
    case 'rotate': {
        const items = [[{text: `5h ${pct(u5)}`, cls: u5 >= 80 ? lv : null}],
            [{text: u7 === null ? '7d --' : `7d ${pct(u7)}`}],
            [{text: `${Math.round(panel.speed ? panel.speed.now : 0)} t/s`}],
            [{text: `≈$${Math.round(panel.claude_cost_api || 0)}`}]];
        return items[tick % items.length];
    }
    case 'ring':
        return [{text: pct(u5), cls: u5 >= 80 ? lv : null}];
    case 'bars':
        return [];
    default: {
        const worst = Math.max(u5, u7 ?? 0);
        return [{text: `5h ${pct(u5)}` + (u7 === null ? '' : ` · 7d ${pct(u7)}`), cls: worst >= 80 ? level(worst) : null}];
    }
    }
}

function pulseParts(panel) {
    const b = (panel.speed && panel.speed.buckets || []).slice(-6);
    const hi = Math.max(1, ...b);
    return [{text: b.map(x => SPARK[Math.floor(x / hi * 7)]).join(''), cls: 'dim'},
        {text: ` ${Math.round(panel.speed ? panel.speed.now : 0)} t/s`}];
}

export function summaryLine(panel) {
    const w5 = win(panel, '5h');
    if (!w5)
        return 'Прогноз появится, когда будут данные о лимитах';
    if (w5.rate_h === null || w5.rate_h === undefined)
        return 'Прогноз появится через 10 минут журнала';
    const p = w5.proj ?? w5.used;
    if (p >= 100 && w5.rate_h > 0) {
        const secs = (100 - w5.used) / w5.rate_h * 3600;
        return `Темп ${Math.round(w5.rate_h)}%/ч — закончится через ${humanLeft(secs)}`;
    }
    return `Темп ${Math.round(w5.rate_h)}%/ч · к сбросу ≈${Math.round(p)}% — хватит`;
}

// ── отрисовка cairo ──
function setColor(cr, rgb, a = 1) {
    cr.setSourceRGBA(rgb[0], rgb[1], rgb[2], a);
}

function drawRing(area, pct) {
    const cr = area.get_context();
    const [w, h] = area.get_surface_size();
    const r = Math.min(w, h) / 2 - 2, cx = w / 2, cy = h / 2;
    cr.setLineWidth(Math.max(2, r * 0.38));
    setColor(cr, [1, 1, 1], 0.22);
    cr.arc(cx, cy, r, 0, 2 * Math.PI);
    cr.stroke();
    const lv = level(pct);
    setColor(cr, pct >= 80 ? COLORS[lv] : COLORS.accent);
    cr.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * Math.min(100, pct) / 100);
    cr.stroke();
    cr.$dispose();
}

function drawBars(area, a, b) {
    const cr = area.get_context();
    const [w, h] = area.get_surface_size();
    const bw = Math.floor(w / 2) - 2;
    [[1, a], [w - bw - 1, b]].forEach(([x, p]) => {
        setColor(cr, [1, 1, 1], 0.22);
        cr.rectangle(x, 1, bw, h - 2);
        cr.fill();
        setColor(cr, p >= 80 ? COLORS[level(p)] : COLORS.accent);
        const fh = (h - 2) * Math.min(100, p) / 100;
        cr.rectangle(x, h - 1 - fh, bw, fh);
        cr.fill();
    });
    cr.$dispose();
}

function drawChart(area, w5, now) {
    const cr = area.get_context();
    const [w, h] = area.get_surface_size();
    const top = 6, bottom = h - 4, ys = v => bottom - (bottom - top) * Math.min(100, v) / 100;
    const start = w5.reset - w5.window, xs = t => (t - start) / w5.window * w;
    // 80%
    setColor(cr, [1, 1, 1], 0.18);
    cr.setLineWidth(1);
    cr.setDash([2, 4], 0);
    cr.moveTo(0, ys(80));
    cr.lineTo(w, ys(80));
    cr.stroke();
    cr.setDash([], 0);
    const pts = (w5.history || []).filter(p => p[0] >= start).concat([[now, w5.used]]);
    if (pts.length) {
        cr.moveTo(xs(pts[0][0]), bottom);
        pts.forEach(([t, v]) => cr.lineTo(xs(t), ys(v)));
        cr.lineTo(xs(now), bottom);
        cr.closePath();
        setColor(cr, COLORS.accent, 0.28);
        cr.fill();
        cr.setLineWidth(2);
        cr.moveTo(xs(pts[0][0]), ys(pts[0][1]));
        pts.forEach(([t, v]) => cr.lineTo(xs(t), ys(v)));
        setColor(cr, COLORS.accent);
        cr.stroke();
    }
    if (w5.proj !== null && w5.proj !== undefined) {
        cr.setDash([3, 4], 0);
        cr.setLineWidth(1.5);
        setColor(cr, w5.proj >= 100 ? COLORS.crit : COLORS.dim);
        cr.moveTo(xs(now), ys(w5.used));
        cr.lineTo(w, ys(w5.proj));
        cr.stroke();
        cr.setDash([], 0);
    }
    setColor(cr, [1, 1, 1], 0.95);
    cr.arc(xs(now), ys(w5.used), 3.5, 0, 2 * Math.PI);
    cr.fill();
    setColor(cr, [1, 1, 1], 0.25);
    cr.setLineWidth(1);
    cr.moveTo(0, bottom + 0.5);
    cr.lineTo(w, bottom + 0.5);
    cr.stroke();
    cr.$dispose();
}

// ── индикатор ──
const AgentOpIndicator = GObject.registerClass(
class AgentOpIndicator extends PanelMenu.Button {
    _init(ext) {
        super._init(0.5, 'AgentOp');
        this._ext = ext;
        this._panel = null;
        this._tick = 0;
        this._busy = false;
        this._cancel = new Gio.Cancellable();
        this._bin = ext.agentopPath();

        const box = new St.BoxLayout({style_class: 'agentop-indicator', y_align: Clutter.ActorAlign.CENTER});
        this._icon = new St.DrawingArea({width: 16, height: 16, y_align: Clutter.ActorAlign.CENTER, visible: false});
        this._icon.connect('repaint', a => this._paintIcon(a));
        this._label = new St.Label({style_class: 'agentop-label', y_align: Clutter.ActorAlign.CENTER, text: '…'});
        this._label.clutter_text.use_markup = true;
        box.add_child(this._icon);
        box.add_child(this._label);
        this.add_child(box);
        this._buildMenu();

        this.menu.connect('open-state-changed', (_m, open) => {
            if (open)
                this._refresh();
        });
        this._refresh();
        this._refreshId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, REFRESH_S, () => {
            this._refresh();
            return GLib.SOURCE_CONTINUE;
        });
        this._tickId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, TICK_S, () => {
            this._tick++;
            if (this._style() === 'rotate')
                this._renderIndicator();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _style() {
        return (this._panel && this._panel.style) || 'text';
    }

    _buildMenu() {
        const item = new PopupMenu.PopupBaseMenuItem({reactive: false, can_focus: false});
        const card = new St.BoxLayout({vertical: true, style_class: 'agentop-card', x_expand: true});
        item.add_child(card);

        const row = new St.BoxLayout({style_class: 'agentop-row', x_expand: true});
        const left = new St.BoxLayout({vertical: true, x_expand: true});
        left.add_child(new St.Label({text: 'Окно 5 часов', style_class: 'agentop-caption'}));
        this._big = new St.Label({text: '—', style_class: 'agentop-big'});
        left.add_child(this._big);
        const right = new St.BoxLayout({vertical: true, x_align: Clutter.ActorAlign.END});
        right.add_child(new St.Label({text: 'сброс через', style_class: 'agentop-caption', x_align: Clutter.ActorAlign.END}));
        this._reset = new St.Label({text: '—', style_class: 'agentop-mid', x_align: Clutter.ActorAlign.END});
        right.add_child(this._reset);
        row.add_child(left);
        row.add_child(right);
        card.add_child(row);

        this._chart = new St.DrawingArea({height: 90, x_expand: true});
        this._chart.connect('repaint', a => {
            const w5 = win(this._panel, '5h');
            if (w5)
                drawChart(a, w5, this._panel.now);
        });
        card.add_child(this._chart);
        this._summary = new St.Label({text: '', style_class: 'agentop-caption'});
        card.add_child(this._summary);

        const wk = new St.BoxLayout({vertical: true});
        const wkRow = new St.BoxLayout({x_expand: true});
        wkRow.add_child(new St.Label({text: 'Неделя', x_expand: true}));
        this._week = new St.Label({text: '—'});
        wkRow.add_child(this._week);
        wk.add_child(wkRow);
        this._meter = new St.Widget({style_class: 'agentop-meter', x_expand: true});
        this._meterFill = new St.Widget({style_class: 'agentop-meter-fill'});
        this._meter.add_child(this._meterFill);
        wk.add_child(this._meter);
        card.add_child(wk);

        this._costs = new St.Label({text: '', style_class: 'agentop-caption'});
        card.add_child(this._costs);
        this.menu.addMenuItem(item);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        this.menu.addAction('Открыть AgentOp', () => this._launch([]));
        this.menu.addAction('Диспетчер задач', () => this._launch(['--view', 'tasks']));
        this.menu.addAction('Обновить сейчас', () => this._refresh(true));

        this._styleMenu = new PopupMenu.PopupSubMenuMenuItem('Вид индикатора');
        this._styleItems = {};
        Object.entries(STYLE_NAMES).forEach(([id, name]) => {
            const it = new PopupMenu.PopupMenuItem(name);
            it.connect('activate', () => this._setStyle(id));
            this._styleMenu.menu.addMenuItem(it);
            this._styleItems[id] = it;
        });
        this.menu.addMenuItem(this._styleMenu);
    }

    _paintIcon(area) {
        const w5 = win(this._panel, '5h');
        if (!w5)
            return;
        if (this._style() === 'bars') {
            const w7 = win(this._panel, '7d');
            drawBars(area, w5.used, w7 ? w7.used : 0);
        } else {
            drawRing(area, w5.used);
        }
    }

    _renderIndicator() {
        const style = this._style();
        const parts = indicatorParts(this._panel, style, Math.floor(this._tick));
        const esc = s => GLib.markup_escape_text(s, -1);
        const hex = {good: '#a6e3a1', warn: '#f9e2af', crit: '#f38ba8', dim: '#8d8da0'};
        this._label.clutter_text.set_markup(parts.map(p => p.cls
            ? `<span foreground="${hex[p.cls]}">${esc(p.text)}</span>` : esc(p.text)).join(''));
        this._label.visible = parts.length > 0;
        this._icon.visible = (style === 'ring' || style === 'bars') && !!win(this._panel, '5h');
        this._icon.width = style === 'bars' ? 14 : 16;
        this._icon.queue_repaint();
    }

    _renderMenu() {
        const p = this._panel, w5 = win(p, '5h'), w7 = win(p, '7d');
        if (w5) {
            this._big.text = `${Math.round(w5.used)}%`;
            this._big.style_class = `agentop-big agentop-${w5.used >= 80 ? level(w5.used) : 'none'}`;
            this._reset.text = humanLeft(w5.rem);
        } else {
            this._big.text = p && p.error ? '—' : '…';
            this._reset.text = p && p['5h'] && p['5h'].expired ? 'сброшено' : '—';
        }
        this._summary.text = p && p.error ? `Claude: ${p.error}` : summaryLine(p);
        if (w7) {
            this._week.text = `${w7.used.toFixed(1)}% · ↻ ${humanLeft(w7.rem)}`;
            const lv = w7.used >= 80 ? ` agentop-${level(w7.used)}` : '';
            this._meterFill.style_class = `agentop-meter-fill${lv}`;
            const full = this._meter.width || 320;
            this._meterFill.width = Math.round(full * Math.min(100, w7.used) / 100);
        } else {
            this._week.text = '—';
            this._meterFill.width = 0;
        }
        if (p)
            this._costs.text = `Claude сегодня ≈$${(p.claude_cost_api || 0).toFixed(2)} по ценам API · opencode $${(p.opencode_cost || 0).toFixed(2)}`;
        Object.entries(this._styleItems).forEach(([id, it]) =>
            it.setOrnament(id === this._style() ? PopupMenu.Ornament.DOT : PopupMenu.Ornament.NONE));
        this._chart.queue_repaint();
    }

    _refresh(force = false) {
        if (this._busy || !this._bin)
            return;
        this._busy = true;
        const argv = [this._bin, '--json'].concat(force ? ['--refresh'] : []);
        let proc;
        try {
            proc = Gio.Subprocess.new(argv, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE);
        } catch (e) {
            this._busy = false;
            this._label.text = 'agentop?';
            return;
        }
        proc.communicate_utf8_async(null, this._cancel, (pr, res) => {
            this._busy = false;
            try {
                const [, out] = pr.communicate_utf8_finish(res);
                this._panel = JSON.parse(out).panel || null;
            } catch (e) {
                if (e.matches && e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                    return;
                this._panel = {error: 'нет данных от agentop'};
            }
            this._renderIndicator();
            this._renderMenu();
        });
    }

    _setStyle(id) {
        if (this._panel)
            this._panel.style = id;
        this._renderIndicator();
        this._renderMenu();
        try {
            Gio.Subprocess.new([this._bin, '--set-panel-style', id], Gio.SubprocessFlags.STDOUT_SILENCE);
        } catch (e) {
            logError(e, 'AgentOp: не удалось сохранить стиль');
        }
    }

    _launch(extra) {
        this.menu.close();
        const term = ['ghostty', 'kgx', 'gnome-terminal'].find(t => GLib.find_program_in_path(t));
        if (!term) {
            Main.notify('AgentOp', 'Не найден терминал: установите ghostty или gnome-terminal');
            return;
        }
        const cmd = [this._bin].concat(extra);
        const argv = term === 'gnome-terminal' ? [term, '--'].concat(cmd) : [term, '-e'].concat(cmd);
        try {
            Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE);
        } catch (e) {
            logError(e, 'AgentOp: не удалось открыть терминал');
        }
    }

    destroy() {
        this._cancel.cancel();
        if (this._refreshId)
            GLib.source_remove(this._refreshId);
        if (this._tickId)
            GLib.source_remove(this._tickId);
        this._refreshId = this._tickId = 0;
        super.destroy();
    }
});

export default class AgentOpExtension extends Extension {
    agentopPath() {
        const local = GLib.build_filenamev([GLib.get_home_dir(), '.local', 'bin', 'agentop']);
        if (GLib.file_test(local, GLib.FileTest.IS_EXECUTABLE))
            return local;
        return GLib.find_program_in_path('agentop');
    }

    enable() {
        this._indicator = new AgentOpIndicator(this);
        Main.panel.addToStatusArea(this.uuid, this._indicator, 0, 'right');
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
