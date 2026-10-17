# The scoreboard's games pop-ups, like the character grid and the color
# picker: GamePopup, one game, opened from a square of the games tracker, and
# GamesSheetPopup, every game of the set, opened from the Games button. Both
# edit the scoreboard's GameReportController and follow its changes in place.
#
# Reporting is where the set ends: picking the winner of the game that takes
# the set offers to report it, and the sheet's button says what it reports.
# What opens a dialog (reporting, clearing, the token check) closes the
# pop-up first: a dialog over a pop-up would close it anyway.

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .CharacterPicker import CharacterCombo
from .GameAssetManager import GameAssetManager
from .GameReport import UNDECIDED
from .GameReportController import (
    STATUS_KIND_ERROR,
    STATUS_KIND_MUTED,
    STATUS_KIND_OK,
    LiveUpdates,
)
from .GamesTracker import GamesTracker
from .Theme import Theme, ThemedIcon

CHARACTER_ICON = QSize(24, 24)
# Widest a team's name is shown on the one-game pop-up's winner buttons
WINNER_NAME_WIDTH = 150


# =====================================================
# HELPERS
# =====================================================
def CharacterIndex(combo, key):
    """Row of a character in the character model, by its key."""
    if not key:
        return 0
    for i in range(1, combo.count()):
        data = combo.itemData(i, Qt.ItemDataRole.UserRole) or {}
        if data.get("en_name") == key:
            return i
    return 0


def StatusColor(kind):
    colors = Theme.Colors()
    dark = Theme.IsDark()
    return {
        STATUS_KIND_OK: QColor("#4cc38a" if dark else "#15803d"),
        STATUS_KIND_ERROR: QColor("#ff8a8a" if dark else "#c62828"),
        STATUS_KIND_MUTED: colors["muted"],
    }.get(kind, colors["text"])


def Muted(text="", scale=0.9):
    label = QLabel(text)
    label.setStyleSheet(f"color: {Theme.Colors()['muted'].name()};")
    font = label.font()
    font.setPointSizeF(font.pointSizeF() * scale)
    label.setFont(font)
    return label


def Bold(text=""):
    label = QLabel(text)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    return label


def Badge(text):
    colors = Theme.Colors()
    label = QLabel(text)
    label.setStyleSheet(
        f"background: {colors['accent'].name()}; color: {colors['onAccent'].name()};"
        "border-radius: 4px; padding: 1px 6px; font-weight: bold;"
    )
    font = label.font()
    font.setPointSizeF(font.pointSizeF() * 0.8)
    label.setFont(font)
    label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return label


def StyleWinnerButton(button, color, checked, radius=None):
    """A winner button: filled with the team's color once picked."""
    colors = Theme.Colors()
    radius = Theme.Radius() if radius is None else radius
    if checked:
        text = GamesTracker.TextColorOn(color)
        button.setStyleSheet(
            f"QPushButton {{ background: {color.name()}; color: {text.name()};"
            f" border: 1px solid {color.name()}; border-radius: {radius}px;"
            " font-weight: bold; padding: 2px 10px; }"
        )
    else:
        button.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {colors['muted'].name()};"
            f" border: 1px solid {colors['border'].name()}; border-radius: {radius}px;"
            " font-weight: bold; padding: 2px 10px; }"
            f"QPushButton:hover {{ color: {colors['text'].name()};"
            f" border-color: {color.name()}; }}"
            f"QPushButton:disabled {{ color: {colors['disabled'].name()}; }}"
        )


def ReportButtonState(controller):
    """(shown, text, enabled, tooltip) of a button reporting the set."""
    if not controller.Reporting():
        return False, "", False, ""
    if controller.Reported():
        return True, QApplication.translate("app", "Reported to start.gg"), False, ""
    winner = controller.SetDecided()
    if controller.report.bestOf <= 0:
        winner = controller.report.SetWinnerTeam()
    if winner is None:
        return True, QApplication.translate("app", "Report when the set ends"), False, ""
    t1, t2 = controller.report.Score()
    text = QApplication.translate("app", "Report {0}–{1} · {2} wins").format(
        t1, t2, controller.TeamName(winner)
    )
    ok, why = controller.CanSend()
    return True, text, ok and not controller.Sending(), why


