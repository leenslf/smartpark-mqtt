from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QPushButton

_STATE_COLORS = {
    "FREE":       "#43A047",
    "OCCUPIED":   "#E53935",
    "RESERVED":   "#FB8C00",
    "REQUESTING": "#1E88E5",
}

# Secondary cue: distinct Unicode symbol per state (shape, not hue)
_STATE_SYMBOLS = {
    "FREE":       "●",
    "OCCUPIED":   "■",
    "RESERVED":   "◆",
    "REQUESTING": "◌",
}


class SlotCell(QPushButton):
    reserve_requested = pyqtSignal(str)

    def __init__(self, slot_id: str, parent=None):
        super().__init__(parent)
        self._slot_id = slot_id
        self._state = "FREE"
        self.setFixedSize(90, 70)
        self.clicked.connect(self._on_clicked)
        self._render()

    def update_state(self, state: str):
        self._state = state
        self._render()

    def _render(self):
        color  = _STATE_COLORS.get(self._state, "#9E9E9E")
        symbol = _STATE_SYMBOLS.get(self._state, "?")
        self.setText(f"{self._slot_id}\n{symbol} {self._state}")
        self.setStyleSheet(
            f"background-color: {color}; color: white; font-weight: bold; border-radius: 6px;"
        )
        self.setCursor(Qt.PointingHandCursor if self._state == "FREE" else Qt.ArrowCursor)

    def _on_clicked(self):
        if self._state == "FREE":
            self.reserve_requested.emit(self._slot_id)
