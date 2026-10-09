# The Stream Queue widget: a tab per stream with the sets it will show next.
# The queues come from start.gg and can be edited here (sets moved, hidden,
# added from the event or typed in by hand, streams added by hand). Each
# stream can be linked to a scoreboard, which then gets the stream's next set
# once its set is over (see the "after a set" option).
import time
import traceback

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .Scheduler import Scheduler
from .ScoreboardManager import ScoreboardManager
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .StreamQueue import *
from .Theme import ThemedIcon
from .TournamentDataManager import TournamentDataManager
from .Workers import Worker

JOB_NAME = "stream_queue"
DEFAULT_INTERVAL_SECS = 15
MIN_INTERVAL_SECS = 5


def SetTitle(data):
    """ "Team A vs Team B" for a queue entry's set."""
    teams = (data or {}).get("team") or {}
    names = []
    for key in ("1", "2"):
        team = teams.get(key) or {}
        name = team.get("teamName")
        if not name:
            players = [
                p.get("mergedName") or p.get("name") or ""
                for p in (team.get("player") or {}).values()
            ]
            name = " / ".join(p for p in players if p)
        names.append(name or QApplication.translate("app", "TBD"))
    return QApplication.translate("app", "{0} vs {1}").format(*names)


def StateText(data):
    state = (data or {}).get("state")
    if state == 2:
        return QApplication.translate("app", "In progress")
    if state == 6:
        return QApplication.translate("app", "Called")
    if state == STATE_COMPLETED:
        return QApplication.translate("app", "Finished")
    return ""


