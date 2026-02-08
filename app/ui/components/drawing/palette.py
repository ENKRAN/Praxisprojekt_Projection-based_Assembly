from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import pyqtSignal as Signal

# --- from https://www.pythonguis.com/widgets/palette/ ---
PALETTES = {
    # bokeh paired 12
    'paired12': [
        '#a6cee3', '#1f78b4', '#b2df8a', '#33a02c', '#fb9a99',
        '#e31a1c', '#fdbf6f', '#ff7f00', '#cab2d6', '#6a3d9a',
        '#ffff99', '#b15928', '#ffffff'
    ],
    # d3 category 10
    'category10': [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
        '#ffffff'
    ],
    # 17 undertones https://lospec.com/palette-list/17undertones
    '17undertones': [
        '#141923', '#414168', '#3a7fa7', '#35e3e3', '#8fd970',
        '#5ebb49', '#458352', '#dcd37b', '#fffee5', '#ffd035',
        '#cc9245', '#a15c3e', '#a42f3b', '#f45b7a', '#c24998',
        '#81588d', '#bcb0c2', '#ffffff'
    ]
}

class _PaletteButton(QtWidgets.QPushButton):
    def __init__(self, color: str):
        super().__init__()
        self.setFixedSize(QtCore.QSize(64, 64))
        self.color = color
        self.setCheckable(True)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: 2px solid #4c566a;
                border-radius: 5px;
                margin: 2px;
            }}
            QPushButton:hover {{
                border: 3px solid #d8dee9;
            }}
            QPushButton:checked {{
                border: 3px solid #eceff4;
            }}
        """)

class _PaletteBase(QtWidgets.QWidget):
    selected = Signal(object)   # emits the color string (or None)

    def __init__(self, allow_none: bool = False, *args, **kwargs):
        """
        :param allow_none: wenn True, darf auch kein Button ausgewählt sein (durch nochmaliges Klicken).
                           Standard: False -> genau ein Button ausgewählt (sofern eine Auswahl erfolgt).
        """
        super().__init__(*args, **kwargs)
        self.allow_none = allow_none

        # gemeinsame ButtonGroup für exklusive Auswahl
        self._group = QtWidgets.QButtonGroup(self)
        # normalerweise exklusiv -> immer nur ein Button checked
        # wenn allow_none True, setzen wir die Gruppe trotzdem auf exklusiv True
        # aber wir implementieren ein Verhalten, das erlauben kann, die Auswahl zu entfernen.
        self._group.setExclusive(True)
        # connect: wenn ein Button angeklickt wird, geben wir die Farbe weiter
        self._group.buttonClicked.connect(self._on_group_button_clicked)

        # Track last checked button to allow "deselect on click" when allow_none True
        self._last_checked = None

    def _on_group_button_clicked(self, btn: QtWidgets.QAbstractButton) -> None:
        """
        Wird aufgerufen, wenn ein Button der Gruppe geklickt wurde.
        Wenn allow_none True und derselbe Button schon vorher ausgewählt war,
        wird er deselektiert (so dass kein Button ausgewählt ist).
        """
        # btn ist das geklickte Button-Objekt; unsere _PaletteButton hat .color
        if self.allow_none:
            # wenn der letzte ausgewählte Button derselbe ist wie der geklickte → ausblenden
            if self._last_checked is btn:
                # temporär exclusivity ausschalten, um Uncheck zu erlauben
                self._group.setExclusive(False)
                btn.setChecked(False)
                self._group.setExclusive(True)
                self._last_checked = None
                self.selected.emit(None)
                return

        # Standardfall: emit die Farbe des nun ausgewählten Buttons
        self._last_checked = btn
        color = getattr(btn, "color", None)
        self.selected.emit(color)

class _PaletteLinearBase(_PaletteBase):
    def __init__(self, colors, allow_none: bool = False, *args, **kwargs):
        super().__init__(allow_none=allow_none, *args, **kwargs)

        if isinstance(colors, str) and colors in PALETTES:
            colors = PALETTES[colors]

        layout = self.layout_class()
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        for c in colors:
            btn = _PaletteButton(c)
            # add to group so Auswahl exklusiv wird
            self._group.addButton(btn)
            layout.addWidget(btn)

        self.setLayout(layout)


class PaletteHorizontal(_PaletteLinearBase):
    layout_class = QtWidgets.QHBoxLayout


class PaletteVertical(_PaletteLinearBase):
    layout_class = QtWidgets.QVBoxLayout


class PaletteGrid(_PaletteBase):
    def __init__(self, colors, n_columns: int = 5, allow_none: bool = False, *args, **kwargs):
        super().__init__(allow_none=allow_none, *args, **kwargs)

        if isinstance(colors, str) and colors in PALETTES:
            colors = PALETTES[colors]

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(5)
        grid.setContentsMargins(5, 5, 5, 5)

        row = col = 0
        for c in colors:
            btn = _PaletteButton(c)
            self._group.addButton(btn)
            grid.addWidget(btn, row, col)

            col += 1
            if col >= n_columns:
                col = 0
                row += 1

        self.setLayout(grid)