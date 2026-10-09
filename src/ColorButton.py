# https://www.pythonguis.com/widgets/qcolorbutton-a-color-selector-tool-for-pyqt/

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .ColorPicker import ColorPicker


class ColorButton(QToolButton):
    """
    Custom Qt Widget to show a chosen color.

    Left-clicking the button shows the color picker, while
    right-clicking resets the color to None (no-color).

    swatchGroups, when set, returns [(title, [Swatch, ...]), ...] shown at
    the top of the picker. Picking one of those also emits swatchPicked
    with the swatch's data.
    """

    colorChanged = Signal(object)
    swatchPicked = Signal(object)

    def __init__(
        self,
        *args,
        color=None,
        disable_right_click=False,
        enable_alpha_selection=False,
        ignore_same_color=True,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self._color = None
        self._default = color
        self.disable_right_click = disable_right_click
        self.enable_alpha_selection = enable_alpha_selection
        self.ignore_same_color = ignore_same_color
        self.swatchGroups = None
        self.clicked.connect(self.onColorPicker)

        # Set the initial/default state.
        self.setColor(self._default)

    def setColor(self, color):
        if self.ignore_same_color:
            if color != self._color:
                self._color = color
                self.colorChanged.emit(color)
        else:
            self._color = color
            self.colorChanged.emit(color)

        if self._color:
            self.setStyleSheet("QToolButton { background-color: %s; }" % self._color)
        else:
            self.setStyleSheet("")

    def color(self):
        return self._color

    def onColorPicker(self):
        """Show the color picker popup below the button."""
        groups = self.swatchGroups() if callable(self.swatchGroups) else None
        # Parented to the window: the button's style sheet (its color) would
        # otherwise apply to the picker's buttons too
        picker = ColorPicker(self._color, groups, self.enable_alpha_selection, self.window())
        picker.picked.connect(self.onPicked)
        picker.Show(self)

    def onPicked(self, color, data):
        self.setColor(color)
        if data is not None:
            self.swatchPicked.emit(data)

    def mousePressEvent(self, e):
        if not self.disable_right_click and e.button() == Qt.RightButton:
            self.setColor(self._default)

        return super().mousePressEvent(e)
