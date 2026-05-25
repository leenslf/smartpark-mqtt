from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget,
)

_COUNTER_STYLE = (
    "background-color: {color}; color: white; font-weight: bold; "
    "border-radius: 6px; padding: 8px 16px;"
)
_BAR_STYLE = (
    "QProgressBar {{"
    "  border: 1px solid #37474F; border-radius: 4px; background: #1C2A31; "
    "  height: 14px; text-align: center; color: transparent;"
    "}}"
    "QProgressBar::chunk {{ background-color: {color}; border-radius: 4px; }}"
)

_FREE_COLOR     = "#43A047"
_OCCUPIED_COLOR = "#E53935"
_RESERVED_COLOR = "#FB8C00"


def _make_counter(text: str, color: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(_COUNTER_STYLE.format(color=color))
    return lbl


class SummaryPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setSpacing(6)
        outer.setContentsMargins(0, 0, 0, 0)

        # --- row 1: metric counters ---
        counters = QHBoxLayout()
        counters.setSpacing(12)
        self._free     = _make_counter("FREE: 0",     _FREE_COLOR)
        self._occupied = _make_counter("OCCUPIED: 0", _OCCUPIED_COLOR)
        self._reserved = _make_counter("RESERVED: 0", _RESERVED_COLOR)
        for w in (self._free, self._occupied, self._reserved):
            counters.addWidget(w)
        outer.addLayout(counters)

        # --- row 2: occupancy progress bar ---
        bar_row = QHBoxLayout()
        bar_row.setSpacing(8)

        lbl_caption = QLabel("Occupancy:")
        lbl_caption.setStyleSheet("color: #90A4AE; font-weight: bold;")
        lbl_caption.setFixedWidth(80)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFixedHeight(14)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(_BAR_STYLE.format(color=_FREE_COLOR))

        self._pct = QLabel("0 %")
        self._pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._pct.setStyleSheet("color: #90A4AE; font-weight: bold;")
        self._pct.setFixedWidth(46)

        bar_row.addWidget(lbl_caption)
        bar_row.addWidget(self._bar, stretch=1)
        bar_row.addWidget(self._pct)
        outer.addLayout(bar_row)

    def update(self, free: int, occupied: int, reserved: int):
        self._free.setText(f"FREE: {free}")
        self._occupied.setText(f"OCCUPIED: {occupied}")
        self._reserved.setText(f"RESERVED: {reserved}")

        total = free + occupied + reserved
        pct   = int(occupied / total * 100) if total > 0 else 0

        self._bar.setValue(pct)
        self._pct.setText(f"{pct} %")

        # Bar colour tracks severity: green → orange → red
        if pct >= 90:
            bar_color = _OCCUPIED_COLOR
        elif pct >= 60:
            bar_color = _RESERVED_COLOR
        else:
            bar_color = _FREE_COLOR
        self._bar.setStyleSheet(_BAR_STYLE.format(color=bar_color))
