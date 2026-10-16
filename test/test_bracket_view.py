# Checks the bracket view's zoom: a bracket set while the view is hidden
# (the dock behind another tab at startup) is fitted once the view is
# shown at its real size, the fit follows the view's size, and stops
# when the bracket is zoomed.
# Run from the repository root: python test/test_bracket_view.py
import os
import sys
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

localeHelper = types.ModuleType("src.Helpers.LocaleHelper")


class LocaleHelper:
    matchNames = {}


localeHelper.LocaleHelper = LocaleHelper
helpers = types.ModuleType("src.Helpers")
helpers.__path__ = [os.path.abspath("src/Helpers")]
sys.modules["src.Helpers"] = helpers
sys.modules["src.Helpers.LocaleHelper"] = localeHelper

from qtpy.QtCore import QPoint, QPointF, Qt
from qtpy.QtGui import QWheelEvent
from qtpy.QtWidgets import QApplication, QTabWidget, QWidget

app = QApplication.instance() or QApplication(sys.argv)

from src.BracketModel import TYPE_DOUBLE_ELIMINATION, GenerateBracket
from src.BracketView import BracketView


def Settle():
    for _ in range(5):
        app.processEvents()


def Zoom(view):
    return view.transform().m11()


def AllSetsShown(view):
    shown = view.mapToScene(view.viewport().rect()).boundingRect()
    return shown.contains(view.scene().itemsBoundingRect())


def HiddenView():
    tabs = QTabWidget()
    tabs.resize(1200, 800)
    tabs.addTab(QWidget(), "Other")
    view = BracketView()
    tabs.addTab(view, "Bracket")
    tabs.show()
    view.SetBracket(GenerateBracket(TYPE_DOUBLE_ELIMINATION, list(range(1, 33))))
    Settle()
    return tabs, view


def TestFitWhenShown():
    tabs, view = HiddenView()
    tabs.setCurrentIndex(1)
    Settle()
    fitted = Zoom(view)
    assert AllSetsShown(view)
    # The same as fitting it by hand at that size
    view.FitInView()
    assert abs(Zoom(view) - fitted) < 1e-6, (fitted, Zoom(view))


def TestFitFollowsSize():
    tabs, view = HiddenView()
    tabs.setCurrentIndex(1)
    Settle()
    before = Zoom(view)
    tabs.resize(1600, 1000)
    Settle()
    assert Zoom(view) > before
    assert AllSetsShown(view)


def TestZoomStopsFit():
    tabs, view = HiddenView()
    tabs.setCurrentIndex(1)
    Settle()
    view.wheelEvent(
        QWheelEvent(
            QPointF(10, 10),
            QPointF(10, 10),
            QPoint(),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
    )
    zoomed = Zoom(view)
    tabs.resize(1600, 1000)
    Settle()
    assert not view.autoFit
    assert abs(Zoom(view) - zoomed) < 1e-6


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
