# Display Controls: shows and hides layouts, by layout folder and by group,
# from the Display Controls window, the web server (e.g. a Stream Deck) and
# socket.io. Saved in the settings, so hidden layouts stay hidden after a
# restart. The layouts play their show animation when turned on and their
# hide animation when turned off (see layout/include/globals.js).

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .Helpers.DisplayControlsHelper import (
    ACTION_HIDE,
    ACTION_SHOW,
    ACTION_TOGGLE,
    KIND_FOLDER,
    KIND_GROUP,
    BuildState,
    LayoutFolders,
    MatchFolder,
    NormalizeAction,
    NormalizeGroupName,
    Resolve,
)
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .Theme import ThemedIcon

SETTINGS_KEY = "display_controls"


class DisplayControlsSignals(QObject):
    changed = Signal()


class DisplayControls:
    """What's shown, kept in the settings and in program_state's display."""

    instance: "DisplayControls" = None
    signals = DisplayControlsSignals()

    def __init__(self, layoutDir="./layout"):
        DisplayControls.instance = self
        self.layoutDir = layoutDir
        self.folders = LayoutFolders(layoutDir)
        saved = SettingsManager.Get(SETTINGS_KEY, {}) or {}
        self.folderValues = {
            str(k): v is not False for k, v in (saved.get("folders") or {}).items()
        }
        self.groupValues = {}
        for k, v in (saved.get("groups") or {}).items():
            name = NormalizeGroupName(k)
            if name:
                self.groupValues[name] = v is not False
        self.Export()

    def State(self):
        return BuildState(self.folders, self.folderValues, self.groupValues)

    def RefreshFolders(self):
        self.folders = LayoutFolders(self.layoutDir)
        self.Export()

    def _Save(self):
        # Only switched folders are saved: new layouts start out shown
        SettingsManager.Set(
            SETTINGS_KEY,
            {
                "folders": {k: v for k, v in self.folderValues.items() if v is False},
                "groups": self.groupValues,
            },
        )
        self.Export()

    def Export(self):
        StateManager.Set("display", self.State())
        DisplayControls.signals.changed.emit()

    def Set(self, kind, name, action):
        """Shows, hides or toggles a folder or group. Returns its name and
        whether it's shown, or an error code."""
        action = NormalizeAction(action)
        if action is None:
            return {"error": "UNKNOWN_ACTION"}
        if kind == KIND_FOLDER:
            folder = MatchFolder(name, self.folders)
            if folder is None:
                return {"error": "NO_FOLDER"}
            shown = Resolve(action, self.folderValues.get(folder, True))
            self.folderValues[folder] = shown
            self._Save()
            return {"kind": kind, "name": folder, "shown": shown}
        if kind == KIND_GROUP:
            group = NormalizeGroupName(name)
            if not group:
                return {"error": "NO_GROUP"}
            # A group that isn't known yet is added: a Stream Deck can hide
            # it before a layout using it has been opened
            shown = Resolve(action, self.groupValues.get(group, True))
            self.groupValues[group] = shown
            self._Save()
            return {"kind": kind, "name": group, "shown": shown}
        return {"error": "UNKNOWN_KIND"}

    def Get(self, kind, name):
        if kind == KIND_FOLDER:
            folder = MatchFolder(name, self.folders)
            if folder is None:
                return {"error": "NO_FOLDER"}
            return {"kind": kind, "name": folder, "shown": self.folderValues.get(folder, True)}
        if kind == KIND_GROUP:
            group = NormalizeGroupName(name)
            if group not in self.groupValues:
                return {"error": "NO_GROUP"}
            return {"kind": kind, "name": group, "shown": self.groupValues[group]}
        return {"error": "UNKNOWN_KIND"}

    def AllShown(self):
        state = self.State()
        return all(state["folders"].values()) and all(state["groups"].values())

    def SetAll(self, action):
        """Shows or hides every folder and group. Toggle hides everything if
        everything is shown, otherwise shows everything."""
        action = NormalizeAction(action)
        if action is None:
            return {"error": "UNKNOWN_ACTION"}
        if action == ACTION_TOGGLE:
            action = ACTION_HIDE if self.AllShown() else ACTION_SHOW
        shown = action == ACTION_SHOW
        for folder in set(self.folders) | set(self.folderValues):
            self.folderValues[folder] = shown
        for group in self.groupValues:
            self.groupValues[group] = shown
        self._Save()
        return {"kind": "all", "shown": shown}

    def AddGroups(self, groups):
        """Adds the groups a layout uses (shown) if they aren't known yet."""
        added = False
        for name in groups or []:
            group = NormalizeGroupName(name)
            if group and group not in self.groupValues:
                self.groupValues[group] = True
                added = True
        if added:
            self._Save()

    def RemoveGroup(self, name):
        group = NormalizeGroupName(name)
        if group in self.groupValues:
            del self.groupValues[group]
            self._Save()


def DisplayURL(path):
    port = SettingsManager.Get("general.webserver_port", 5500)
    return f"http://127.0.0.1:{port}{QUrl.toPercentEncoding(path, b'/').data().decode()}"


