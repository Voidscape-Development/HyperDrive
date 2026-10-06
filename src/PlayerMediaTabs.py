"""The Player Database window's tabs for the files of players, sponsors and
teams in user_data: avatars, custom data, sponsor logos and team logos."""

import os
import shutil
from collections.abc import Callable

import orjson
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .Helpers.DynamicExport import DynamicExport
from .Helpers.MediaHelper import (
    AVATAR_DIR,
    CUSTOM_PLAYER_DIR,
    SPONSOR_LOGO_DIR,
    TEAM_LOGO_DIR,
    MediaHelper,
)
from .Helpers.SponsorHelper import SponsorHelper
from .PlayerDB import PlayerDB
from .Theme import ThemedIcon

PersonRole = Qt.ItemDataRole.UserRole + 1
PathRole = Qt.ItemDataRole.UserRole + 2


def OpenFolder(folder: str):
    os.makedirs(folder, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(folder)))


def ShowError(parent, message: str):
    QMessageBox.warning(parent, QApplication.translate("app", "Player media"), message)


def ConfirmOverwrite(parent, path: str) -> bool:
    if not os.path.exists(path):
        return True
    answer = QMessageBox.question(
        parent,
        QApplication.translate("app", "Replace file"),
        QApplication.translate("app", "{0} already exists. Replace it?").format(
            os.path.basename(path)
        ),
    )
    return answer == QMessageBox.StandardButton.Yes


class FileDropFilter(QObject):
    """Accepts local files dropped on a widget, and passes their paths to callback"""

    def __init__(self, widget: QWidget, callback: Callable[[list[str]], None], imagesOnly=False):
        super().__init__(widget)
        self.callback = callback
        self.imagesOnly = imagesOnly
        widget.setAcceptDrops(True)
        widget.installEventFilter(self)

    def Paths(self, event) -> list[str]:
        mime = event.mimeData()
        if not mime.hasUrls():
            return []
        paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
        paths = [p for p in paths if os.path.isfile(p)]
        if self.imagesOnly:
            paths = [p for p in paths if MediaHelper.IsImage(p)]
        return paths

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            if self.Paths(event):
                event.acceptProposedAction()
                return True
        elif event.type() == QEvent.Type.Drop:
            paths = self.Paths(event)
            if paths:
                event.acceptProposedAction()
                self.callback(paths)
                return True
        return False