def PlacePopup(popup, anchor: QRect):
    """Under anchor (a rect on screen), centered on it, or above it when
    there's no room below."""
    popup.adjustSize()
    size = popup.size()
    position = QPoint(anchor.center().x() - size.width() // 2, anchor.bottom() + 4)
    screen = QApplication.screenAt(anchor.center()) or QApplication.primaryScreen()
    if screen is not None:
        area = screen.availableGeometry()
        if position.y() + size.height() > area.bottom():
            position.setY(max(area.top(), anchor.top() - size.height() - 4))
        position.setX(max(area.left(), min(position.x(), area.right() - size.width())))
    popup.move(position)


def ColorDot(color, size=10):
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(QRectF(0, 0, size * 2, size * 2))
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


class IconCharacterCombo(CharacterCombo):
    """A character dropdown showing only the character's icon, with its name
    in the tooltip: several fit where one dropdown with names would."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dimmed = False

    def SetShown(self, dimmed):
        self.dimmed = dimmed
        name = self.currentText()
        self.setToolTip(name or QApplication.translate("app", "No character"))
        self.update()

    def sizeHint(self):
        # The icon in a frame, without the dropdown arrow: the grid opens
        # on a click all the same
        icon = self.iconSize()
        return QSize(icon.width() + 12, max(icon.height() + 10, super().sizeHint().height()))

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        option.currentText = ""
        option.currentIcon = QIcon()
        option.subControls = QStyle.SubControl.SC_ComboBoxFrame
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        icon = self.itemIcon(self.currentIndex())
        if not icon.isNull():
            # The characters a game would take, not picked yet
            if self.dimmed:
                painter.setOpacity(0.45)
            size = self.iconSize()
            rect = QRect(QPoint(0, 0), size)
            rect.moveCenter(self.rect().center())
            icon.paint(painter, rect)


class CharacterCombos(QWidget):
    """A team's characters in a game: a character dropdown, opening the
    grid, per character the team has (each player's characters,
    GameReportController.CharactersPerTeam), side by side or one under the
    other. compact shows
    only their icons. A game without any shows the ones it would take
    (GameReportController.CarriedCharacters) in italics (dimmed, compact),
    if it's the game being played."""

    def __init__(
        self,
        controller,
        team,
        align=Qt.AlignmentFlag.AlignLeft,
        vertical=False,
        compact=False,
        parent=None,
    ):
        super().__init__(parent)
        self.controller = controller
        self.team = team
        self.index = 0
        self.carried = False
        layout = QVBoxLayout(self) if vertical else QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        if not vertical:
            layout.setAlignment(align)
        self.combos = []
        for _ in range(controller.CharactersPerTeam()):
            combo = IconCharacterCombo() if compact else CharacterCombo()
            combo.setModel(GameAssetManager.instance.characterModel)
            combo.setIconSize(CHARACTER_ICON)
            if not compact:
                combo.setSizeAdjustPolicy(
                    QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
                )
                combo.setMinimumContentsLength(9)
            # Keys go to the pop-up (1 / 2 pick the winner) until clicked
            combo.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
            combo.currentIndexChanged.connect(self.Changed)
            layout.addWidget(combo)
            self.combos.append(combo)

    def SetGame(self, index):
        self.index = index
        self.Refresh()

    def Refresh(self):
        report = self.controller.report
        game = report.games[self.index]
        chars = game["characters"].get(self.team) or []
        # Only the game being played takes characters it doesn't have yet
        self.carried = not any(chars) and self.index == report.CurrentGameIndex()
        if self.carried:
            chars, _ = self.controller.CarriedCharacters(self.index, self.team)
        for p, combo in enumerate(self.combos):
            with QSignalBlocker(combo):
                combo.setCurrentIndex(CharacterIndex(combo, chars[p] if p < len(chars) else None))
            if isinstance(combo, IconCharacterCombo):
                combo.SetShown(self.carried)
            else:
                font = combo.font()
                font.setItalic(self.carried)
                combo.setFont(font)

    def Changed(self):
        chars = []
        for combo in self.combos:
            data = combo.currentData() or {}
            chars.append(data.get("en_name") or None)
        self.controller.SetCharacters(self.index, self.team, chars)


class _Popup(QFrame):
    """What both pop-ups share: closing, following the games and the
    status, and running what opens a dialog once closed."""

    def __init__(self, controller, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.controller = controller
        controller.signals.gamesChanged.connect(self.GamesChanged)
        controller.signals.statusChanged.connect(self.Refresh)

    def closeEvent(self, event):
        for signal, slot in [
            (self.controller.signals.gamesChanged, self.GamesChanged),
            (self.controller.signals.statusChanged, self.Refresh),
        ]:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        super().closeEvent(event)

    def GamesChanged(self):
        self.Refresh()

    def Refresh(self):
        pass

    def CloseThen(self, action):
        self.close()
        QTimer.singleShot(0, action)

    def ReportSet(self):
        self.CloseThen(self.controller.ReportSet)


# =====================================================
# ONE GAME
# =====================================================
class GamePopup(_Popup):
    """One game: who won it, with which characters (and on which stage, for
    a game with stages). Arrows (or ← →) go to the other games, 1 and 2
    pick the winner."""

    def __init__(self, controller, index, parent=None):
        super().__init__(controller, parent)
        self.index = index
        # Room for long characters' names, like Mr. Game & Watch
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(6)
        layout.addLayout(header)
        self.previousButton = QToolButton()
        self.previousButton.setIcon(ThemedIcon("assets/icons/arrow_left.svg"))
        self.previousButton.setToolTip(QApplication.translate("app", "Previous game"))
        self.previousButton.setAutoRaise(True)
        self.previousButton.clicked.connect(lambda: self.Go(-1))
        header.addWidget(self.previousButton)
        self.title = Bold()
        header.addWidget(self.title)
        self.nowBadge = Badge(QApplication.translate("app", "NOW"))
        header.addWidget(self.nowBadge)
        header.addStretch()
        self.scoreLabel = Muted(scale=1.0)
        header.addWidget(self.scoreLabel)
        self.nextButton = QToolButton()
        self.nextButton.setIcon(ThemedIcon("assets/icons/arrow_right.svg"))
        self.nextButton.setToolTip(QApplication.translate("app", "Next game"))
        self.nextButton.setAutoRaise(True)
        self.nextButton.clicked.connect(lambda: self.Go(1))
        header.addWidget(self.nextButton)

        layout.addWidget(Muted(QApplication.translate("app", "Who won?")))

        teams = QHBoxLayout()
        teams.setSpacing(8)
        layout.addLayout(teams)
        self.winnerButtons = {}
        self.characters = {}
        for team in (1, 2):
            column = QVBoxLayout()
            column.setSpacing(6)
            button = QPushButton()
            button.setCheckable(True)
            button.setMinimumHeight(48)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda checked, team=team: self.WinnerClicked(team, checked))
            column.addWidget(button)
            self.winnerButtons[team] = button
            if controller.HasCharacters():
                combos = CharacterCombos(controller, team, vertical=True)
                column.addWidget(combos)
                self.characters[team] = combos
            teams.addLayout(column, 1)

        self.carriedLabel = Muted()
        layout.addWidget(self.carriedLabel)

        self.stage = None
        if controller.HasStages():
            row = QHBoxLayout()
            row.addWidget(Muted(QApplication.translate("app", "Stage")))
            self.stage = QComboBox()
            self.stage.setModel(GameAssetManager.instance.stageModelWithBlank)
            self.stage.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
            self.stage.currentIndexChanged.connect(self.StageChanged)
            row.addWidget(self.stage, 1)
            layout.addLayout(row)

        # The set was won: offers to report it
        colors = Theme.Colors()
        self.setOver = QFrame()
        self.setOver.setObjectName("setOver")
        self.setOver.setStyleSheet(
            f"QFrame#setOver {{ background: {colors['accentSoft'].name()};"
            f" border: 1px solid {colors['accent'].name()}; border-radius: {Theme.Radius()}px; }}"
        )
        setOverLayout = QVBoxLayout(self.setOver)
        setOverLayout.setContentsMargins(10, 8, 10, 8)
        setOverLayout.setSpacing(6)
        self.setOverLabel = Bold()
        setOverLayout.addWidget(self.setOverLabel)
        self.setOverButtons = QWidget()
        buttons = QHBoxLayout(self.setOverButtons)
        buttons.setContentsMargins(0, 0, 0, 0)
        self.reportButton = QPushButton(QApplication.translate("app", "Report to start.gg"))
        self.reportButton.setStyleSheet(
            f"QPushButton {{ background: {colors['accent'].name()};"
            f" color: {colors['onAccent'].name()}; border: none;"
            f" border-radius: {Theme.Radius()}px; padding: 5px 12px; font-weight: bold; }}"
            f"QPushButton:disabled {{ background: {colors['raised'].name()};"
            f" color: {colors['disabled'].name()}; }}"
        )
        self.reportButton.clicked.connect(self.ReportSet)
        buttons.addWidget(self.reportButton, 1)
        later = QPushButton(QApplication.translate("app", "Later"))
        later.clicked.connect(self.close)
        buttons.addWidget(later)
        setOverLayout.addWidget(self.setOverButtons)
        self.setOverStatus = Muted()
        self.setOverStatus.setWordWrap(True)
        setOverLayout.addWidget(self.setOverStatus)
        layout.addWidget(self.setOver)

        layout.addWidget(
            Muted(QApplication.translate("app", "1 / 2 pick the winner · ← → other games"))
        )

        self.Refresh()

    def Open(self, anchor: QRect):
        PlacePopup(self, anchor)
        self.show()
        self.setFocus()

    def Go(self, step):
        index = self.index + step
        if 0 <= index < len(self.controller.report.games):
            self.index = index
            self.Refresh()

    def Refresh(self):
        controller = self.controller
        report = controller.report
        if not report.games:
            self.close()
            return
        self.index = max(0, min(self.index, len(report.games) - 1))
        game = report.games[self.index]
        current = self.index == report.CurrentGameIndex()

        self.title.setText(QApplication.translate("app", "Game {0}").format(self.index + 1))
        self.nowBadge.setVisible(current and controller.SetDecided() is None)
        scoreAfter = report.ScoreAfter(self.index)
        self.scoreLabel.setText(f"{scoreAfter[0]}–{scoreAfter[1]}" if scoreAfter else "")
        self.previousButton.setEnabled(self.index > 0)
        self.nextButton.setEnabled(self.index < len(report.games) - 1)

        needed = controller.GameNeeded(self.index)
        for team, button in self.winnerButtons.items():
            checked = game["winner"] == team
            name = controller.TeamName(team)
            # A long name (a doubles team's) ends in … instead of widening the pop-up
            shown = button.fontMetrics().elidedText(
                name, Qt.TextElideMode.ElideRight, WINNER_NAME_WIDTH
            )
            button.setText(
                shown + "\n" + QApplication.translate("app", "Won") if checked else shown
            )
            button.setToolTip(name if shown != name else "")
            button.setChecked(checked)
            button.setEnabled(needed)
            StyleWinnerButton(button, controller.TeamColor(team), checked)

        carried = []
        for team, combos in self.characters.items():
            combos.SetGame(self.index)
            combos.setEnabled(needed)
            if combos.carried:
                chars, source = controller.CarriedCharacters(self.index, team)
                if any(chars):
                    carried.append(source)
        if carried and game["winner"] is UNDECIDED:
            source = carried[0]
            self.carriedLabel.setText(
                QApplication.translate("app", "Characters from the scoreboard")
                if source is None
                else QApplication.translate("app", "Characters from game {0}").format(source + 1)
            )
            self.carriedLabel.show()
        else:
            self.carriedLabel.hide()

        if self.stage is not None:
            index = 0
            if game.get("stage"):
                for s in range(1, self.stage.count()):
                    data = self.stage.itemData(s, Qt.ItemDataRole.UserRole) or {}
                    if data.get("codename") == game["stage"]:
                        index = s
                        break
            with QSignalBlocker(self.stage):
                self.stage.setCurrentIndex(index)
            self.stage.setEnabled(needed)

        winner = controller.SetDecided()
        self.setOver.setVisible(winner is not None)
        if winner is not None:
            t1, t2 = report.Score()
            self.setOverLabel.setText(
                QApplication.translate("app", "{0} wins the set {1}–{2}").format(
                    controller.TeamName(winner), max(t1, t2), min(t1, t2)
                )
            )
            shown, _text, enabled, why = ReportButtonState(controller)
            reported = controller.Reported()
            self.setOverButtons.setVisible(shown and not reported)
            self.reportButton.setEnabled(enabled)
            status, _kind = controller.Status()
            self.setOverStatus.setText(status if shown and (reported or why) else "")
            self.setOverStatus.setVisible(bool(self.setOverStatus.text()))
        self.adjustSize()

    def WinnerClicked(self, team, checked):
        self.controller.SetWinner(self.index, team if checked else UNDECIDED)

    def StageChanged(self):
        data = self.stage.currentData() or {}
        self.controller.SetStage(self.index, data.get("codename"))

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_1, Qt.Key.Key_2) and self.controller.GameNeeded(self.index):
            team = 1 if key == Qt.Key.Key_1 else 2
            game = self.controller.report.games[self.index]
            self.WinnerClicked(team, game["winner"] != team)
        elif key == Qt.Key.Key_Left:
            self.Go(-1)
        elif key == Qt.Key.Key_Right:
            self.Go(1)
        elif (
            key in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and self.setOver.isVisible()
            and self.setOverButtons.isVisible()
            and self.reportButton.isEnabled()
        ):
            self.ReportSet()
        else:
            super().keyPressEvent(event)


