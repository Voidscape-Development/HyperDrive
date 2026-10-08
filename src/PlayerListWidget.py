import traceback

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from src.Helpers.AltTextHelper import (
    TEMPLATE_PLACEHOLDERS,
    add_alt_text_tooltip_to_button,
    default_templates,
    generate_alt_text,
    load_options,
    load_program_state,
    save_options,
)

from .DisplayOptions import DisplayOptionsButton
from .GameAssetManager import GameAssetManager
from .PlayerList import PlayerList
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .TournamentDataManager import TournamentDataManager


class PlayerListWidgetSignals(QObject):
    UpdateData = Signal(object)


class PlayerListWidget(QDockWidget):
    def __init__(self, *args, base="player_list"):
        with StateManager.SaveBlock():
            super().__init__(*args)
            self.SetupUi(base)

    def SetupUi(self, base):
        self.signals = PlayerListWidgetSignals()

        self.playerList = PlayerList(base=base)

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

        self.displayOptions = DisplayOptionsButton("player_list_display_options")
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

        GameAssetManager.instance.signals.onLoad.connect(self.SetDefaultsFromAssets)

    def LoadFromStandingsClicked(self):
        if TournamentDataManager.instance.provider is None:
            return
        self.loadFromStandingsBt.setEnabled(False)
        self.loadFromStandingsBt.setText(QApplication.translate("app", "Loading standings..."))
        TournamentDataManager.instance.GetStandings(
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
        options = load_options()
        try:
            data = load_program_state()
        except:
            logger.error(traceback.format_exc())
            data = {}
        bracketLink = SettingsManager.Get("TOURNAMENT_URL", "") or ""

        messagebox = QDialog(self)
        messagebox.setWindowTitle(QApplication.translate("app", "Descriptive Text for Results"))
        messagebox.resize(1000, 650)
        messagebox.setLayout(QHBoxLayout())

        tabs = QTabWidget()
        messagebox.layout().addWidget(tabs, 2)

        right = QVBoxLayout()
        messagebox.layout().addLayout(right, 3)
        textbox = QPlainTextEdit()
        textbox.setReadOnly(True)
        right.addWidget(textbox)
        copyTextButton = QPushButton(QApplication.translate("app", "Copy text"))
        copyTextButton.clicked.connect(
            lambda: QApplication.clipboard().setText(textbox.toPlainText())
        )
        right.addWidget(copyTextButton)

        def refresh():
            options["mode"] = "template" if tabs.currentIndex() == 1 else "simple"
            textbox.setPlainText(generate_alt_text(data, options, bracket_link=bracketLink))

        def textEdit(key, height=60):
            edit = QPlainTextEdit(options.get(key, ""))
            edit.setFixedHeight(height)

            def changed():
                options[key] = edit.toPlainText()
                refresh()

            edit.textChanged.connect(changed)
            return edit

        # Simple: pick what is shown
        simple = QWidget()
        simple.setLayout(QVBoxLayout())
        checkboxes = [
            ("show_date", QApplication.translate("app", "Date")),
            ("show_game", QApplication.translate("app", "Game")),
            ("show_bracket_link", QApplication.translate("app", "Bracket link")),
            ("show_seed", QApplication.translate("app", "Seed")),
            ("show_country", QApplication.translate("app", "Country")),
            ("show_characters", QApplication.translate("app", "Characters")),
            ("show_variants", QApplication.translate("app", "Character variants")),
            ("show_twitter", QApplication.translate("app", "Twitter")),
            ("show_pronoun", QApplication.translate("app", "Pronouns")),
            ("show_commentators", QApplication.translate("app", "Commentators")),
        ]
        grid = QGridLayout()
        simple.layout().addLayout(grid)
        for i, (key, label) in enumerate(checkboxes):
            checkbox = QCheckBox(label)
            checkbox.setChecked(bool(options.get(key)))
            checkbox.toggled.connect(
                lambda checked, key=key: [options.__setitem__(key, checked), refresh()]
            )
            grid.addWidget(checkbox, i // 2, i % 2)
        simple.layout().addWidget(QLabel(QApplication.translate("app", "Text at the top")))
        simple.layout().addWidget(textEdit("header_text"))
        simple.layout().addWidget(QLabel(QApplication.translate("app", "Text at the bottom")))
        simple.layout().addWidget(textEdit("footer_text"))
        simple.layout().addStretch()
        tabs.addTab(simple, QApplication.translate("app", "Simple"))

        # Template: write the text, with {placeholders}
        template = QWidget()
        template.setLayout(QVBoxLayout())
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(template)
        helpLabel = QLabel(
            QApplication.translate(
                "app",
                "{name} is replaced by the value. A part in [[ ]] is only shown when every value in it is filled in, for example [[ ({twitter})]].",
            )
        )
        helpLabel.setWordWrap(True)
        template.layout().addWidget(helpLabel)
        templateParts = [
            ("header", QApplication.translate("app", "Header")),
            ("entry", QApplication.translate("app", "Each placement")),
            ("player", QApplication.translate("app", "Each player")),
            ("footer", QApplication.translate("app", "Footer")),
        ]
        templateEdits = {}
        for part, label in templateParts:
            title = QLabel(f"<b>{label}</b>")
            template.layout().addWidget(title)
            placeholders = QLabel(" ".join("{" + p + "}" for p in TEMPLATE_PLACEHOLDERS[part]))
            placeholders.setWordWrap(True)
            placeholders.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            template.layout().addWidget(placeholders)
            templateEdits[part] = textEdit(
                f"template_{part}", 50 if part in ("entry", "player") else 90
            )
            template.layout().addWidget(templateEdits[part])

        def resetTemplates():
            for part, text in default_templates().items():
                templateEdits[part].setPlainText(text)

        resetButton = QPushButton(QApplication.translate("app", "Reset templates"))
        resetButton.clicked.connect(resetTemplates)
        template.layout().addWidget(resetButton)
        template.layout().addStretch()
        tabs.addTab(scroll, QApplication.translate("app", "Template"))

        tabs.setCurrentIndex(1 if options.get("mode") == "template" else 0)
        tabs.currentChanged.connect(refresh)
        refresh()

        messagebox.exec()
        save_options(options)

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