class ImagePreview(QLabel):
    def __init__(self, size=160, emptyText=""):
        super().__init__()
        self.previewSize = size
        self.emptyText = emptyText
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.SetImage(None)

    def SetImage(self, path: str | None):
        pixmap = QPixmap(path) if path and os.path.isfile(path) else QPixmap()
        if pixmap.isNull():
            self.setPixmap(QPixmap())
            self.setText(self.emptyText)
            return
        self.setText("")
        self.setPixmap(
            pixmap.scaled(
                self.previewSize - 8,
                self.previewSize - 8,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


class PlayerMediaTab(QWidget):
    """A person's avatar, custom data and sponsor logos, by sponsor and tag.
    Works for anyone, saved in the player database or not."""

    TEXT_EXTENSIONS = DynamicExport.TEXT_EXTENSIONS + (".json",)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.editingFile = None
        self.dirty = False
        self.loadingText = False

        layout = QHBoxLayout()
        self.setLayout(layout)
        splitter = QSplitter()
        layout.addWidget(splitter)

        # People
        listWidget = QWidget()
        listWidget.setLayout(QVBoxLayout())
        listWidget.layout().setContentsMargins(0, 0, 0, 0)
        splitter.addWidget(listWidget)

        self.search = QLineEdit()
        self.search.setPlaceholderText(QApplication.translate("app", "Search players..."))
        self.search.setClearButtonEnabled(True)
        listWidget.layout().addWidget(self.search)

        self.onlyWithFiles = QCheckBox(QApplication.translate("app", "Only people with files"))
        listWidget.layout().addWidget(self.onlyWithFiles)

        self.model = QStandardItemModel()
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.onlyWithFiles.toggled.connect(lambda _: self.RefreshList())

        self.list = QListView()
        self.list.setModel(self.proxy)
        self.list.setIconSize(QSize(24, 24))
        self.list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.list.selectionModel().currentChanged.connect(self.PersonSelected)
        listWidget.layout().addWidget(self.list)

        listHint = QLabel(
            QApplication.translate(
                "app",
                "Players in the database and anyone with files. Type a sponsor and tag on the "
                "right for someone else.",
            )
        )
        listHint.setWordWrap(True)
        listWidget.layout().addWidget(listHint)

        # The person's media
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        splitter.addWidget(scroll)
        right = QWidget()
        right.setLayout(QVBoxLayout())
        scroll.setWidget(right)

        form = QFormLayout()
        right.layout().addLayout(form)
        self.sponsor = QLineEdit()
        form.addRow(QApplication.translate("app", "Sponsor"), self.sponsor)
        self.tag = QLineEdit()
        form.addRow(QApplication.translate("app", "Tag"), self.tag)

        # Reloads once typing stops
        self.reloadTimer = QTimer(self)
        self.reloadTimer.setSingleShot(True)
        self.reloadTimer.setInterval(300)
        self.reloadTimer.timeout.connect(self.LoadPerson)
        self.sponsor.textEdited.connect(lambda _: self.reloadTimer.start())
        self.tag.textEdited.connect(lambda _: self.reloadTimer.start())

        # Avatar
        avatarBox = QGroupBox(QApplication.translate("app", "Avatar"))
        avatarBox.setLayout(QHBoxLayout())
        right.layout().addWidget(avatarBox)
        self.avatarPreview = ImagePreview(
            emptyText=QApplication.translate("app", "No avatar.\nDrop an image here.")
        )
        FileDropFilter(self.avatarPreview, lambda paths: self.SetAvatar(paths[0]), imagesOnly=True)
        avatarBox.layout().addWidget(self.avatarPreview)
        avatarSide = QVBoxLayout()
        avatarBox.layout().addLayout(avatarSide)
        self.avatarLabel = QLabel()
        self.avatarLabel.setWordWrap(True)
        self.avatarLabel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        avatarSide.addWidget(self.avatarLabel)
        avatarButtons = QHBoxLayout()
        avatarSide.addLayout(avatarButtons)
        self.avatarChooseBt = QPushButton(QApplication.translate("app", "Choose image..."))
        self.avatarChooseBt.clicked.connect(self.ChooseAvatar)
        avatarButtons.addWidget(self.avatarChooseBt)
        self.avatarRemoveBt = QPushButton(QApplication.translate("app", "Remove"))
        self.avatarRemoveBt.setIcon(ThemedIcon("./assets/icons/cancel.svg"))
        self.avatarRemoveBt.clicked.connect(self.RemoveAvatar)
        avatarButtons.addWidget(self.avatarRemoveBt)
        avatarSide.addStretch()

        # Sponsor logos
        sponsorBox = QGroupBox(QApplication.translate("app", "Sponsor logos"))
        sponsorBox.setLayout(QVBoxLayout())
        right.layout().addWidget(sponsorBox)
        self.sponsorLogos = QHBoxLayout()
        sponsorBox.layout().addLayout(self.sponsorLogos)
        self.sponsorLabel = QLabel()
        self.sponsorLabel.setWordWrap(True)
        sponsorBox.layout().addWidget(self.sponsorLabel)
        self.sponsorAddBt = QPushButton()
        self.sponsorAddBt.clicked.connect(self.ChooseSponsorLogo)
        sponsorBox.layout().addWidget(self.sponsorAddBt, 0, Qt.AlignmentFlag.AlignLeft)

        # Custom data
        customBox = QGroupBox(QApplication.translate("app", "Custom data"))
        customBox.setLayout(QVBoxLayout())
        right.layout().addWidget(customBox)
        self.customLabel = QLabel()
        self.customLabel.setWordWrap(True)
        customBox.layout().addWidget(self.customLabel)

        self.files = QListWidget()
        self.files.setIconSize(QSize(32, 32))
        self.files.setMinimumHeight(90)
        self.files.setMaximumHeight(150)
        self.files.currentItemChanged.connect(self.FileSelected)
        FileDropFilter(self.files.viewport(), self.AddFiles)
        customBox.layout().addWidget(self.files)

        fileButtons = QHBoxLayout()
        customBox.layout().addLayout(fileButtons)
        self.newTextBt = QPushButton(QApplication.translate("app", "New text..."))
        self.newTextBt.clicked.connect(self.NewTextFile)
        fileButtons.addWidget(self.newTextBt)
        self.addFilesBt = QPushButton(QApplication.translate("app", "Add files..."))
        self.addFilesBt.clicked.connect(self.ChooseFiles)
        fileButtons.addWidget(self.addFilesBt)
        self.renameBt = QPushButton(QApplication.translate("app", "Rename..."))
        self.renameBt.clicked.connect(self.RenameFile)
        fileButtons.addWidget(self.renameBt)
        self.deleteBt = QPushButton(QApplication.translate("app", "Delete"))
        self.deleteBt.setIcon(ThemedIcon("./assets/icons/cancel.svg"))
        self.deleteBt.clicked.connect(self.DeleteFile)
        fileButtons.addWidget(self.deleteBt)
        self.openFolderBt = QPushButton(QApplication.translate("app", "Open folder"))
        self.openFolderBt.clicked.connect(lambda: OpenFolder(self.CustomFolder()))
        fileButtons.addWidget(self.openFolderBt)

        # The selected file: its text to edit, or a preview
        self.editorStack = QStackedWidget()
        customBox.layout().addWidget(self.editorStack)

        self.editorEmpty = QLabel(
            QApplication.translate(
                "app",
                "Each file reaches the layouts by its name, e.g. bio.txt as custom.bio. "
                "Drop files on the list to add them.",
            )
        )
        self.editorEmpty.setWordWrap(True)
        self.editorStack.addWidget(self.editorEmpty)

        textPage = QWidget()
        textPage.setLayout(QVBoxLayout())
        textPage.layout().setContentsMargins(0, 0, 0, 0)
        self.textEdit = QPlainTextEdit()
        self.textEdit.setMinimumHeight(140)
        self.textEdit.textChanged.connect(self.TextChanged)
        textPage.layout().addWidget(self.textEdit)
        textButtons = QHBoxLayout()
        textPage.layout().addLayout(textButtons)
        self.textStatus = QLabel()
        self.textStatus.setWordWrap(True)
        textButtons.addWidget(self.textStatus, 1)
        self.textSaveBt = QPushButton(QApplication.translate("app", "Save"))
        self.textSaveBt.setIcon(ThemedIcon("./assets/icons/save.svg"))
        self.textSaveBt.clicked.connect(self.SaveText)
        textButtons.addWidget(self.textSaveBt)
        self.editorStack.addWidget(textPage)

        self.filePreview = ImagePreview(size=220)
        self.editorStack.addWidget(self.filePreview)

        self.fileInfo = QLabel()
        self.fileInfo.setWordWrap(True)
        self.editorStack.addWidget(self.fileInfo)

        right.layout().addStretch()

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([320, 680])

        self.textSaveShortcut = QShortcut(QKeySequence.StandardKey.Save, self.textEdit)
        self.textSaveShortcut.activated.connect(self.SaveText)

        PlayerDB.signals.db_updated.connect(self.DBUpdated)

        self.LoadPerson()

    # People

    def showEvent(self, event):
        self.RefreshList()
        self.LoadPerson()
        super().showEvent(event)

    def DBUpdated(self):
        if self.isVisible():
            self.RefreshList()

    def RefreshList(self):
        """Players in the database, and anyone with an avatar or a custom
        data folder"""
        people = {}

        def Add(team, name, inDB=False):
            key = (team.upper(), name.upper())
            if key not in people:
                people[key] = (team, name, inDB)

        for player in list(PlayerDB.database.values()):
            if player.get("gamerTag"):
                Add(player.get("prefix") or "", player["gamerTag"], True)

        # Folders and avatars whose names are a known player's are theirs
        known = set()
        for team, name, _ in people.values():
            known.add(DynamicExport.FolderKey(name))
            known.add(DynamicExport.FolderKey(f"{team} {name}" if team else name))
        if os.path.isdir(CUSTOM_PLAYER_DIR):
            for entry in os.scandir(CUSTOM_PLAYER_DIR):
                if entry.is_dir() and DynamicExport.FolderKey(entry.name) not in known:
                    Add("", entry.name)
        for stem in MediaHelper.ListPngs(AVATAR_DIR):
            if DynamicExport.FolderKey(stem) not in known:
                Add("", stem)

        self.model.clear()
        for team, name, inDB in people.values():
            avatar = MediaHelper.FindAvatar(team, name)
            hasAvatar = avatar is not None
            hasFolder = DynamicExport.FindCustomFolder(name, team) is not None
            if self.onlyWithFiles.isChecked() and not (hasAvatar or hasFolder):
                continue
            item = QStandardItem(f"{team} {name}" if team else name)
            item.setData((team, name), PersonRole)
            if hasAvatar:
                item.setIcon(QIcon(avatar))
            notes = []
            if not inDB:
                notes.append(QApplication.translate("app", "Not in the player database"))
            if hasFolder:
                notes.append(QApplication.translate("app", "Has custom data"))
            item.setToolTip("\n".join(notes))
            self.model.appendRow(item)
        self.proxy.sort(0)

    def PersonSelected(self, current, _previous=None):
        person = current.data(PersonRole) if current.isValid() else None
        if person is None:
            return
        self.SetPerson(*person)

    def SetPerson(self, team: str, name: str):
        """Shows the media of this person, e.g. from a player's Media button"""
        if not self.ConfirmDiscard():
            return
        self.sponsor.setText(team or "")
        self.tag.setText(name or "")
        self.LoadPerson()

    def Person(self) -> tuple[str, str]:
        return self.sponsor.text().strip(), self.tag.text().strip()

    def LoadPerson(self):
        if not self.ConfirmDiscard():
            return
        team, name = self.Person()
        hasName = bool(name)

        # Avatar
        avatar = MediaHelper.FindAvatar(team, name) if hasName else None
        self.avatarPreview.SetImage(avatar)
        if not hasName:
            avatarText = QApplication.translate("app", "Type a tag, or pick someone on the left.")
        elif avatar:
            avatarText = QApplication.translate("app", "From {0}").format(
                os.path.relpath(avatar, "./user_data")
            )
        else:
            avatarText = QApplication.translate("app", "Will be saved as {0}").format(
                os.path.relpath(MediaHelper.NewAvatarPath(team, name), "./user_data")
            )
        if hasName and team:
            avatarText += "\n" + QApplication.translate(
                "app",
                "Looked for with the sponsor first ({0}), then the tag alone ({1}), "
                "so it works with any sponsor.",
            ).format(
                os.path.basename(MediaHelper.AvatarPath(team, name)),
                os.path.basename(MediaHelper.AvatarPath("", name)),
            )
        self.avatarLabel.setText(avatarText)
        self.avatarChooseBt.setEnabled(hasName)
        self.avatarRemoveBt.setEnabled(avatar is not None)
        self.avatarPreview.setAcceptDrops(hasName)

        # Sponsor logos
        while self.sponsorLogos.count():
            widget = self.sponsorLogos.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        logo, logos = SponsorHelper.ValidSponsors(team)
        for path in logos or ([logo] if logo else []):
            preview = ImagePreview(size=64)
            preview.SetImage(path)
            preview.setToolTip(os.path.basename(path))
            self.sponsorLogos.addWidget(preview)
        self.sponsorLogos.addStretch()
        if not team:
            self.sponsorLabel.setText(QApplication.translate("app", "No sponsor."))
        elif logo:
            self.sponsorLabel.setText(
                QApplication.translate("app", "Manage every logo in the Sponsor logos tab.")
            )
        else:
            self.sponsorLabel.setText(
                QApplication.translate("app", "No logo for {0}.").format(team)
            )
        self.sponsorAddBt.setVisible(bool(team))
        self.sponsorAddBt.setText(
            QApplication.translate("app", "Set the logo of {0}...").format(team)
        )

        # Custom data
        folder = self.CustomFolder()
        exists = folder is not None and os.path.isdir(folder)
        if not hasName:
            text = ""
        elif exists:
            text = QApplication.translate("app", "Files in {0}").format(
                os.path.relpath(folder, "./user_data")
            )
        else:
            text = QApplication.translate("app", "No files yet. They will be saved in {0}").format(
                os.path.relpath(folder, "./user_data")
            )
        if not DynamicExport.Enabled():
            text += "\n" + QApplication.translate(
                "app", "Custom data isn't sent to the layouts: it's turned off in Settings."
            )
        self.customLabel.setText(text)
        for widget in [self.files, self.newTextBt, self.addFilesBt, self.openFolderBt]:
            widget.setEnabled(hasName)
        self.RefreshFiles()

    # Avatar

    def ChooseAvatar(self):
        path, _ = QFileDialog.getOpenFileName(
            self, QApplication.translate("app", "Choose an avatar"), "", MediaHelper.ImageFilter()
        )
        if path:
            self.SetAvatar(path)

    def SetAvatar(self, source: str):
        team, name = self.Person()
        if not name:
            return
        destination = MediaHelper.NewAvatarPath(team, name)
        if not ConfirmOverwrite(self, destination):
            return
        try:
            MediaHelper.SaveImageAsPng(source, destination)
        except OSError as e:
            ShowError(self, str(e))
            return
        MediaHelper.Changed()
        self.LoadPerson()

    def RemoveAvatar(self):
        team, name = self.Person()
        avatar = MediaHelper.FindAvatar(team, name)
        if avatar:
            MediaHelper.Remove(avatar)
        MediaHelper.Changed()
        self.LoadPerson()

    def ChooseSponsorLogo(self):
        team, _ = self.Person()
        if not team:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            QApplication.translate("app", "Choose the logo of {0}").format(team),
            "",
            MediaHelper.ImageFilter(),
        )
        if not path:
            return
        destination = MediaHelper.SponsorLogoPath(team)
        if not ConfirmOverwrite(self, destination):
            return
        try:
            MediaHelper.SaveImageAsPng(path, destination)
        except OSError as e:
            ShowError(self, str(e))
            return
        MediaHelper.Changed()
        self.LoadPerson()

    # Custom data

    def CustomFolder(self) -> str | None:
        """The person's folder, or where it would be made"""
        team, name = self.Person()
        if not name:
            return None
        return DynamicExport.FindCustomFolder(name, team) or MediaHelper.CustomFolderPath(name)

    def RefreshFiles(self, select: str | None = None):
        current = self.files.currentItem()
        select = select or (current.data(PathRole) if current else None)
        self.files.blockSignals(True)
        self.files.clear()
        folder = self.CustomFolder()
        if folder and os.path.isdir(folder):
            for entry in DynamicExport.Files(folder):
                stem, ext = os.path.splitext(entry.name)
                item = QListWidgetItem(entry.name)
                item.setData(PathRole, entry.path)
                key = stem.strip().replace(".", "_")
                item.setToolTip(f"custom.{key}")
                if MediaHelper.IsImage(entry.name):
                    item.setIcon(QIcon(entry.path))
                self.files.addItem(item)
                if entry.path == select:
                    self.files.setCurrentItem(item)
        self.files.blockSignals(False)
        self.FileSelected(self.files.currentItem())

    def FileSelected(self, item, _previous=None):
        path = item.data(PathRole) if item else None
        if path != self.editingFile and not self.ConfirmDiscard():
            # Back to the file being edited
            for i in range(self.files.count()):
                if self.files.item(i).data(PathRole) == self.editingFile:
                    self.files.blockSignals(True)
                    self.files.setCurrentRow(i)
                    self.files.blockSignals(False)
            return
        self.editingFile = path
        self.dirty = False
        self.renameBt.setEnabled(path is not None)
        self.deleteBt.setEnabled(path is not None)

        if path is None:
            self.editorStack.setCurrentWidget(self.editorEmpty)
            return

        ext = os.path.splitext(path)[1].lower()
        if ext in self.TEXT_EXTENSIONS:
            try:
                with open(path, encoding="utf-8-sig") as f:
                    text = f.read()
            except (OSError, UnicodeDecodeError) as e:
                self.fileInfo.setText(str(e))
                self.editorStack.setCurrentIndex(3)
                return
            self.loadingText = True
            self.textEdit.setPlainText(text)
            self.loadingText = False
            self.textStatus.setText("")
            self.textStatus.setStyleSheet("")
            self.textSaveBt.setEnabled(False)
            self.editorStack.setCurrentIndex(1)
        elif MediaHelper.IsImage(path):
            self.filePreview.SetImage(path)
            self.editorStack.setCurrentWidget(self.filePreview)
        else:
            self.fileInfo.setText(
                QApplication.translate("app", "Layouts get its path: {0}").format(path)
            )
            self.editorStack.setCurrentWidget(self.fileInfo)

    def TextChanged(self):
        if self.loadingText:
            return
        self.dirty = True
        self.textSaveBt.setEnabled(True)
        self.textStatus.setText(QApplication.translate("app", "Not saved"))

    def SaveText(self):
        if not self.editingFile or not self.dirty:
            return True
        text = self.textEdit.toPlainText()
        if self.editingFile.lower().endswith(".json"):
            try:
                orjson.loads(text)
            except orjson.JSONDecodeError as e:
                self.textStatus.setText(
                    QApplication.translate("app", "Not valid JSON: {0}").format(e)
                )
                self.textStatus.setStyleSheet("color: #f44336")
                return False
        try:
            with open(self.editingFile, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as e:
            ShowError(self, str(e))
            return False
        self.dirty = False
        self.textSaveBt.setEnabled(False)
        self.textStatus.setStyleSheet("")
        self.textStatus.setText(QApplication.translate("app", "Saved"))
        MediaHelper.Changed()
        return True

    def ConfirmDiscard(self) -> bool:
        """Asks what to do with unsaved text. False to stay on it."""
        if not self.dirty:
            return True
        answer = QMessageBox.question(
            self,
            QApplication.translate("app", "Unsaved changes"),
            QApplication.translate("app", "Save the changes to {0}?").format(
                os.path.basename(self.editingFile)
            ),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Save:
            return self.SaveText()
        if answer == QMessageBox.StandardButton.Discard:
            self.dirty = False
            return True
        return False

    def AskFileName(self, title: str, default: str) -> str | None:
        name, ok = QInputDialog.getText(
            self,
            title,
            QApplication.translate(
                "app", "File name. Layouts get it by its name without the extension."
            ),
            text=default,
        )
        name = MediaHelper.Sanitize(name.strip()) if ok else ""
        return name or None

    def NewTextFile(self):
        folder = self.CustomFolder()
        name = self.AskFileName(QApplication.translate("app", "New text"), "bio.txt")
        if not folder or not name:
            return
        if not os.path.splitext(name)[1]:
            name += ".txt"
        path = f"{folder}/{name}"
        if os.path.exists(path):
            ShowError(self, QApplication.translate("app", "{0} already exists.").format(name))
            return
        os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8"):
            pass
        MediaHelper.Changed()
        self.LoadPerson()
        self.RefreshFiles(select=path)
        self.textEdit.setFocus()

    def ChooseFiles(self):
        paths, _ = QFileDialog.getOpenFileNames(self, QApplication.translate("app", "Add files"))
        if paths:
            self.AddFiles(paths)

    def AddFiles(self, paths: list[str]):
        folder = self.CustomFolder()
        if not folder:
            return
        os.makedirs(folder, exist_ok=True)
        last = None
        for source in paths:
            destination = f"{folder}/{os.path.basename(source)}"
            if os.path.abspath(source) == os.path.abspath(destination):
                continue
            if not ConfirmOverwrite(self, destination):
                continue
            try:
                shutil.copyfile(source, destination)
            except OSError as e:
                ShowError(self, str(e))
                continue
            last = destination
        MediaHelper.Changed()
        self.LoadPerson()
        if last:
            self.RefreshFiles(select=last)

    def RenameFile(self):
        item = self.files.currentItem()
        if not item or not self.ConfirmDiscard():
            return
        path = item.data(PathRole)
        oldName = os.path.basename(path)
        name = self.AskFileName(QApplication.translate("app", "Rename"), oldName)
        if not name or name == oldName:
            return
        if not os.path.splitext(name)[1]:
            name += os.path.splitext(oldName)[1]
        destination = f"{os.path.dirname(path)}/{name}"
        # Only the case changed: the same file on Windows and macOS
        if name.lower() != oldName.lower() and os.path.exists(destination):
            ShowError(self, QApplication.translate("app", "{0} already exists.").format(name))
            return
        try:
            os.replace(path, destination)
        except OSError as e:
            ShowError(self, str(e))
            return
        self.dirty = False
        MediaHelper.Changed()
        self.RefreshFiles(select=destination)

    def DeleteFile(self):
        item = self.files.currentItem()
        if not item:
            return
        path = item.data(PathRole)
        answer = QMessageBox.question(
            self,
            QApplication.translate("app", "Delete"),
            QApplication.translate("app", "Delete {0}?").format(os.path.basename(path)),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.dirty = False
        MediaHelper.Remove(path)
        MediaHelper.Changed()
        self.RefreshFiles()


class LogoGridTab(QWidget):
    """The images in a logo folder (sponsor logos, team logos): add, rename
    and delete them"""

    def __init__(self, folder: str, pathFor: Callable[[str], str], hint: str, parent=None):
        super().__init__(parent)
        self.folder = folder
        self.pathFor = pathFor

        self.setLayout(QVBoxLayout())

        top = QHBoxLayout()
        self.layout().addLayout(top)
        self.search = QLineEdit()
        self.search.setPlaceholderText(QApplication.translate("app", "Search..."))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.Filter)
        top.addWidget(self.search)

        hintLabel = QLabel(hint)
        hintLabel.setWordWrap(True)
        self.layout().addWidget(hintLabel)

        self.grid = QListWidget()
        self.grid.setViewMode(QListView.ViewMode.IconMode)
        self.grid.setIconSize(QSize(96, 96))
        self.grid.setGridSize(QSize(132, 132))
        self.grid.setResizeMode(QListView.ResizeMode.Adjust)
        self.grid.setMovement(QListView.Movement.Static)
        self.grid.setWordWrap(True)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.grid.itemSelectionChanged.connect(self.UpdateButtons)
        self.grid.itemDoubleClicked.connect(lambda _: self.Rename())
        FileDropFilter(self.grid.viewport(), self.AddImages, imagesOnly=True)
        self.layout().addWidget(self.grid)

        buttons = QHBoxLayout()
        self.layout().addLayout(buttons)
        self.countLabel = QLabel()
        buttons.addWidget(self.countLabel)
        buttons.addStretch()
        self.addBt = QPushButton(QApplication.translate("app", "Add..."))
        self.addBt.clicked.connect(self.ChooseImages)
        buttons.addWidget(self.addBt)
        self.renameBt = QPushButton(QApplication.translate("app", "Rename..."))
        self.renameBt.clicked.connect(self.Rename)
        buttons.addWidget(self.renameBt)
        self.deleteBt = QPushButton(QApplication.translate("app", "Delete"))
        self.deleteBt.setIcon(ThemedIcon("./assets/icons/cancel.svg"))
        self.deleteBt.clicked.connect(self.Delete)
        buttons.addWidget(self.deleteBt)
        openBt = QPushButton(QApplication.translate("app", "Open folder"))
        openBt.clicked.connect(lambda: OpenFolder(self.folder))
        buttons.addWidget(openBt)

        self.UpdateButtons()

    def showEvent(self, event):
        self.Refresh()
        super().showEvent(event)

    def Refresh(self, select: list[str] | None = None):
        select = select if select is not None else [i.text() for i in self.grid.selectedItems()]
        self.grid.clear()
        names = MediaHelper.ListPngs(self.folder)
        for name in names:
            path = f"{self.folder}/{name}.png"
            item = QListWidgetItem(QIcon(QPixmap(path)), name)
            item.setData(PathRole, path)
            item.setToolTip(f"{name}.png")
            self.grid.addItem(item)
            if name in select:
                item.setSelected(True)
        self.countLabel.setText(QApplication.translate("app", "{0} logos").format(len(names)))
        self.Filter(self.search.text())

    def Filter(self, text: str):
        for i in range(self.grid.count()):
            item = self.grid.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def UpdateButtons(self):
        selected = self.grid.selectedItems()
        self.renameBt.setEnabled(len(selected) == 1)
        self.deleteBt.setEnabled(len(selected) > 0)

    def AskName(self, title: str, default: str) -> str | None:
        name, ok = QInputDialog.getText(
            self,
            title,
            QApplication.translate("app", "Name, as typed in HyperDrive:"),
            text=default,
        )
        return name.strip() if ok and name.strip() else None

    def ChooseImages(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, QApplication.translate("app", "Add logos"), "", MediaHelper.ImageFilter()
        )
        if paths:
            self.AddImages(paths)

    def AddImages(self, paths: list[str]):
        added = []
        for source in paths:
            default = os.path.splitext(os.path.basename(source))[0]
            name = self.AskName(QApplication.translate("app", "Add logo"), default)
            if not name:
                continue
            destination = self.pathFor(name)
            if not ConfirmOverwrite(self, destination):
                continue
            try:
                MediaHelper.SaveImageAsPng(source, destination)
            except OSError as e:
                ShowError(self, str(e))
                continue
            added.append(os.path.splitext(os.path.basename(destination))[0])
        if added:
            MediaHelper.Changed()
            self.Refresh(select=added)

    def Rename(self):
        selected = self.grid.selectedItems()
        if len(selected) != 1:
            return
        path = selected[0].data(PathRole)
        oldName = selected[0].text()
        name = self.AskName(QApplication.translate("app", "Rename logo"), oldName)
        if not name:
            return
        destination = self.pathFor(name)
        if destination == path:
            return
        # Only the case changed: the same file on Windows and macOS
        sameFile = os.path.basename(destination).lower() == os.path.basename(path).lower()
        if not sameFile and not ConfirmOverwrite(self, destination):
            return
        try:
            os.replace(path, destination)
        except OSError as e:
            ShowError(self, str(e))
            return
        MediaHelper.Changed()
        self.Refresh(select=[os.path.splitext(os.path.basename(destination))[0]])

    def Delete(self):
        selected = self.grid.selectedItems()
        if not selected:
            return
        answer = QMessageBox.question(
            self,
            QApplication.translate("app", "Delete"),
            QApplication.translate("app", "Delete {0} logos?").format(len(selected))
            if len(selected) > 1
            else QApplication.translate("app", "Delete {0}?").format(selected[0].text()),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        for item in selected:
            MediaHelper.Remove(item.data(PathRole))
        MediaHelper.Changed()
        self.Refresh(select=[])


def SponsorLogosTab():
    return LogoGridTab(
        SPONSOR_LOGO_DIR,
        MediaHelper.SponsorLogoPath,
        QApplication.translate(
            "app",
            "A player gets the logo of the sponsor typed for them, e.g. HD. With more than "
            "one sponsor (HD | GG), the logo of all of them if there is one, otherwise each "
            "one's. Drop images here to add them.",
        ),
    )


def TeamLogosTab():
    return LogoGridTab(
        TEAM_LOGO_DIR,
        MediaHelper.TeamLogoPath,
        QApplication.translate(
            "app",
            "A team on the scoreboard gets the logo named after its team name. "
            "Drop images here to add them.",
        ),
    )
