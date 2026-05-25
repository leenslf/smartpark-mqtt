from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QGridLayout, QWidget

from ui.widgets.slot_cell import SlotCell

_COLS = 5


class SlotGrid(QWidget):
    reserve_requested = pyqtSignal(str)

    def __init__(self, slot_ids: list, parent=None):
        super().__init__(parent)
        self._cells: dict = {}
        layout = QGridLayout(self)
        layout.setSpacing(8)
        for i, slot_id in enumerate(slot_ids):
            cell = SlotCell(slot_id)
            cell.reserve_requested.connect(self.reserve_requested)
            layout.addWidget(cell, i // _COLS, i % _COLS)
            self._cells[slot_id] = cell

    def update_slot(self, slot_id: str, state: str):
        if slot_id in self._cells:
            self._cells[slot_id].update_state(state)
