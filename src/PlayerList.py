from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .DisplayOptions import ApplyHiddenElements
from .PlayerDrag import PlayerDragBoard
from .PlayerListSlotWidget import PlayerListSlotWidget
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .TournamentDataManager import TournamentDataManager


class PlayerListWidgetSignals(QObject):
    UpdateData = Signal(object)
    DataChanged = Signal()


class PlayerList(QWidget):
    def __init__(self, *args, base="player_list", startCollapsed=False):
        with StateManager.SaveBlock():
            super().__init__(*args)
            self.SetupUi(base, startCollapsed)

    # =====================================================
    # SETUP
    # =====================================================
    def SetupUi(self, base, startCollapsed=False):
        self.signals = PlayerListWidgetSignals()

        self.base = base

        self.slotWidgets: list[PlayerListSlotWidget] = []
        # Players are dragged by their grip within and between the slots
        self.dragBoard = PlayerDragBoard(
            lambda: [s.playerWidgets for s in self.slotWidgets],
            lambda a, b: a.SwapWith(b, emitIdChanged=False),
            self,
        )

        self.playersPerTeam = 0
        self.charactersPerPlayer = 0
        # Object names of the player fields hidden by the display options;
        # slots apply these to the player widgets they create
        self.hiddenElements = set()
        self.scoresVisible = False

        # Which slots are collapsed and which players have their details
        # folded, by place, kept in the settings for next time. Also the
        # list's "start slots collapsed" and "compact players" choices
        self.foldsKey = "player_list_folds." + base.replace(".", "_")
        folds = SettingsManager.Get(self.foldsKey, None)
        self.folds = folds if isinstance(folds, dict) else {}
        for key in ("slots", "players"):
            if not isinstance(self.folds.get(key), dict):
                self.folds[key] = {}
        if not isinstance(self.folds.get("start_collapsed"), bool):
            self.folds["start_collapsed"] = startCollapsed

        self.setLayout(QVBoxLayout())

        self.childDataChangedLock = False

        # Slots still to be resized by SetSizesGradually, one per timeout.
        # Not 0: the gap lets the window handle input and paint in between
        self.resizeQueue = []
        self.resizeTimer = QTimer(self)
        self.resizeTimer.setInterval(15)
        self.resizeTimer.timeout.connect(self.ResizeNextSlot)

        scrollArea = QScrollArea()
        scrollArea.setFrameShadow(QFrame.Shadow.Plain)
        scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        scrollArea.setWidgetResizable(True)

        self.widgetArea = QWidget()
        self.widgetArea.setLayout(QVBoxLayout())
        self.widgetArea.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        scrollArea.setWidget(self.widgetArea)

        self.layout().addWidget(scrollArea)

        StateManager.Set(base, {})

    def ChildDataChangedEmit(self):
        if not self.childDataChangedLock:
            self.signals.DataChanged.emit()

    # =====================================================
    # STANDINGS
    # =====================================================
    def LoadFromStandingsClicked(self):
        TournamentDataManager.instance.GetStandings(
            self.slotNumber.value(), self.signals.UpdateData
        )

    def LoadFromStandings(self, data, enrichBlocking=True):
        data = data or []

        with StateManager.SaveBlock():
            if len(data) > 0:
                self.SetSlotNumber(len(data))
                playerNumber = len(data[0].get("players") or [])
                self.SetPlayersPerTeam(playerNumber)

                self.childDataChangedLock = True
                try:
                    for i, slot in enumerate(self.slotWidgets):
                        # SetSlotNumber can leave a different amount of slots
                        # than there is data (e.g. a slot failed to be removed)
                        if i >= len(data):
                            break
                        slot.SetTeamData(data[i], enrichBlocking=enrichBlocking)
                finally:
                    self.childDataChangedLock = False

    # =====================================================
    # SIZE
    # =====================================================
    def SetSlotNumber(self, number):
        with StateManager.SaveBlock():
            self.DoSetSlotNumber(number)

    def DoSetSlotNumber(self, number):
        while len(self.slotWidgets) < number:
            s = PlayerListSlotWidget(len(self.slotWidgets) + 1, self, base=self.base)
            self.slotWidgets.append(s)
            self.widgetArea.layout().addWidget(s)
            s.SetPlayersPerTeam(self.playersPerTeam)
            s.SetCharacterNumber(self.charactersPerPlayer)
            s.scoreWidget.setVisible(self.scoresVisible)
            s.SetCollapsed(self.SlotCollapsed(s.index))
            s.signals.dataChanged.connect(self.ChildDataChangedEmit)
            s.signals.collapsedChanged.connect(
                lambda collapsed, s=s: self.SaveSlotCollapsed(s.index, collapsed)
            )

            # s.SetCharactersPerPlayer(self.charNumber.value())

            # index = len(self.team1playerWidgets)

            # p.btMoveUp.clicked.connect(lambda x, index=index, p=p: p.SwapWith(
            #     self.team1playerWidgets[index-1 if index > 0 else 0]))
            # p.btMoveDown.clicked.connect(lambda x, index=index, p=p: p.SwapWith(
            #     self.team1playerWidgets[index+1 if index < len(self.team1playerWidgets) - 1 else index]))

        while len(self.slotWidgets) > number:
            s = self.slotWidgets[-1]
            s.setParent(None)
            self.slotWidgets.remove(s)
            StateManager.Unset(f"{self.base}.slot.{s.index}")

        self.signals.DataChanged.emit()

    def SetPlayersPerTeam(self, number):
        # logger.info("PlayerList#SetPlayersPerTeam")
        self.playersPerTeam = number
        with StateManager.SaveBlock():
            self.childDataChangedLock = True
            try:
                for s in self.slotWidgets:
                    s.SetPlayersPerTeam(number)
            finally:
                self.childDataChangedLock = False
            self.signals.DataChanged.emit()

    def SetCharactersPerPlayer(self, value):
        # logger.info("PlayerList#SetCharactersPerPlayer")
        self.charactersPerPlayer = value
        with StateManager.SaveBlock():
            self.childDataChangedLock = True
            try:
                for s in self.slotWidgets:
                    s.SetCharacterNumber(value)
            finally:
                self.childDataChangedLock = False
            self.signals.DataChanged.emit()

    def SetSizesGradually(self, players, characters):
        """Sets the players per slot and characters per player one slot at a
        time, a slot per pass of the event loop. Used when a game is loaded:
        making every slot's player cards at once froze the window."""
        self.playersPerTeam = players
        self.charactersPerPlayer = characters
        self.resizeQueue = list(self.slotWidgets)
        self.resizeTimer.start()

    def ResizeNextSlot(self):
        # Slots read the sizes when resized, so a size changed directly in
        # the meantime (which resizes every slot) is kept
        while self.resizeQueue:
            s = self.resizeQueue.pop(0)
            if s not in self.slotWidgets:
                continue
            with StateManager.SaveBlock():
                self.childDataChangedLock = True
                try:
                    s.SetPlayersPerTeam(self.playersPerTeam)
                    s.SetCharacterNumber(self.charactersPerPlayer)
                finally:
                    self.childDataChangedLock = False
            return
        self.resizeTimer.stop()
        self.signals.DataChanged.emit()

    # =====================================================
    # DISPLAY
    # =====================================================
    def SetHiddenElements(self, hidden):
        self.hiddenElements = set(hidden)
        for s in self.slotWidgets:
            for pw in s.playerWidgets:
                ApplyHiddenElements(pw, self.hiddenElements)

    def SetScoresVisible(self, value):
        self.scoresVisible = value != Qt.CheckState.Unchecked
        for s in self.slotWidgets:
            s.scoreWidget.setVisible(self.scoresVisible)

    # =====================================================
    # FOLDING
    # =====================================================
    def SaveFolds(self):
        SettingsManager.Set(self.foldsKey, self.folds)

    def StartCollapsed(self):
        return self.folds["start_collapsed"]

    def SetStartCollapsed(self, value):
        self.folds["start_collapsed"] = bool(value)
        self.SaveFolds()

    def CompactPlayers(self):
        return self.folds.get("compact_players", False) is True

    def SlotCollapsed(self, slot):
        """How a slot starts: collapsed with "start slots collapsed", else as
        it was left."""
        if self.StartCollapsed():
            return True
        return self.folds["slots"].get(str(slot), False) is True

    def SaveSlotCollapsed(self, slot, collapsed):
        self.folds["slots"][str(slot)] = bool(collapsed)
        self.SaveFolds()

    def SetAllCollapsed(self, collapsed):
        for s in self.slotWidgets:
            s.SetCollapsed(collapsed)
            self.folds["slots"][str(s.index)] = bool(collapsed)
        self.SaveFolds()

    def PlayerDetailsShown(self, slot, player):
        shown = self.folds["players"].get(f"{slot}-{player}")
        if isinstance(shown, bool):
            return shown
        return not self.CompactPlayers()

    def SavePlayerDetailsShown(self, slot, player, shown):
        self.folds["players"][f"{slot}-{player}"] = bool(shown)
        self.SaveFolds()

    def SetCompactPlayers(self, compact):
        """Folds every player's details away, or shows them all."""
        self.folds["compact_players"] = bool(compact)
        for s in self.slotWidgets:
            for pw in s.playerWidgets:
                pw.SetDetailsShown(not compact)
                self.folds["players"][f"{s.index}-{pw.index}"] = not compact
        self.SaveFolds()
