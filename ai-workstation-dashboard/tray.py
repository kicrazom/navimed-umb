#!/usr/bin/env python3
"""Mini dashboard: małe okno always-on-top (CPU + GPU0 + GPU1 + żywe modele)
plus ikona w tacce KDE jako wskaźnik obciążenia.

Cienka nakładka na /api/snapshot z ai-dashboard — zero własnego pollingu ROCm.
Uruchom:   ./tray.py            (wymaga biegnącego ai-dashboard na :8666)
Self-test: ./tray.py --selftest
"""

import json
import sys
import urllib.error
import urllib.request

API = "http://127.0.0.1:8666/api/snapshot"
POLL_MS = 2000

# ponytail: PyQt5 bo KDE i tak stoi na Qt i pakiet już jest w systemie —
# żadnego pip install, żadnego własnego czytania /sys/class/drm.
# ponytail: QProgressBar rysuje % na sobie — nie malujemy słupków ręcznie.


def fetch(url=API):
    with urllib.request.urlopen(url, timeout=4) as r:
        return json.load(r)


def gib(n):
    return (n or 0) / 1024**3


def discrete_gpus(snap):
    """Tylko karty dyskretne (R9700), iGPU nas nie interesuje."""
    return [g for g in snap.get("gpus", []) if g.get("gpu_type") == "discrete"]


def models_by_gpu(snap):
    """{idx: [model, ...]} — vLLM wykrywa dashboard, my tylko czytamy."""
    raw = (snap.get("services") or {}).get("gpu_models") or {}
    return {int(k): (v if isinstance(v, list) else [v]) for k, v in raw.items()}


def model_label(snap, idx):
    m = models_by_gpu(snap).get(idx) or []
    return " · ".join(m) if m else "—"


def gpu_line(g):
    """Prawa kolumna wiersza GPU: temperatura, VRAM, pobór mocy."""
    return (
        f"{g.get('temp_c', 0):.0f}°C · "
        f"{gib(g.get('vram_used_b')):.1f}/{gib(g.get('vram_total_b')):.0f} GiB · "
        f"{g.get('power_w', 0):.0f} W"
    )


def badge(snap):
    """Liczba na ikonie w tacce: najwyższe obciążenie GPU dyskretnych."""
    gs = discrete_gpus(snap)
    return max((g.get("use_percent") or 0) for g in gs) if gs else 0


def selftest():
    snap = {
        "hostname": "ai-workstation",
        "cpu_percent": 12.4,
        "cpu_temp": 51.4,
        "gpus": [
            {
                "index": 0,
                "gpu_type": "discrete",
                "use_percent": 97,
                "temp_c": 71.0,
                "vram_used_b": 20 * 1024**3,
                "vram_total_b": 32 * 1024**3,
                "power_w": 240.0,
            },
            {
                "index": 1,
                "gpu_type": "discrete",
                "use_percent": 3,
                "temp_c": 30.0,
                "vram_used_b": 1024**3,
                "vram_total_b": 32 * 1024**3,
                "power_w": 15.0,
            },
            {
                "index": 2,
                "gpu_type": "integrated",
                "use_percent": 0,
                "temp_c": 40.0,
                "vram_used_b": 0,
                "vram_total_b": 2 * 1024**3,
                "power_w": 0.0,
            },
        ],
        "services": {"gpu_models": {"0": ["bge-m3"]}},
    }
    assert badge(snap) == 97, badge(snap)  # max, nie suma
    assert len(discrete_gpus(snap)) == 2  # iGPU odfiltrowane
    assert model_label(snap, 0) == "bge-m3"
    assert model_label(snap, 1) == "—"  # GPU bez modelu
    assert gpu_line(snap["gpus"][0]) == "71°C · 20.0/32 GiB · 240 W"
    assert badge({"gpus": []}) == 0  # brak GPU nie wywala
    assert model_label({"services": {}}, 0) == "—"  # brak services nie wywala
    print("selftest OK")