class AddStartggSetDialog(QDialog):
    """Picks a set of the event to add to a queue."""

    def __init__(self, parent, threadPool):
        super().__init__(parent)
        self.setWindowTitle(QApplication.translate("app", "Add a set"))
        self.resize(700, 500)
        self.setLayout(QVBoxLayout())

        self.filter = QLineEdit()
        self.filter.setPlaceholderText(QApplication.translate("app", "Filter"))
        self.layout().addWidget(self.filter)

        self.model = QStandardItemModel(0, 4)
        self.model.setHorizontalHeaderLabels(
            [
                QApplication.translate("app", "Phase"),
                QApplication.translate("app", "Match"),
                QApplication.translate("app", "Players"),
                QApplication.translate("app", "Stream"),
            ]
        )
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.filter.textChanged.connect(self.proxy.setFilterFixedString)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.accept)
        self.layout().addWidget(self.table)

        self.status = QLabel(QApplication.translate("app", "Loading sets..."))
        self.layout().addWidget(self.status)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.layout().addWidget(buttons)

        provider = TournamentDataManager.instance.provider
        if provider is None:
            self.status.setText(QApplication.translate("app", "No tournament loaded"))
            return
        worker = Worker(provider.GetMatches, **{"getFinished": False})
        worker.signals.result.connect(self.SetsLoaded)
        threadPool.start(worker)

    def SetsLoaded(self, sets):
        try:
            for s in sets or []:
                if not s or s.get("id") is None:
                    continue
                players = QApplication.translate("app", "{0} vs {1}").format(
                    s.get("p1_name") or QApplication.translate("app", "TBD"),
                    s.get("p2_name") or QApplication.translate("app", "TBD"),
                )
                row = [
                    QStandardItem(s.get("tournament_phase") or ""),
                    QStandardItem(s.get("round_name") or ""),
                    QStandardItem(players),
                    QStandardItem(s.get("stream") or ""),
                ]
                row[0].setData(s.get("id"), Qt.ItemDataRole.UserRole)
                self.model.appendRow(row)
            self.status.setText(
                QApplication.translate("app", "{0} sets").format(self.model.rowCount())
            )
        except RuntimeError:
            # Closed before the sets came in
            pass

    def SelectedSetId(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        return self.proxy.index(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)


class StreamQueueTab(QWidget):
    def __init__(self, owner: "StreamQueueWidget", name):
        super().__init__()
        self.owner = owner
        self.name = name
        self.setLayout(QVBoxLayout())

        top = QHBoxLayout()
        self.layout().addLayout(top)
        top.addWidget(QLabel(QApplication.translate("app", "Scoreboard")))
        self.scoreboardSelect = QComboBox()
        self.scoreboardSelect.setToolTip(
            QApplication.translate(
                "app",
                'The scoreboard showing this stream\'s sets. It gets the next set of the queue once its set is over, depending on the "after a set" option.',
            )
        )
        self.scoreboardSelect.currentIndexChanged.connect(self.ScoreboardChanged)
        top.addWidget(self.scoreboardSelect)
        self.btLoadNext = QPushButton(QApplication.translate("app", "Load next set"))
        self.btLoadNext.setIcon(ThemedIcon("./assets/icons/list.svg"))
        self.btLoadNext.clicked.connect(lambda: self.owner.LoadNext(self.name))
        top.addWidget(self.btLoadNext)
        top.addStretch()

        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(
            [
                "#",
                QApplication.translate("app", "Match"),
                QApplication.translate("app", "Players"),
                QApplication.translate("app", "Station"),
                QApplication.translate("app", "Status"),
            ]
        )
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.model().rowsMoved.connect(self.RowsMoved)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tree.itemDoubleClicked.connect(lambda item, _c: self.LoadSelected())
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.ContextMenu)
        self.layout().addWidget(self.tree)

        buttons = QHBoxLayout()
        self.layout().addLayout(buttons)
        self.btLoad = QPushButton(QApplication.translate("app", "Load into scoreboard"))
        self.btLoad.clicked.connect(self.LoadSelected)
        buttons.addWidget(self.btLoad)
        btUp = QPushButton("▲")
        btUp.setToolTip(QApplication.translate("app", "Move up"))
        btUp.clicked.connect(lambda: self.MoveSelected(-1))
        buttons.addWidget(btUp)
        btDown = QPushButton("▼")
        btDown.setToolTip(QApplication.translate("app", "Move down"))
        btDown.clicked.connect(lambda: self.MoveSelected(1))
        buttons.addWidget(btDown)
        btRemove = QPushButton(QApplication.translate("app", "Remove"))
        btRemove.setToolTip(
            QApplication.translate(
                "app", "Takes the set out of this queue. start.gg's queue isn't changed."
            )
        )
        btRemove.clicked.connect(self.RemoveSelected)
        buttons.addWidget(btRemove)
        buttons.addStretch()
        btAdd = QPushButton(QApplication.translate("app", "Add set..."))
        btAdd.clicked.connect(self.AddStartggSet)
        buttons.addWidget(btAdd)
        btCustom = QPushButton(QApplication.translate("app", "Add custom..."))
        btCustom.setToolTip(
            QApplication.translate("app", "A set that isn't on start.gg, e.g. an exhibition")
        )
        btCustom.clicked.connect(self.AddCustomSet)
        buttons.addWidget(btCustom)
        btReset = QPushButton(QApplication.translate("app", "Reset"))
        btReset.setToolTip(
            QApplication.translate("app", "Back to start.gg's queue, undoing the changes made here")
        )
        btReset.clicked.connect(self.Reset)
        buttons.addWidget(btReset)

        self.updating = False

    def Config(self):
        return self.owner.model.GetStream(self.name)

    def SelectedKey(self):
        item = self.tree.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def Refresh(self):
        config = self.Config()
        if config is None:
            return
        self.updating = True
        try:
            # Scoreboards
            self.scoreboardSelect.blockSignals(True)
            self.scoreboardSelect.clear()
            self.scoreboardSelect.addItem(QApplication.translate("app", "None"), None)
            for n in ScoreboardManager.instance.GetScoreboardNumbers():
                self.scoreboardSelect.addItem(ScoreboardManager.instance.GetTabName(n), n)
            self.scoreboardSelect.setCurrentIndex(
                max(0, self.scoreboardSelect.findData(config.scoreboard))
            )
            self.scoreboardSelect.blockSignals(False)
            self.btLoadNext.setEnabled(config.scoreboard is not None)

            selected = self.SelectedKey()
            onStream = self.owner.OnStream().get(self.name)
            self.tree.clear()
            for i, entry in enumerate(self.owner.model.Queue(self.name)):
                data = entry.get("set") or {}
                item = QTreeWidgetItem(
                    [
                        str(i + 1),
                        " - ".join(x for x in (data.get("phase"), data.get("match")) if x),
                        SetTitle(data),
                        str(data.get("station"))
                        if data.get("station") not in (None, -1, "")
                        else "",
                        StateText(data),
                    ]
                )
                item.setData(0, Qt.ItemDataRole.UserRole, entry["key"])
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)
                if entry["source"] != SOURCE_STARTGG:
                    item.setToolTip(
                        2, QApplication.translate("app", "Added here, not in start.gg's queue")
                    )
                    font = item.font(2)
                    font.setItalic(True)
                    item.setFont(2, font)
                if onStream is not None and entry["key"] == SetKey(onStream):
                    item.setText(4, QApplication.translate("app", "On stream"))
                    font = item.font(4)
                    font.setBold(True)
                    for c in range(5):
                        item.setFont(c, font)
                self.tree.addTopLevelItem(item)
                if entry["key"] == selected:
                    self.tree.setCurrentItem(item)
            for c in (0, 1, 3, 4):
                self.tree.resizeColumnToContents(c)
        finally:
            self.updating = False

    def ScoreboardChanged(self):
        config = self.Config()
        if config is None or self.updating:
            return
        number = self.scoreboardSelect.currentData()
        # A scoreboard shows one stream
        for other in self.owner.model.streams:
            if other is not config and number is not None and str(other.scoreboard) == str(number):
                other.scoreboard = None
        config.scoreboard = number
        self.owner.Changed()

    def RowsMoved(self, *args):
        if self.updating:
            return
        keys = [
            self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
            for i in range(self.tree.topLevelItemCount())
        ]
        config = self.Config()
        if config is not None:
            config.order = keys
            QTimer.singleShot(0, self.owner.Changed)

    def MoveSelected(self, offset):
        key = self.SelectedKey()
        if key:
            self.owner.model.Move(self.name, key, offset)
            self.owner.Changed()

    def RemoveSelected(self):
        key = self.SelectedKey()
        if key:
            self.owner.model.Remove(self.name, key)
            self.owner.Changed()

    def Reset(self):
        if (
            QMessageBox.question(
                self,
                QApplication.translate("app", "Reset queue"),
                QApplication.translate("app", "Undo the changes made to {0}'s queue?").format(
                    self.name
                ),
            )
            == QMessageBox.StandardButton.Yes
        ):
            self.owner.model.ResetOrder(self.name)
            self.owner.Changed()

    def LoadSelected(self):
        key = self.SelectedKey()
        entry = next((e for e in self.owner.model.Queue(self.name) if e["key"] == key), None)
        if entry is None:
            return
        config = self.Config()
        number = config.scoreboard if config else None
        if number is None:
            numbers = ScoreboardManager.instance.GetScoreboardNumbers()
            if len(numbers) == 1:
                number = numbers[0]
            else:
                names = [ScoreboardManager.instance.GetTabName(n) for n in numbers]
                name, ok = QInputDialog.getItem(
                    self,
                    QApplication.translate("app", "Load into scoreboard"),
                    QApplication.translate("app", "Scoreboard"),
                    names,
                    0,
                    False,
                )
                if not ok:
                    return
                number = numbers[names.index(name)]
        self.owner.LoadEntry(entry, number)

    def AddStartggSet(self):
        dialog = AddStartggSetDialog(self, self.owner.threadPool)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            setId = dialog.SelectedSetId()
            if setId is not None:
                self.owner.model.AddStartggSet(self.name, setId)
                self.owner.Changed()
                # Get its players and round
                self.owner.Refresh()

    def AddCustomSet(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(QApplication.translate("app", "Add custom set"))
        form = QFormLayout()
        dialog.setLayout(form)
        team1 = QLineEdit()
        team2 = QLineEdit()
        match = QLineEdit()
        form.addRow(QApplication.translate("app", "Player/Team 1"), team1)
        form.addRow(QApplication.translate("app", "Player/Team 2"), team2)
        form.addRow(QApplication.translate("app", "Match"), match)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted and (
            team1.text().strip() or team2.text().strip()
        ):
            self.owner.model.AddCustomSet(
                self.name, team1.text().strip(), team2.text().strip(), match=match.text().strip()
            )
            self.owner.Changed()

    def ContextMenu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        self.tree.setCurrentItem(item)
        menu = QMenu(self)
        menu.addAction(QApplication.translate("app", "Load into scoreboard"), self.LoadSelected)
        menu.addAction(
            QApplication.translate("app", "Move to the top"),
            lambda: [
                self.owner.model.MoveTo(self.name, self.SelectedKey(), 0),
                self.owner.Changed(),
            ],
        )
        menu.addAction(QApplication.translate("app", "Remove"), self.RemoveSelected)
        menu.exec(self.tree.viewport().mapToGlobal(pos))


class StreamQueueWidget(QDockWidget):
    instance: "StreamQueueWidget" = None

    def __init__(self, *args):
        super().__init__(*args)
        StreamQueueWidget.instance = self
        self.setWindowTitle(QApplication.translate("app", "Stream Queue"))
        self.setFloating(True)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)

        self.threadPool = QThreadPool()
        self.model = StreamQueueModel.FromDict(SettingsManager.Get("stream_queue", {}))
        self.tabs: dict[str, StreamQueueTab] = {}

        contents = QWidget()
        contents.setLayout(QVBoxLayout())
        self.setWidget(contents)

        top = QHBoxLayout()
        contents.layout().addLayout(top)
        self.btRefresh = QPushButton()
        self.btRefresh.setIcon(ThemedIcon("./assets/icons/undo.svg"))
        self.btRefresh.setToolTip(QApplication.translate("app", "Update the queues now"))
        self.btRefresh.clicked.connect(self.Refresh)
        top.addWidget(self.btRefresh)
        self.autoRefresh = QCheckBox(QApplication.translate("app", "Update every"))
        self.autoRefresh.setChecked(SettingsManager.Get("stream_queue_options.auto_refresh", True))
        self.autoRefresh.toggled.connect(self.AutoRefreshChanged)
        top.addWidget(self.autoRefresh)
        self.interval = QSpinBox()
        self.interval.setRange(MIN_INTERVAL_SECS, 600)
        self.interval.setSuffix(QApplication.translate("app", " s"))
        self.interval.setValue(
            SettingsManager.Get("stream_queue_options.interval", DEFAULT_INTERVAL_SECS)
        )
        self.interval.valueChanged.connect(self.IntervalChanged)
        top.addWidget(self.interval)
        self.statusLabel = QLabel()
        top.addWidget(self.statusLabel)
        top.addStretch()

        top.addWidget(QLabel(QApplication.translate("app", "After a set")))
        self.afterSet = QComboBox()
        self.afterSet.addItem(QApplication.translate("app", "Do nothing"), AFTER_SET_NOTHING)
        self.afterSet.addItem(
            QApplication.translate("app", "Ask to load the next set"), AFTER_SET_ASK
        )
        self.afterSet.addItem(
            QApplication.translate("app", "Load the next set"), AFTER_SET_LOAD_NEXT
        )
        self.afterSet.setToolTip(
            QApplication.translate(
                "app",
                "What happens when the set on a stream's scoreboard is over (reported, or finished on start.gg)",
            )
        )
        self.afterSet.setCurrentIndex(max(0, self.afterSet.findData(self.model.afterSet)))
        self.afterSet.currentIndexChanged.connect(self.AfterSetChanged)
        top.addWidget(self.afterSet)

        self.btOptions = QToolButton()
        self.btOptions.setIcon(ThemedIcon("./assets/icons/settings.svg"))
        self.btOptions.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self)
        self.autoAddAction = menu.addAction(
            QApplication.translate("app", "Add start.gg's streams automatically")
        )
        self.autoAddAction.setCheckable(True)
        self.autoAddAction.setChecked(self.model.autoAddStreams)
        self.autoAddAction.toggled.connect(self.AutoAddChanged)
        menu.addAction(QApplication.translate("app", "Add stream..."), self.AddStream)
        self.btOptions.setMenu(menu)
        top.addWidget(self.btOptions)

        self.tabWidget = QTabWidget()
        self.tabWidget.setTabsClosable(True)
        self.tabWidget.setMovable(True)
        self.tabWidget.tabCloseRequested.connect(self.CloseTab)
        self.tabWidget.tabBar().tabMoved.connect(self.TabMoved)
        btAdd = QToolButton()
        btAdd.setText("+")
        btAdd.setToolTip(QApplication.translate("app", "Add a stream by hand"))
        btAdd.clicked.connect(self.AddStream)
        self.tabWidget.setCornerWidget(btAdd, Qt.Corner.TopRightCorner)
        contents.layout().addWidget(self.tabWidget)

        self.emptyLabel = QLabel(
            QApplication.translate(
                "app",
                "No streams yet. Streams in start.gg's stream queue show up here, or add one with +.",
            )
        )
        self.emptyLabel.setWordWrap(True)
        self.emptyLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        contents.layout().addWidget(self.emptyLabel)

        Scheduler.instance.Register(
            JOB_NAME, self.RunRefresh, self.interval.value() * 1000, MIN_INTERVAL_SECS * 1000
        )
        Scheduler.instance.signals.tick.connect(self.UpdateStatus)
        Scheduler.instance.signals.job_state_changed.connect(
            lambda name: self.UpdateStatus() if name == JOB_NAME else None
        )

        TournamentDataManager.instance.signals.tournament_changed.connect(self.TournamentChanged)
        ScoreboardManager.instance.signals.ScoreboardAdded.connect(self.ScoreboardsChanged)
        ScoreboardManager.instance.signals.ScoreboardRemoved.connect(self.ScoreboardRemoved)
        ScoreboardManager.instance.signals.TabNamesChanged.connect(self.UpdateTabs)
        for n in ScoreboardManager.instance.GetScoreboardNumbers():
            self.ScoreboardsChanged(n)

        self.UpdateTabs()
        self.Export()

    # Updating from start.gg

    def TournamentChanged(self):
        provider = TournamentDataManager.instance.provider
        if provider is not None and self.autoRefresh.isChecked():
            Scheduler.instance.Start(JOB_NAME, run_now=True)
        else:
            Scheduler.instance.Stop(JOB_NAME)
        self.UpdateStatus()

    def AutoRefreshChanged(self, checked):
        SettingsManager.Set("stream_queue_options.auto_refresh", checked)
        self.TournamentChanged()

    def IntervalChanged(self, value):
        SettingsManager.Set("stream_queue_options.interval", value)
        Scheduler.instance.SetInterval(JOB_NAME, value * 1000)

    def Refresh(self):
        if TournamentDataManager.instance.provider is None:
            return
        Scheduler.instance.TriggerNow(JOB_NAME)

    def RunRefresh(self, done):
        provider = TournamentDataManager.instance.provider
        if provider is None:
            done()
            return
        addedIds = self.model.AddedSetIds()

        def Fetch(progress_callback=None, cancel_event=None):
            result = {"queues": provider.GetStreamQueue(), "added": {}}
            for setId in addedIds:
                try:
                    data = provider.GetFutureMatch(setId)
                    if data:
                        result["added"][str(setId)] = data
                except Exception:
                    logger.error(traceback.format_exc())
            return result

        worker = Worker(Fetch)
        worker.signals.result.connect(
            lambda result, provider=provider: self.Fetched(result, provider)
        )
        worker.signals.finished.connect(done)
        self.threadPool.start(worker)

    def Fetched(self, result, provider):
        # Another tournament was loaded meanwhile
        if provider is not TournamentDataManager.instance.provider:
            return
        try:
            self.model.SetProviderQueues((result or {}).get("queues") or {})
            self.model.SetAddedSetData((result or {}).get("added") or {})
        except Exception:
            logger.error(traceback.format_exc())
        self.Changed(save=False)

    def UpdateStatus(self):
        parts = []
        if self.model.lastUpdated:
            ago = int(time.time() - self.model.lastUpdated)
            parts.append(QApplication.translate("app", "Updated {0}s ago").format(ago))
        if JOB_NAME in Scheduler.instance.jobs and Scheduler.instance.IsRunning(JOB_NAME):
            parts.append(QApplication.translate("app", "Updating..."))
        self.statusLabel.setText(" · ".join(parts))

    # Tabs

    def UpdateTabs(self):
        names = [s.name for s in self.model.streams]
        # Remove tabs of streams that are gone
        for name in list(self.tabs):
            if name not in names:
                tab = self.tabs.pop(name)
                index = self.tabWidget.indexOf(tab)
                if index >= 0:
                    self.tabWidget.removeTab(index)
                tab.deleteLater()
        for i, name in enumerate(names):
            tab = self.tabs.get(name)
            if tab is None:
                tab = StreamQueueTab(self, name)
                self.tabs[name] = tab
                self.tabWidget.insertTab(i, tab, name)
            elif self.tabWidget.indexOf(tab) != i:
                self.tabWidget.tabBar().blockSignals(True)
                self.tabWidget.tabBar().moveTab(self.tabWidget.indexOf(tab), i)
                self.tabWidget.tabBar().blockSignals(False)
            config = self.model.GetStream(name)
            label = name
            if config.scoreboard is not None:
                label = f"{name} → {ScoreboardManager.instance.GetTabName(config.scoreboard)}"
            self.tabWidget.setTabText(self.tabWidget.indexOf(tab), label)
            tab.Refresh()
        self.tabWidget.setVisible(bool(names))
        self.emptyLabel.setVisible(not names)
        self.UpdateStatus()

    def TabMoved(self, frm, to):
        order = [self.tabWidget.widget(i).name for i in range(self.tabWidget.count())]
        self.model.streams.sort(key=lambda s: order.index(s.name) if s.name in order else 999)
        self.Changed()

    def CloseTab(self, index):
        tab = self.tabWidget.widget(index)
        if tab is None:
            return
        if (
            QMessageBox.question(
                self,
                QApplication.translate("app", "Remove stream"),
                QApplication.translate(
                    "app", "Remove {0}? start.gg's streams can be added back with +."
                ).format(tab.name),
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.model.RemoveStream(tab.name)
        self.Changed()

    def AddStream(self):
        name, ok = QInputDialog.getText(
            self,
            QApplication.translate("app", "Add stream"),
            QApplication.translate(
                "app",
                "Stream name (e.g. the Twitch channel). A stream in start.gg's stream queue gets its queue.",
            ),
        )
        if ok and name.strip():
            self.model.AddStream(name.strip())
            self.Changed()
            self.tabWidget.setCurrentWidget(self.tabs.get(self.model.GetStream(name.strip()).name))

    def AutoAddChanged(self, checked):
        self.model.autoAddStreams = checked
        if checked:
            self.model.SetProviderQueues(self.model.providerQueues)
        self.Changed()

    def AfterSetChanged(self):
        self.model.afterSet = self.afterSet.currentData()
        self.Changed()

    # Scoreboards

    def ScoreboardsChanged(self, number=None):
        if number is not None:
            scoreboard = ScoreboardManager.instance.GetScoreboard(number)
            if scoreboard is not None and hasattr(scoreboard.signals, "SetFinished"):
                scoreboard.signals.SetFinished.connect(
                    lambda setId, number=number: self.ScoreboardSetFinished(number, setId)
                )
            if scoreboard is not None:
                scoreboard.signals.NewSetLoaded.connect(lambda: QTimer.singleShot(0, self.Export))
        self.UpdateTabs()

    def ScoreboardRemoved(self, number):
        for config in self.model.streams:
            if config.scoreboard is not None and str(config.scoreboard) == str(number):
                config.scoreboard = None
        self.Changed()

    def OnStream(self):
        """Set id on each linked stream's scoreboard."""
        result = {}
        for config in self.model.streams:
            if config.scoreboard is not None:
                setId = StateManager.Get(f"score.{config.scoreboard}.set_id")
                if setId is not None:
                    result[config.name] = setId
        return result

    def LoadEntry(self, entry, number):
        scoreboard = ScoreboardManager.instance.GetScoreboard(number)
        if scoreboard is None:
            return
        data = entry.get("set") or {}
        if data.get("id") is not None and entry.get("source") != SOURCE_CUSTOM:
            scoreboard.signals.NewSetSelected.emit({"id": data.get("id"), "auto_update": "set"})
        else:
            # Typed in by hand: only the names
            scoreboard.StopAutoUpdate(clear_variables=True)
            scoreboard.CommandClearAll()
            scoreboard.ClearScore()
            for t, key in enumerate(("1", "2")):
                team = (data.get("team") or {}).get(key) or {}
                for p, player in enumerate((team.get("player") or {}).values()):
                    scoreboard.signals.ChangeSetData.emit(
                        {
                            "team": t + 1,
                            "player": p + 1,
                            "data": {"gamerTag": player.get("name") or ""},
                        }
                    )
            if data.get("match"):
                scoreboard.signals.ChangeSetData.emit({"round_name": data.get("match")})
        QTimer.singleShot(0, self.Export)

    def LoadNext(self, name, ask=False):
        config = self.model.GetStream(name)
        if config is None or config.scoreboard is None:
            return
        current = StateManager.Get(f"score.{config.scoreboard}.set_id")
        entry = self.model.NextEntry(name, current)
        if entry is None:
            return
        if ask:
            answer = QMessageBox.question(
                self,
                QApplication.translate("app", "Next set"),
                QApplication.translate("app", "Load {0} into {1}?").format(
                    SetTitle(entry.get("set")),
                    ScoreboardManager.instance.GetTabName(config.scoreboard),
                ),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.LoadEntry(entry, config.scoreboard)

    def ScoreboardSetFinished(self, number, setId):
        """The set on a scoreboard is over (reported here or on start.gg)."""
        self.model.SetFinished(setId)
        config = self.model.StreamOfScoreboard(number)
        self.Changed()
        if config is None:
            return
        if self.model.afterSet == AFTER_SET_LOAD_NEXT:
            self.LoadNext(config.name)
        elif self.model.afterSet == AFTER_SET_ASK:
            # Not from inside the signal that reported it
            QTimer.singleShot(0, lambda: self.LoadNext(config.name, ask=True))

    # Saving and exporting

    def Changed(self, save=True):
        if save:
            SettingsManager.Set("stream_queue", self.model.ToDict())
        self.UpdateTabs()
        self.Export()

    def Export(self):
        try:
            data = self.model.Export(self.OnStream())
            data["currentStream"] = SettingsManager.Get("twitch_username")
            StateManager.Set("stream_queue", data)
        except Exception:
            logger.error(traceback.format_exc())
