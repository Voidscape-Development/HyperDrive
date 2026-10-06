from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from src.Helpers.TSHAltTextHelper import add_alt_text_tooltip_to_button, generate_top_n_alt_text

from .StateManager import StateManager
from .TSHDisplayOptions import TSHDisplayOptionsButton
from .TSHGameAssetManager import TSHGameAssetManager
from .TSHPlayerList import TSHPlayerList
from .TSHTournamentDataProvider import TSHTournamentDataProvider


class TSHPlayerListWidgetSignals(QObject):
    UpdateData = Signal(object)


class TSHPlayerListWidget(QDockWidget):
    def __init__(self, *args, base="player_list"):
        with StateManager.SaveBlock():
            super().__init__(*args)
            self.SetupUi(base)

    def SetupUi(self, base):
        self.signals = TSHPlayerListWidgetSignals()

        self.playerList = TSHPlayerList(base=base)

        self.setWindowTitle(QApplication.translate("app", "Player List"))
        self.setFloating(True)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.widget = QWidget()
        self.setWidget(self.widget)
        self.widget.setLayout(QVBoxLayout())

        self.setFloating(True)
        self.setWindowFlags(Qt.WindowType.Window)

        topOptions = QWidget()
        topOptions.setLayout(QHBoxLayout())
        topOptions.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Maximum)

        self.widget.layout().addWidget(topOptions)

        row = QWidget()
        row.setLayout(QHBoxLayout())
        topOptions.layout().addWidget(row)

        col = QWidget()
        col.setLayout(QVBoxLayout())
        self.slotNumber = QSpinBox()
        col.layout().addWidget(QLabel(QApplication.translate("app", "Number of slots")))
        col.layout().addWidget(self.slotNumber)
        self.slotNumber.valueChanged.connect(lambda val: self.playerList.SetSlotNumber(val))
        row.layout().addWidget(col)

        col = QWidget()
        col.setLayout(QVBoxLayout())
        self.playerPerTeam = QSpinBox()
        col.layout().addWidget(QLabel(QApplication.translate("app", "Players per slot")))
        col.layout().addWidget(self.playerPerTeam)
        self.playerPerTeam.valueChanged.connect(self.playerList.SetPlayersPerTeam)
        row.layout().addWidget(col)

        col = QWidget()
        col.setLayout(QVBoxLayout())
        self.charNumber = QSpinBox()
        col.layout().addWidget(QLabel(QApplication.translate("app", "Characters per player")))
        col.layout().addWidget(self.charNumber)
        self.charNumber.valueChanged.connect(self.playerList.SetCharactersPerPlayer)
        row.layout().addWidget(col)

        row = QWidget()
        row.setLayout(QHBoxLayout())
        topOptions.layout().addWidget(row)

        showScoresWidget = QWidget()
        showScoresWidget.setLayout(QVBoxLayout())
        self.showScoresCheckbox = QCheckBox()
        self.showScoresCheckbox.setChecked(False)
        showScoresWidget.layout().addWidget(QLabel(QApplication.translate("app", "Show scores")))
        showScoresWidget.layout().addWidget(self.showScoresCheckbox)
        self.showScoresCheckbox.checkStateChanged.connect(self.playerList.SetScoresVisible)
        row.layout().addWidget(showScoresWidget)

        self.loadFromStandingsBt = QPushButton(
            QApplication.translate("app", "Load tournament standings")
        )
        self.loadFromStandingsBt.clicked.connect(self.LoadFromStandingsClicked)
        row.layout().addWidget(self.loadFromStandingsBt)

        self.generateAltTextButton = QPushButton(
            QApplication.translate("app", "Generate Descriptive Text for Results")
        )
        self.generateAltTextButton = add_alt_text_tooltip_to_button(self.generateAltTextButton)
        self.generateAltTextButton.clicked.connect(self.AltTextWindow)
        row.layout().addWidget(self.generateAltTextButton)

        self.displayOptions = TSHDisplayOptionsButton("player_list_display_options")
        self.displayOptions.changed.connect(
            lambda: self.playerList.SetHiddenElements(self.displayOptions.HiddenElements())
        )
        self.playerList.SetHiddenElements(self.displayOptions.HiddenElements())
        row.layout().addWidget(self.displayOptions)

        self.widget.layout().addWidget(self.playerList)

        self.slotWidgets = []

        StateManager.Set("player_list", {})

        self.playerPerTeam.setValue(1)
        self.charNumber.setValue(1)
        self.slotNumber.setValue(8)

        self.signals.UpdateData.connect(self.LoadFromStandings)

        TSHGameAssetManager.instance.signals.onLoad.connect(self.SetDefaultsFromAssets)

    def LoadFromStandingsClicked(self):
        if TSHTournamentDataProvider.instance.provider is None:
            return
        self.loadFromStandingsBt.setEnabled(False)
        self.loadFromStandingsBt.setText(QApplication.translate("app", "Loading standings..."))
        TSHTournamentDataProvider.instance.GetStandings(
            self.slotNumber.value(),
            self.signals.UpdateData,
            on_progress=self.StandingsProgress,
            on_finished=self.StandingsFinished,
        )

    def StandingsProgress(self, done, total):
        self.loadFromStandingsBt.setText(
            QApplication.translate("app", "Loading standings...") + f" {done}/{total}"
        )

    def StandingsFinished(self):
        self.loadFromStandingsBt.setEnabled(True)
        self.loadFromStandingsBt.setText(QApplication.translate("app", "Load tournament standings"))

    def AltTextWindow(self):
        def copy_text():
            textbox.selectAll()
            textbox.copy()

        messagebox = QDialog()
        messagebox.setWindowTitle(QApplication.translate("app", "Descriptive Text for Results"))
        vbox = QVBoxLayout()
        messagebox.setLayout(vbox)
        textbox = QTextEdit()
        text_data = generate_top_n_alt_text().strip("\n")
        textbox.setText(text_data)
        textbox.setReadOnly(True)
        vbox.layout().addWidget(textbox)

        hbox = QHBoxLayout()
        vbox.layout().addLayout(hbox)

        copyTextButton = QPushButton(QApplication.translate("app", "Copy text"))
        copyTextButton.clicked.connect(copy_text)
        hbox.layout().addWidget(copyTextButton)

        messagebox.exec()

    def LoadFromStandings(self, data):
        if not data:
            return
        with StateManager.SaveBlock():
            # Keep the spin boxes in step with what the list is set to
            self.playerPerTeam.setValue(len(data[0].get("players") or []))
            self.slotNumber.setValue(len(data))
            # Provider lookups for missing details (e.g. mains) happen in the
            # background instead of one network request per player here on
            # the UI thread
            self.playerList.LoadFromStandings(data, enrichBlocking=False)

    def SetDefaultsFromAssets(self):
        if StateManager.Get("game.defaults"):
            players, characters = (
                StateManager.Get("game.defaults.players_per_team", 1),
                StateManager.Get("game.defaults.characters_per_player", 1),
            )
        else:
            players, characters = 1, 1

        with StateManager.SaveBlock():
            if self.playerList.playersPerTeam != players:
                self.playerList.SetPlayersPerTeam(players)

            if self.playerList.charactersPerPlayer != characters:
                self.playerList.SetCharactersPerPlayer(characters)