class DisplayControlsWidget(QDockWidget):
    def __init__(self, *args):
        super().__init__(*args)
        self.setWindowTitle(QApplication.translate("app", "Display Controls"))
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)

        contents = QWidget()
        contents.setLayout(QVBoxLayout())
        self.setWidget(contents)

        top = QHBoxLayout()
        contents.layout().addLayout(top)
        self.btShowAll = QPushButton(QApplication.translate("app", "Show all"))
        self.btShowAll.clicked.connect(lambda: DisplayControls.instance.SetAll(ACTION_SHOW))
        top.addWidget(self.btShowAll)
        self.btHideAll = QPushButton(QApplication.translate("app", "Hide all"))
        self.btHideAll.clicked.connect(lambda: DisplayControls.instance.SetAll(ACTION_HIDE))
        top.addWidget(self.btHideAll)
        self.btRefresh = QPushButton()
        self.btRefresh.setIcon(ThemedIcon("./assets/icons/undo.svg"))
        self.btRefresh.setToolTip(QApplication.translate("app", "Look for new layout folders"))
        self.btRefresh.clicked.connect(lambda: DisplayControls.instance.RefreshFolders())
        top.addWidget(self.btRefresh)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText(QApplication.translate("app", "Filter"))
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self.ApplyFilter)
        contents.layout().addWidget(self.filter)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.ContextMenu)
        self.tree.itemChanged.connect(self.ItemChanged)
        self.tree.setToolTip(
            QApplication.translate(
                "app",
                "Checked layouts are shown. Right click to copy links for a Stream Deck.",
            )
        )
        contents.layout().addWidget(self.tree)

        self.groupsItem = QTreeWidgetItem([QApplication.translate("app", "Groups")])
        self.groupsItem.setToolTip(
            0,
            QApplication.translate(
                "app", "Layouts with ?display=<group> in their URL are also hidden with their group"
            ),
        )
        self.foldersItem = QTreeWidgetItem([QApplication.translate("app", "Layouts")])
        for item in (self.groupsItem, self.foldersItem):
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tree.addTopLevelItem(item)
            item.setExpanded(True)

        addGroup = QHBoxLayout()
        contents.layout().addLayout(addGroup)
        self.groupName = QLineEdit()
        self.groupName.setPlaceholderText(QApplication.translate("app", "New group"))
        self.groupName.returnPressed.connect(self.AddGroup)
        addGroup.addWidget(self.groupName)
        self.btAddGroup = QPushButton(QApplication.translate("app", "Add group"))
        self.btAddGroup.clicked.connect(self.AddGroup)
        addGroup.addWidget(self.btAddGroup)

        self.updating = False
        DisplayControls.signals.changed.connect(self.Update)
        self.Update()

    def Update(self):
        controls = DisplayControls.instance
        if controls is None:
            return
        state = controls.State()
        self.updating = True
        try:
            for parent, kind, values in (
                (self.groupsItem, KIND_GROUP, state["groups"]),
                (self.foldersItem, KIND_FOLDER, state["folders"]),
            ):
                items = {
                    parent.child(i).text(0): parent.child(i) for i in range(parent.childCount())
                }
                for name in list(items):
                    if name not in values:
                        parent.removeChild(items.pop(name))
                for index, (name, shown) in enumerate(
                    sorted(values.items(), key=lambda v: v[0].lower())
                ):
                    item = items.get(name)
                    if item is None:
                        item = QTreeWidgetItem([name])
                        item.setData(0, Qt.ItemDataRole.UserRole, kind)
                        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                        parent.insertChild(index, item)
                    item.setCheckState(
                        0, Qt.CheckState.Checked if shown else Qt.CheckState.Unchecked
                    )
        finally:
            self.updating = False
        self.ApplyFilter()

    def ApplyFilter(self):
        text = self.filter.text().strip().lower()
        for parent in (self.groupsItem, self.foldersItem):
            for i in range(parent.childCount()):
                item = parent.child(i)
                item.setHidden(bool(text) and text not in item.text(0).lower())

    def ItemChanged(self, item, column):
        if self.updating:
            return
        kind = item.data(0, Qt.ItemDataRole.UserRole)
        if kind not in (KIND_FOLDER, KIND_GROUP):
            return
        shown = item.checkState(0) == Qt.CheckState.Checked
        DisplayControls.instance.Set(kind, item.text(0), ACTION_SHOW if shown else ACTION_HIDE)

    def AddGroup(self):
        name = NormalizeGroupName(self.groupName.text())
        if name:
            DisplayControls.instance.AddGroups([name])
        self.groupName.clear()

    def ContextMenu(self, pos):
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        kind = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if kind in (KIND_FOLDER, KIND_GROUP):
            base = f"/display/{kind}/{item.text(0)}"
        else:
            base = "/display/all"
        for action, label in (
            (ACTION_TOGGLE, QApplication.translate("app", "Copy toggle link")),
            (ACTION_SHOW, QApplication.translate("app", "Copy show link")),
            (ACTION_HIDE, QApplication.translate("app", "Copy hide link")),
        ):
            menu.addAction(
                label,
                lambda url=DisplayURL(f"{base}/{action}"): QApplication.clipboard().setText(url),
            )
        if kind in (KIND_FOLDER, KIND_GROUP):
            menu.addAction(
                QApplication.translate("app", "Copy state link"),
                lambda url=DisplayURL(base): QApplication.clipboard().setText(url),
            )
        if kind == KIND_GROUP:
            menu.addSeparator()
            menu.addAction(
                QApplication.translate("app", "Copy layout URL parameter"),
                lambda: QApplication.clipboard().setText(f"?display={item.text(0)}"),
            )
            menu.addAction(
                QApplication.translate("app", "Remove group"),
                lambda: DisplayControls.instance.RemoveGroup(item.text(0)),
            )
        menu.exec(self.tree.viewport().mapToGlobal(pos))