def main():
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
    from PyQt5.QtWidgets import (
        QAction,
        QApplication,
        QGridLayout,
        QLabel,
        QMenu,
        QProgressBar,
        QSystemTrayIcon,
        QWidget,
    )

    def hue(pct):
        """Zielony (0%) → czerwony (100%)."""
        return QColor.fromHsv(int(120 - 1.2 * max(0, min(100, pct))), 200, 200)

    def icon_for(pct, dead=False):
        pm = QPixmap(64, 64)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#555") if dead else hue(pct))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, 64, 64, 12, 12)
        p.setPen(QColor("white"))
        f = QFont()
        f.setPixelSize(34 if pct < 100 else 26)
        f.setBold(True)
        p.setFont(f)
        p.drawText(pm.rect(), Qt.AlignCenter, "--" if dead else str(pct))
        p.end()
        return QIcon(pm)

    class Row:
        """Jeden wiersz: nazwa | pasek z % | detal (temp/VRAM/W) | model."""

        def __init__(self, grid, r, name, with_model):
            self.bar = QProgressBar()
            self.bar.setRange(0, 100)
            self.bar.setTextVisible(True)
            self.bar.setFormat("%p%")
            self.bar.setFixedHeight(20)
            self.detail = QLabel("—")
            self.detail.setStyleSheet("color:#aaa; font-size:10px;")
            head = QLabel(f"<b>{name}</b>")
            head.setFixedWidth(42)
            grid.addWidget(head, r, 0)
            grid.addWidget(self.bar, r, 1)
            grid.addWidget(self.detail, r, 2)
            self.model = None
            if with_model:
                self.model = QLabel("—")
                self.model.setStyleSheet("color:#6cf; font-size:10px;")
                grid.addWidget(self.model, r + 1, 1, 1, 2)

        def set(self, pct, detail, model=None):
            pct = int(pct or 0)
            self.bar.setValue(pct)
            c = hue(pct)
            self.bar.setStyleSheet(
                "QProgressBar{background:#222;border:1px solid #444;border-radius:4px;"
                "color:white;font-weight:bold;}"
                f"QProgressBar::chunk{{background:{c.name()};border-radius:3px;}}"
            )
            self.detail.setText(detail)
            if self.model is not None and model is not None:
                self.model.setText(f"▸ {model}")

    class Mini(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("AI mini dashboard")
            self.setWindowFlags(
                Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            )
            self.setStyleSheet("background:#111; color:#eee;")
            self.setFixedWidth(340)
            g = QGridLayout(self)
            g.setContentsMargins(10, 8, 10, 8)
            g.setVerticalSpacing(3)
            self.title = QLabel("<b>ai-workstation</b>")
            self.title.setStyleSheet("color:#888; font-size:10px;")
            g.addWidget(self.title, 0, 0, 1, 3)
            self.cpu = Row(g, 1, "CPU", with_model=False)
            self.g0 = Row(g, 2, "GPU0", with_model=True)
            self.g1 = Row(g, 4, "GPU1", with_model=True)
            self._drag = None

        # ponytail: okno bez ramki → przeciąganie trzeba obsłużyć samemu, 3 linijki
        def mousePressEvent(self, e):
            self._drag = e.globalPos() - self.frameGeometry().topLeft()

        def mouseMoveEvent(self, e):
            if self._drag:
                self.move(e.globalPos() - self._drag)

        def update_from(self, snap):
            self.title.setText(
                f"<b>{snap.get('hostname', '?')}</b> · uptime {snap.get('uptime_str', '?')}"
            )
            self.cpu.set(
                snap.get("cpu_percent"),
                f"{(snap.get('cpu_temp') or 0):.0f}°C · "
                f"{snap.get('ram_used_gib', 0):.0f}/{snap.get('ram_total_gib', 0):.0f} GiB RAM",
            )
            gs = {g["index"]: g for g in discrete_gpus(snap)}
            for idx, row in ((0, self.g0), (1, self.g1)):
                g = gs.get(idx)
                if g:
                    row.set(g.get("use_percent"), gpu_line(g), model_label(snap, idx))
                else:
                    row.set(0, "brak karty", "—")

        def show_dead(self, err):
            self.title.setText(f"<b style='color:#f66'>:8666 nieosiągalny</b> — {err}")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    win = Mini()

    tray = QSystemTrayIcon(icon_for(0, dead=True))
    menu = QMenu()
    toggle = QAction("Pokaż/ukryj mini dashboard")

    def show_docked():
        # ponytail: zawsze prawy dolny róg ekranu nad panelem; stała wielkość, bez maksymalizacji
        win.adjustSize()
        win.setFixedSize(win.sizeHint())
        a = app.primaryScreen().availableGeometry()
        win.move(a.right() - win.width() - 8, a.bottom() - win.height() - 8)
        win.show()

    toggle.triggered.connect(lambda: win.hide() if win.isVisible() else show_docked())
    full = QAction("Otwórz pełny dashboard (:8666)")
    full.triggered.connect(
        lambda: __import__("subprocess").Popen(["xdg-open", "http://localhost:8666"])
    )
    quit_act = QAction("Zamknij")
    quit_act.triggered.connect(app.quit)
    for a in (toggle, full):
        menu.addAction(a)
    menu.addSeparator()
    menu.addAction(quit_act)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda r: toggle.trigger() if r == QSystemTrayIcon.Trigger else None
    )
    tray.show()

    def refresh():
        try:
            snap = fetch()
        except (urllib.error.URLError, OSError, ValueError) as e:
            tray.setIcon(icon_for(0, dead=True))
            tray.setToolTip("ai-dashboard nieosiągalny na :8666")
            win.show_dead(e)
            return
        tray.setIcon(icon_for(badge(snap)))
        tray.setToolTip(f"{snap.get('hostname')} · GPU max {badge(snap)}%")
        win.update_from(snap)

    t = QTimer()
    t.timeout.connect(refresh)
    t.start(POLL_MS)
    refresh()  # start schowany w tacce; okno tylko po kliknięciu ikony
    sys.exit(app.exec_())


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
