from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel

_NEUTRAL_STYLE = (
    "background-color: #1C2A31; color: #546E7A; "
    "font-weight: bold; padding: 8px; border-radius: 4px; "
    "border: 1px solid #2E3F47;"
)
_ACTIVE_STYLE = (
    "background-color: #B71C1C; color: white; "
    "font-weight: bold; padding: 8px; border-radius: 4px; "
    "border: 2px solid #FF5252;"
)

_NEUTRAL_TEXT = "●  Lot status: Normal"
_ACTIVE_TEXT  = "⚠  ALERT — Lot occupancy exceeded 90 %. Please divert incoming vehicles."

_BANNER_HEIGHT = 38


class AlertBanner(QLabel):
    """
    Fixed-height status strip always present in the layout.

    Only text and stylesheet change on threshold transitions — the widget
    is never hidden, so no other widget shifts when the alert fires or clears.
    """

    def __init__(self, parent=None):
        super().__init__(_NEUTRAL_TEXT, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(_BANNER_HEIGHT)
        self.setStyleSheet(_NEUTRAL_STYLE)

    def set_active(self, active: bool):
        if active:
            self.setText(_ACTIVE_TEXT)
            self.setStyleSheet(_ACTIVE_STYLE)
        else:
            self.setText(_NEUTRAL_TEXT)
            self.setStyleSheet(_NEUTRAL_STYLE)