# =====================================================
# EVERY GAME
# =====================================================
class GamesSheetPopup(_Popup):
    """Every game of the set, a row each: the teams' characters, who won it
    and the score once it was played. The game being played is highlighted
    and games the set won't need are greyed out. 1 and 2 pick the winner of
    the game being played; Ctrl+Enter reports the set."""

    def __init__(self, controller, parent=None):
        super().__init__(controller, parent)
        self.rows = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        layout.addLayout(header)
        header.addWidget(Bold(QApplication.translate("app", "Games")))
        header.addStretch()
        self.status = Muted()
        header.addWidget(self.status)

        self.gridWidget = QWidget()
        self.grid = QGridLayout(self.gridWidget)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(2)
        layout.addWidget(self.gridWidget)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {Theme.Colors()['border'].name()};")
        layout.addWidget(line)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        layout.addLayout(footer)
        self.moreButton = QToolButton()
        self.moreButton.setIcon(ThemedIcon("assets/icons/menu.svg"))
        self.moreButton.setToolTip(QApplication.translate("app", "More"))
        self.moreButton.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.moreButton.setStyleSheet("QToolButton::menu-indicator { image: none; }")
        self.moreButton.setMenu(QMenu(self.moreButton))
        self.moreButton.menu().aboutToShow.connect(self.FillMenu)
        footer.addWidget(self.moreButton)
        self.hint = Muted()
        footer.addWidget(self.hint, 1)
        colors = Theme.Colors()
        self.reportButton = QPushButton()
        self.reportButton.setStyleSheet(
            f"QPushButton {{ background: {colors['accent'].name()};"
            f" color: {colors['onAccent'].name()}; border: none;"
            f" border-radius: {Theme.Radius()}px; padding: 5px 12px; font-weight: bold; }}"
            f"QPushButton:disabled {{ background: {colors['raised'].name()};"
            f" color: {colors['disabled'].name()}; }}"
        )
        self.reportButton.clicked.connect(self.ReportSet)
        footer.addWidget(self.reportButton)

        self.BuildRows()
        self.Refresh()

    def Open(self, anchor: QRect):
        PlacePopup(self, anchor)
        self.show()
        self.setFocus()

    def BuildRows(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.rows = []
        controller = self.controller
        hasCharacters = controller.HasCharacters()
        colors = Theme.Colors()

        self.teamHeaders = {}
        headers = [
            (0, Muted(QApplication.translate("app", "Game"), 0.8), Qt.AlignmentFlag.AlignLeft),
            (2, Muted(QApplication.translate("app", "Winner"), 0.8), Qt.AlignmentFlag.AlignCenter),
        ]
        if hasCharacters:
            self.teamHeaders = {1: Muted(scale=0.8), 2: Muted(scale=0.8)}
            headers += [
                (1, self.teamHeaders[1], Qt.AlignmentFlag.AlignRight),
                (3, self.teamHeaders[2], Qt.AlignmentFlag.AlignLeft),
            ]
        for column, label, align in headers:
            self.grid.addWidget(label, 0, column, align)

        if not controller.report.games:
            empty = Muted(QApplication.translate("app", "Set the best of to keep track of games"))
            empty.setContentsMargins(6, 8, 6, 8)
            self.grid.addWidget(empty, 1, 0, 1, 5)

        for i in range(len(controller.report.games)):
            r = i + 1
            row = {}
            # Behind the row's widgets, for the game being played
            highlight = QFrame()
            highlight.setObjectName("currentGame")
            highlight.setStyleSheet(
                f"QFrame#currentGame {{ background: {colors['accentSoft'].name()};"
                f" border-radius: {Theme.Radius()}px; }}"
            )
            self.grid.addWidget(highlight, r, 0, 1, 5)
            row["highlight"] = highlight

            label = QLabel(QApplication.translate("app", "G{0}").format(i + 1))
            label.setContentsMargins(6, 4, 0, 4)
            font = label.font()
            font.setBold(True)
            label.setFont(font)
            self.grid.addWidget(label, r, 0)
            row["label"] = label

            row["characters"] = {}
            if hasCharacters:
                for team, column, align in [
                    (1, 1, Qt.AlignmentFlag.AlignRight),
                    (2, 3, Qt.AlignmentFlag.AlignLeft),
                ]:
                    # Several characters a team (players or characters a
                    # player): only their icons, so the pop-up doesn't grow
                    # as wide as four dropdowns
                    combos = CharacterCombos(
                        controller, team, align, compact=controller.CharactersPerTeam() > 1
                    )
                    combos.SetGame(i)
                    self.grid.addWidget(combos, r, column)
                    row["characters"][team] = combos

            winners = QWidget()
            winnersLayout = QHBoxLayout(winners)
            winnersLayout.setContentsMargins(0, 2, 0, 2)
            winnersLayout.setSpacing(0)
            row["winners"] = {}
            for team in (1, 2):
                button = QPushButton()
                button.setCheckable(True)
                button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                button.setMinimumWidth(72)
                button.setIconSize(QSize(8, 8))
                button.clicked.connect(
                    lambda checked, i=i, team=team: self.controller.SetWinner(
                        i, team if checked else UNDECIDED
                    )
                )
                winnersLayout.addWidget(button)
                row["winners"][team] = button
            self.grid.addWidget(winners, r, 2)

            score = Muted(scale=1.0)
            score.setContentsMargins(0, 0, 6, 0)
            score.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.grid.addWidget(score, r, 4)
            row["score"] = score
            self.rows.append(row)

        self.grid.setColumnStretch(1, 1)
        self.grid.setColumnStretch(3, 1)
        self.hint.setText(
            QApplication.translate("app", "Click a character to change it") if hasCharacters else ""
        )

    def GamesChanged(self):
        if len(self.rows) != len(self.controller.report.games):
            self.BuildRows()
            self.Refresh()
            self.adjustSize()
        else:
            self.Refresh()

    def Refresh(self):
        controller = self.controller
        report = controller.report
        current = report.CurrentGameIndex()
        decided = controller.SetDecided() is not None

        for team, label in self.teamHeaders.items():
            label.setText(controller.TeamName(team))

        for i, row in enumerate(self.rows):
            game = report.games[i]
            needed = controller.GameNeeded(i)
            row["highlight"].setVisible(i == current and not decided)
            row["label"].setEnabled(needed)
            for team, combos in row["characters"].items():
                combos.SetGame(i)
                combos.setEnabled(needed)
            for team, button in row["winners"].items():
                checked = game["winner"] == team
                # The columns' headers name the teams, which can be too long
                # for the buttons
                button.setText(QApplication.translate("app", "Won"))
                button.setIcon(QIcon() if checked else ColorDot(controller.TeamColor(team)))
                button.setToolTip(
                    QApplication.translate("app", "Won by {0}").format(controller.TeamName(team))
                )
                button.setChecked(checked)
                button.setEnabled(needed)
                StyleWinnerButton(button, controller.TeamColor(team), checked)
            scoreAfter = report.ScoreAfter(i)
            if scoreAfter:
                row["score"].setText(f"{scoreAfter[0]}–{scoreAfter[1]}")
            elif not needed:
                row["score"].setText(QApplication.translate("app", "Not needed"))
            else:
                row["score"].setText("")

        text, kind = controller.Status()
        self.status.setText(text if controller.Reporting() else "")
        self.status.setStyleSheet(f"color: {StatusColor(kind).name()};")

        shown, text, enabled, why = ReportButtonState(controller)
        self.reportButton.setVisible(shown)
        self.reportButton.setText(text)
        self.reportButton.setEnabled(enabled)
        self.reportButton.setToolTip(why)

    def FillMenu(self):
        controller = self.controller
        menu = self.moreButton.menu()
        menu.clear()
        ok, _why = controller.CanSend()
        busy = controller.Sending()
        if controller.CanRetry():
            menu.addAction(QApplication.translate("app", "Retry"), controller.RetryLast)
        if not LiveUpdates():
            action = menu.addAction(
                QApplication.translate("app", "Send games now"), controller.SendLiveUpdate
            )
            action.setEnabled(ok and not busy)
        menu.addAction(
            QApplication.translate("app", "Check start.gg token"),
            lambda: self.CloseThen(controller.CheckToken),
        )
        menu.addSeparator()
        action = menu.addAction(
            QApplication.translate("app", "Clear games"),
            lambda: self.CloseThen(controller.ClearGames),
        )
        action.setEnabled(controller.report.HasResults())
        action = menu.addAction(
            QApplication.translate("app", "Reset set on start.gg..."),
            lambda: self.CloseThen(controller.ResetSet),
        )
        action.setEnabled(ok and not busy)

    def keyPressEvent(self, event):
        key = event.key()
        report = self.controller.report
        current = report.CurrentGameIndex()
        if (
            key in (Qt.Key.Key_1, Qt.Key.Key_2)
            and current < len(report.games)
            and self.controller.SetDecided() is None
        ):
            self.controller.SetWinner(current, 1 if key == Qt.Key.Key_1 else 2)
        elif (
            key in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
            and self.reportButton.isVisible()
            and self.reportButton.isEnabled()
        ):
            self.ReportSet()
        else:
            super().keyPressEvent(event)
