import os
import traceback

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .AssetDownloader import (
    JOB_CANCELLED,
    JOB_DONE,
    JOB_DOWNLOADING,
    JOB_FAILED,
    JOB_QUEUED,
    JOB_UNPACKING,
    AssetDownloader,
)
from .GameAssetManager import GameAssetManager
from .Helpers import AssetCatalog
from .Helpers.AssetCatalog import BASE_FILES, STATE_INSTALLED, STATE_NEW, STATE_UPDATE
from .Theme import Theme, ThemedIcon

LOGO_WIDTH = 64
LOGO_HEIGHT = 36
SIDEBAR_WIDTH = 300
TAGS_WIDTH = 210
SIZE_WIDTH = 84
STATUS_WIDTH = 250
# Rows the downloads panel shows before it scrolls
DOWNLOAD_ROWS_SHOWN = 4

FILTER_ALL = "all"
FILTER_INSTALLED = "installed"
FILTER_UPDATES = "updates"


# =====================================================
# HELPERS
# =====================================================
def Colors():
    colors = Theme.Colors()
    dark = Theme.IsDark()
    # Readable as text on the window, in dark and light themes
    colors["ok"] = QColor("#4cc38a" if dark else "#15803d")
    colors["warn"] = QColor("#f0b44c" if dark else "#b45309")
    colors["info"] = QColor("#7aa2ff" if dark else "#1d4ed8")
    return colors


def Label(text="", color=None, scale=1.0, bold=False, wrap=False):
    label = QLabel(text)
    if color is not None:
        label.setStyleSheet(f"color: {color.name()};")
    if scale != 1.0 or bold:
        font = label.font()
        if scale != 1.0:
            font.setPointSizeF(font.pointSizeF() * scale)
        font.setBold(bold)
        label.setFont(font)
    label.setWordWrap(wrap)
    return label


class ElidedLabel(QLabel):
    """A one-line label that ends in … instead of growing past its space."""

    def __init__(self, text="", color=None, scale=1.0, bold=False):
        super().__init__()
        self.fullText = ""
        if color is not None:
            self.setStyleSheet(f"color: {color.name()};")
        if scale != 1.0 or bold:
            font = self.font()
            font.setPointSizeF(font.pointSizeF() * scale)
            font.setBold(bold)
            self.setFont(font)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text):
        self.fullText = text or ""
        self._Elide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._Elide()

    def _Elide(self):
        metrics = self.fontMetrics()
        super().setText(
            metrics.elidedText(self.fullText, Qt.TextElideMode.ElideRight, self.width())
        )

    def sizeHint(self):
        return QSize(
            self.fontMetrics().horizontalAdvance(self.fullText), super().sizeHint().height()
        )


def Logo(source, width, height):
    """A game logo (file path or PNG bytes) fitted to width × height, or None."""
    pixmap = QPixmap()
    if isinstance(source, (bytes, bytearray)):
        pixmap.loadFromData(source)
    elif source:
        pixmap.load(source)
    if pixmap.isNull():
        return None
    return pixmap.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def LogoTile(width, height, colors):
    tile = QLabel()
    tile.setFixedSize(width, height)
    tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
    tile.setStyleSheet(f"background: {colors['window'].name()}; border-radius: {Theme.Radius()}px;")
    return tile


def Pill(text, colors):
    pill = Label(text, colors["text"], scale=0.85)
    pill.setStyleSheet(
        f"color: {colors['text'].name()}; border: 1px solid {colors['border'].name()};"
        "border-radius: 4px; padding: 1px 7px;"
    )
    pill.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return pill


def Button(text=""):
    """A button that Enter doesn't press: in a dialog, buttons take Enter by
    default, and only the download button should."""
    button = QPushButton(text)
    button.setAutoDefault(False)
    return button


def PackName(catalog, game, pack):
    # The catalog names base files after the game
    if pack == BASE_FILES:
        return QApplication.translate("app", "Base files")
    return str(catalog[game]["assets"][pack].get("name", pack))


def FormatVersion(version):
    """A version (26.10.02.40910) as its date, e.g. Oct 2."""
    date = AssetCatalog.VersionDate(version)
    if date is None:
        return str(version or "")
    qdate = QDate(date.year, date.month, date.day)
    fmt = "MMM d" if date.year == QDate.currentDate().year() else "MMM d, yyyy"
    return QLocale().toString(qdate, fmt)


def FormatDuration(seconds):
    if seconds is None:
        return ""
    if seconds < 60:
        return QApplication.translate("app", "less than a minute left")
    minutes = round(seconds / 60)
    if minutes < 60:
        return QApplication.translate("app", "about {0} min left").format(minutes)
    return QApplication.translate("app", "about {0} h {1} min left").format(
        minutes // 60, minutes % 60
    )


def PackCount(n):
    if n == 1:
        return QApplication.translate("app", "1 pack")
    return QApplication.translate("app", "{0} packs").format(n)


def InstalledCatalog(games):
    """A catalog of what's installed, shown when the real one can't be loaded."""
    catalog = {}
    for game, info in games.items():
        # Alternate versions share their game's folder
        if info.get("base_game_dir"):
            continue
        packs = {
            pack: {
                "name": config.get("name", pack),
                "version": config.get("version", ""),
                "description": config.get("description", ""),
                "credits": config.get("credits"),
                "files": {},
            }
            for pack, config in info.get("assets", {}).items()
            # Folders inside base_files are part of it, not packs
            if "/" not in pack
        }
        catalog[game] = {"name": info.get("name", game), "assets": packs}
    return catalog


# =====================================================
# GAME LIST
# =====================================================
class GameRow(QWidget):
    def __init__(self, name, colors):
        super().__init__()
        self.colors = colors
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(12)

        self.logo = LogoTile(LOGO_WIDTH, LOGO_HEIGHT, colors)
        layout.addWidget(self.logo)

        column = QVBoxLayout()
        column.setSpacing(2)
        layout.addLayout(column, 1)
        column.addWidget(ElidedLabel(name))

        subRow = QHBoxLayout()
        subRow.setSpacing(8)
        column.addLayout(subRow)
        self.sub = Label("", colors["muted"], scale=0.9)
        subRow.addWidget(self.sub)
        self.badge = Label("", colors["warn"], scale=0.9)
        subRow.addWidget(self.badge)
        subRow.addStretch()
        self.setToolTip(name)

    def SetLogo(self, pixmap):
        if pixmap is not None:
            self.logo.setPixmap(pixmap)

    def SetInfo(self, sub, badge=""):
        self.sub.setText(sub)
        self.badge.setText(badge)
        self.badge.setVisible(bool(badge))


# =====================================================
# PACK ROWS
# =====================================================
class PackRow(QFrame):
    def __init__(self, window, game, pack):
        super().__init__()
        self.window = window
        self.game = game
        self.pack = pack
        colors = window.colors
        self.colors = colors
        info = window.catalog[game]["assets"][pack]

        self.setObjectName("packRow")
        self.setStyleSheet(
            f"QFrame#packRow {{ border-bottom: 1px solid {colors['raised'].name()}; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        self.check = QCheckBox()
        name = PackName(window.catalog, game, pack)
        self.check.setAccessibleName(QApplication.translate("app", "Select {0}").format(name))
        self.check.toggled.connect(lambda checked: window.SetSelected(game, pack, checked))
        checkBox = QWidget()
        checkBox.setFixedWidth(24)
        checkLayout = QHBoxLayout(checkBox)
        checkLayout.setContentsMargins(0, 0, 0, 0)
        checkLayout.addWidget(self.check)
        layout.addWidget(checkBox)

        # Name, description and credits
        column = QVBoxLayout()
        column.setSpacing(2)
        layout.addLayout(column, 1)
        nameRow = QHBoxLayout()
        nameRow.setSpacing(8)
        column.addLayout(nameRow)
        nameRow.addWidget(Label(name, bold=True))
        if pack == BASE_FILES:
            required = Pill(QApplication.translate("app", "Required"), colors)
            required.setToolTip(
                QApplication.translate("app", "Every other pack of the game needs these")
            )
            nameRow.addWidget(required)
        nameRow.addStretch()

        description = str(info.get("description") or "")
        credits = str(info.get("credits") or "").strip()
        if pack == BASE_FILES and not description:
            description = QApplication.translate("app", "Base config to use this game.")
        column.addWidget(ElidedLabel(description.replace("\n", " "), colors["muted"]))
        if credits:
            column.addWidget(
                ElidedLabel(
                    QApplication.translate("app", "Credits: {0}").format(
                        credits.replace("\n", " ")
                    ),
                    colors["muted"],
                    scale=0.9,
                )
            )
        tooltip = description
        if credits:
            tooltip += "\n\n" + QApplication.translate("app", "Credits:") + "\n" + credits
        self.setToolTip(tooltip)

        # What the pack includes
        tags = QHBoxLayout()
        tags.setSpacing(6)
        if info.get("has_stage_data"):
            tags.addWidget(Pill(QApplication.translate("app", "Stage data"), colors))
        if info.get("has_eyesight_data"):
            tags.addWidget(Pill(QApplication.translate("app", "Eyesight data"), colors))
        tags.addStretch()
        tagsBox = QWidget()
        tagsBox.setFixedWidth(TAGS_WIDTH)
        tagsBox.setLayout(tags)
        tags.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(tagsBox)

        size = AssetCatalog.PackSize(window.catalog, game, pack)
        sizeLabel = Label(AssetCatalog.FormatSize(size) if size else "", colors["text"])
        sizeLabel.setFixedWidth(SIZE_WIDTH)
        sizeLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(sizeLabel)

        # Status, and what can be done with the pack
        status = QWidget()
        status.setFixedWidth(STATUS_WIDTH)
        statusLayout = QHBoxLayout(status)
        statusLayout.setContentsMargins(8, 0, 0, 0)
        statusLayout.setSpacing(8)
        statusColumn = QVBoxLayout()
        statusColumn.setSpacing(3)
        statusLayout.addLayout(statusColumn, 1)
        self.statusLabel = Label("")
        statusColumn.addWidget(self.statusLabel)
        self.detailLabel = Label("", colors["muted"], scale=0.9)
        statusColumn.addWidget(self.detailLabel)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        statusColumn.addWidget(self.progress)

        self.updateButton = Button(QApplication.translate("app", "Update"))
        self.updateButton.clicked.connect(lambda: window.downloader.Enqueue([(game, pack)]))
        statusLayout.addWidget(self.updateButton)

        self.moreButton = QToolButton()
        self.moreButton.setText("⋯")
        self.moreButton.setAccessibleName(
            QApplication.translate("app", "More actions for {0}").format(name)
        )
        self.moreButton.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.moreButton.setStyleSheet("QToolButton::menu-indicator { image: none; }")
        menu = QMenu(self.moreButton)
        menu.addAction(
            QApplication.translate("app", "Open folder"), lambda: window.OpenFolder(game, pack)
        )
        if pack != BASE_FILES:
            menu.addAction(
                QApplication.translate("app", "Remove…"), lambda: window.ConfirmRemove(game, pack)
            )
        self.moreButton.setMenu(menu)
        statusLayout.addWidget(self.moreButton)
        layout.addWidget(status)

        self.Refresh()

    def Refresh(self):
        window = self.window
        colors = self.colors
        game, pack = self.game, self.pack
        job = window.downloader.ActiveJob(game, pack)
        state = window.PackState(game, pack)
        auto = window.IsAutoBase(game, pack)
        info = window.catalog[game]["assets"][pack]

        selectable = not window.offline and job is None and state != STATE_INSTALLED and not auto
        self.check.setVisible(
            not window.offline and (state != STATE_INSTALLED or auto) and job is None
        )
        self.check.setEnabled(selectable)
        self.check.blockSignals(True)
        self.check.setChecked(auto or pack in window.selection.get(game, set()))
        self.check.blockSignals(False)

        self.updateButton.setVisible(not window.offline and job is None and state == STATE_UPDATE)
        self.moreButton.setVisible(job is None and state != STATE_NEW)
        self.progress.setVisible(job is not None and job.state != JOB_QUEUED)

        installed = AssetCatalog.InstalledVersion(window.installedGames, game, pack)
        latest = info.get("version", "")
        if job is not None:
            self.RefreshJob(job)
        elif auto:
            self.SetStatus(QApplication.translate("app", "Added automatically"), colors["info"], "")
        elif window.downloader.JustInstalled(game, pack):
            self.SetStatus(
                QApplication.translate("app", "Installed"),
                colors["ok"],
                QApplication.translate("app", "just now"),
            )
        elif state == STATE_INSTALLED:
            self.SetStatus(
                QApplication.translate("app", "Installed"), colors["ok"], FormatVersion(installed)
            )
        elif state == STATE_UPDATE:
            self.SetStatus(
                QApplication.translate("app", "Update available"),
                colors["warn"],
                f"{FormatVersion(installed)} → {FormatVersion(latest)}",
            )
        else:
            self.SetStatus(QApplication.translate("app", "Not installed"), colors["muted"], "")

    def RefreshJob(self, job):
        colors = self.colors
        if job.cancelRequested:
            self.SetStatus(QApplication.translate("app", "Cancelling…"), colors["muted"], "")
        elif job.state == JOB_QUEUED:
            self.SetStatus(QApplication.translate("app", "Waiting in queue"), colors["muted"], "")
        elif job.state == JOB_UNPACKING:
            self.SetStatus(QApplication.translate("app", "Unpacking…"), colors["text"], "")
            self.progress.setRange(0, 0)
        elif job.state == JOB_DOWNLOADING:
            percent = round(100 * job.done / job.total) if job.total else 0
            self.SetStatus(
                QApplication.translate("app", "Downloading · {0}%").format(percent),
                colors["text"],
                "",
            )
            self.progress.setRange(0, 1000)
            self.progress.setValue(round(1000 * job.done / job.total) if job.total else 0)

    def SetStatus(self, text, color, detail):
        self.statusLabel.setText(text)
        self.statusLabel.setStyleSheet(f"color: {color.name()};")
        self.detailLabel.setText(detail)
        self.detailLabel.setVisible(bool(detail))


# =====================================================
# DOWNLOADS PANEL
# =====================================================
class DownloadRow(QWidget):
    def __init__(self, window, job):
        super().__init__()
        self.window = window
        self.job = job
        colors = window.colors
        self.colors = colors
        downloader = window.downloader

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 6, 20, 6)
        layout.setSpacing(14)

        self.logo = LogoTile(48, 28, colors)
        logo = window.GameLogo(job.game, 42, 20)
        if logo is not None:
            self.logo.setPixmap(logo)
        layout.addWidget(self.logo)

        column = QVBoxLayout()
        column.setSpacing(2)
        layout.addLayout(column, 1)
        column.addWidget(ElidedLabel(f"{job.packName} · {job.gameName}"))
        self.detail = ElidedLabel("", colors["muted"], scale=0.9)
        column.addWidget(self.detail)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedSize(260, 6)
        layout.addWidget(self.progress)

        self.cancelButton = QToolButton()
        self.cancelButton.setText("✕")
        self.cancelButton.setAccessibleName(
            QApplication.translate("app", "Cancel {0}").format(job.packName)
        )
        self.cancelButton.setToolTip(QApplication.translate("app", "Cancel"))
        self.cancelButton.clicked.connect(lambda: downloader.Cancel(job))
        layout.addWidget(self.cancelButton)

        self.retryButton = Button(QApplication.translate("app", "Retry"))
        self.retryButton.clicked.connect(lambda: downloader.Retry(job))
        layout.addWidget(self.retryButton)

        self.doneLabel = Label("✓", colors["ok"], bold=True)
        self.doneLabel.setAccessibleName(QApplication.translate("app", "Installed"))
        layout.addWidget(self.doneLabel)

        self.Refresh()

    def Refresh(self):
        job = self.job
        colors = self.colors
        size = AssetCatalog.FormatSize(job.total)
        detailColor = colors["muted"]
        self.progress.setRange(0, 1000)

        if job.cancelRequested and job.active:
            detail = QApplication.translate("app", "Cancelling…")
        elif job.state == JOB_QUEUED:
            detail = QApplication.translate("app", "Waiting · {0}").format(size)
            self.progress.setValue(0)
        elif job.state == JOB_DOWNLOADING:
            parts = [
                QApplication.translate("app", "{0} of {1}").format(
                    AssetCatalog.FormatSize(job.done), size
                )
            ]
            if job.speed > 0:
                parts.append(f"{AssetCatalog.FormatSize(job.speed)}/s")
                parts.append(FormatDuration(job.SecondsLeft()))
            detail = " · ".join(parts)
            self.progress.setValue(round(1000 * job.done / job.total) if job.total else 0)
        elif job.state == JOB_UNPACKING:
            detail = QApplication.translate("app", "Unpacking {0}…").format(size)
            self.progress.setRange(0, 0)
        elif job.state == JOB_DONE:
            detail = QApplication.translate("app", "Installed")
            detailColor = colors["ok"]
            self.progress.setValue(1000)
        elif job.state == JOB_FAILED:
            detail = QApplication.translate("app", "Failed: {0}").format(job.error)
            detailColor = colors["warn"]
            self.progress.setValue(0)
        else:
            detail = QApplication.translate("app", "Cancelled")
            self.progress.setValue(0)

        self.detail.setText(detail)
        self.detail.setToolTip(job.error if job.state == JOB_FAILED else "")
        self.detail.setStyleSheet(f"color: {detailColor.name()};")
        self.cancelButton.setVisible(job.active and not job.cancelRequested)
        self.retryButton.setVisible(job.state in (JOB_FAILED, JOB_CANCELLED))
        self.doneLabel.setVisible(job.state == JOB_DONE)


class DownloadsPanel(QFrame):
    def __init__(self, window):
        super().__init__()
        self.window = window
        downloader = window.downloader
        colors = window.colors
        self.rows = {}

        self.setObjectName("downloadsPanel")
        self.setStyleSheet(
            f"QFrame#downloadsPanel {{ background: {colors['surface'].name()};"
            f"border-top: 1px solid {colors['border'].name()}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(20, 10, 20, 10)
        header.setSpacing(12)
        layout.addLayout(header)
        header.addWidget(Label(QApplication.translate("app", "Downloads"), bold=True))
        self.summary = Label("", colors["muted"])
        header.addWidget(self.summary)
        header.addStretch()
        self.hint = Label(
            QApplication.translate("app", "Downloads keep going if you close this window"),
            colors["muted"],
            scale=0.9,
        )
        header.addWidget(self.hint)
        self.clearButton = Button(QApplication.translate("app", "Clear finished"))
        self.clearButton.clicked.connect(downloader.ClearFinished)
        header.addWidget(self.clearButton)
        self.cancelAllButton = Button(QApplication.translate("app", "Cancel all"))
        self.cancelAllButton.clicked.connect(downloader.CancelAll)
        header.addWidget(self.cancelAllButton)
        self.collapseButton = QToolButton()
        self.collapseButton.setCheckable(True)
        self.collapseButton.setArrowType(Qt.ArrowType.DownArrow)
        self.collapseButton.setAccessibleName(
            QApplication.translate("app", "Show or hide the downloads")
        )
        self.collapseButton.toggled.connect(self.SetCollapsed)
        header.addWidget(self.collapseButton)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list = QWidget()
        self.listLayout = QVBoxLayout(self.list)
        self.listLayout.setContentsMargins(0, 0, 0, 0)
        self.listLayout.setSpacing(0)
        self.listLayout.addStretch()
        self.scroll.setWidget(self.list)
        layout.addWidget(self.scroll)

        downloader.signals.jobsChanged.connect(self.Refresh)
        downloader.signals.jobProgress.connect(self.UpdateJob)
        self.Refresh()

    def SetCollapsed(self, collapsed):
        self.scroll.setVisible(not collapsed)
        self.collapseButton.setArrowType(
            Qt.ArrowType.UpArrow if collapsed else Qt.ArrowType.DownArrow
        )

    def Refresh(self):
        jobs = self.window.downloader.jobs
        for job, row in list(self.rows.items()):
            if job not in jobs:
                row.deleteLater()
                del self.rows[job]
        for i, job in enumerate(jobs):
            row = self.rows.get(job)
            if row is None:
                row = DownloadRow(self.window, job)
                self.rows[job] = row
            self.listLayout.insertWidget(i, row)
            row.Refresh()

        rowHeight = max((r.sizeHint().height() for r in self.rows.values()), default=0)
        self.scroll.setFixedHeight(rowHeight * min(len(jobs), DOWNLOAD_ROWS_SHOWN) + 4)
        self.setVisible(len(jobs) > 0)
        self.RefreshSummary()

    def UpdateJob(self, job):
        row = self.rows.get(job)
        if row is not None:
            row.Refresh()
        self.RefreshSummary()

    def RefreshSummary(self):
        jobs = self.window.downloader.jobs
        active = [j for j in jobs if j.active]
        finished = [j for j in jobs if not j.active]
        if active:
            left = sum(max(0, j.total - j.done) for j in active)
            text = QApplication.translate("app", "{0} in progress · {1} left").format(
                len(active), AssetCatalog.FormatSize(left)
            )
            running = self.window.downloader.runningJob
            if running is not None and running.speed > 0:
                text += " · " + FormatDuration(left / running.speed)
        else:
            text = QApplication.translate("app", "All done")
        self.summary.setText(text)
        self.hint.setVisible(bool(active))
        self.cancelAllButton.setVisible(bool(active))
        self.clearButton.setVisible(bool(finished))


# =====================================================
# UPDATES DIALOG
# =====================================================
class UpdatesDialog(QDialog):
    """Lists the packs "update all" would download, to untick any before starting."""

    def __init__(self, window, updates):
        super().__init__(window)
        self.window = window
        colors = window.colors
        catalog = window.catalog
        self.setWindowTitle(QApplication.translate("app", "Review updates"))
        self.setMinimumWidth(640)
        self.checks = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(
            Label(
                QApplication.translate("app", "Review {0} updates").format(len(updates)),
                scale=1.4,
                bold=True,
            )
        )
        layout.addWidget(
            Label(
                QApplication.translate(
                    "app",
                    "Newer versions of packs you have installed. Untick any you want to keep as they are.",
                ),
                colors["muted"],
                wrap=True,
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        listLayout = QVBoxLayout(content)
        listLayout.setContentsMargins(0, 0, 0, 0)
        listLayout.setSpacing(4)
        lastGame = None
        for game, pack in updates:
            info = catalog[game]["assets"][pack]
            if game != lastGame:
                lastGame = game
                gameRow = QHBoxLayout()
                gameRow.setSpacing(10)
                tile = LogoTile(52, 28, colors)
                logo = window.GameLogo(game, 46, 20)
                if logo is not None:
                    tile.setPixmap(logo)
                gameRow.addWidget(tile)
                gameRow.addWidget(
                    Label(catalog[game].get("name", game), colors["muted"], bold=True)
                )
                gameRow.addStretch()
                listLayout.addSpacing(8)
                listLayout.addLayout(gameRow)

            row = QHBoxLayout()
            row.setContentsMargins(8, 0, 0, 0)
            check = QCheckBox(PackName(catalog, game, pack))
            check.setChecked(True)
            check.toggled.connect(self.RefreshTotal)
            row.addWidget(check, 1)
            installed = AssetCatalog.InstalledVersion(window.installedGames, game, pack)
            row.addWidget(
                Label(
                    f"{FormatVersion(installed)} → {FormatVersion(info.get('version'))}",
                    colors["muted"],
                )
            )
            size = AssetCatalog.PackSize(catalog, game, pack)
            sizeLabel = Label(AssetCatalog.FormatSize(size))
            sizeLabel.setFixedWidth(SIZE_WIDTH)
            sizeLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(sizeLabel)
            listLayout.addLayout(row)
            self.checks.append((check, game, pack, size))
        listLayout.addStretch()
        scroll.setWidget(content)
        scroll.setMinimumHeight(min(420, 60 + 44 * len(updates)))
        layout.addWidget(scroll, 1)

        footer = QHBoxLayout()
        footer.setSpacing(12)
        totals = QVBoxLayout()
        totals.setSpacing(2)
        self.total = Label("", bold=True)
        totals.addWidget(self.total)
        totals.addWidget(Label(window.FreeSpaceText(), colors["muted"], scale=0.9))
        footer.addLayout(totals, 1)
        cancel = Button(QApplication.translate("app", "Cancel"))
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        self.okButton = Button()
        self.okButton.setDefault(True)
        self.okButton.clicked.connect(self.accept)
        footer.addWidget(self.okButton)
        layout.addLayout(footer)
        self.RefreshTotal()

    def Selected(self):
        return [(game, pack) for check, game, pack, _ in self.checks if check.isChecked()]

    def RefreshTotal(self):
        chosen = [c for c in self.checks if c[0].isChecked()]
        size = sum(c[3] for c in chosen)
        self.total.setText(f"{PackCount(len(chosen))} · {AssetCatalog.FormatSize(size)}")
        self.okButton.setText(
            QApplication.translate("app", "Update {0}").format(PackCount(len(chosen)))
        )
        self.okButton.setEnabled(bool(chosen))


# =====================================================
# WINDOW
# =====================================================
class AssetDownloaderWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.downloader = AssetDownloader.instance
        self.setWindowTitle(QApplication.translate("app", "Download assets"))
        # Its own window: the rest of HyperDrive stays usable while it's open
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.resize(1240, 780)
        self.setMinimumSize(960, 560)

        self.colors = Colors()
        self.catalog = {}
        self.installedGames = {}
        self.offline = True
        self.updates = []
        self.selection = {}
        self.currentGame = None
        self.filterMode = FILTER_ALL
        self.gameItems = {}
        self.gameRows = {}
        self.packRows = {}
        self.logoCache = {}

        self.BuildUi()

        self.downloader.signals.catalogChanged.connect(self.RefreshAll)
        self.downloader.signals.jobsChanged.connect(self.OnJobsChanged)
        self.downloader.signals.jobProgress.connect(self.OnJobProgress)
        GameAssetManager.instance.signals.onLoadAssets.connect(self.RefreshAll)
        self.RefreshAll()

    # =====================================================
    # LAYOUT
    # =====================================================
    def BuildUi(self):
        colors = self.colors
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Search, filters and updates
        top = QFrame()
        top.setObjectName("topBar")
        top.setStyleSheet(
            f"QFrame#topBar {{ border-bottom: 1px solid {colors['border'].name()}; }}"
        )
        topLayout = QHBoxLayout(top)
        topLayout.setContentsMargins(20, 12, 20, 12)
        topLayout.setSpacing(12)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(340)
        self.search.setAccessibleName(QApplication.translate("app", "Search games and packs"))
        self.search.textChanged.connect(self.ApplyFilter)
        topLayout.addWidget(self.search)

        self.filterGroup = QButtonGroup(self)
        self.filterGroup.setExclusive(True)
        self.filterButtons = {}
        for mode in (FILTER_ALL, FILTER_INSTALLED, FILTER_UPDATES):
            button = Button()
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, m=mode: self.SetFilter(m))
            self.filterGroup.addButton(button)
            self.filterButtons[mode] = button
            topLayout.addWidget(button)
        self.filterButtons[FILTER_ALL].setChecked(True)
        topLayout.addStretch()

        self.refreshButton = QToolButton()
        self.refreshButton.setIcon(ThemedIcon("assets/icons/undo.svg"))
        self.refreshButton.setToolTip(
            QApplication.translate("app", "Check for new packs and updates")
        )
        self.refreshButton.setAccessibleName(self.refreshButton.toolTip())
        self.refreshButton.clicked.connect(lambda: self.downloader.LoadCatalog(force=True))
        topLayout.addWidget(self.refreshButton)
        self.reviewButton = Button()
        self.reviewButton.setIcon(ThemedIcon("assets/icons/update_available.svg"))
        self.reviewButton.clicked.connect(self.ReviewUpdates)
        topLayout.addWidget(self.reviewButton)
        root.addWidget(top)

        # Loading and connection problems
        self.banner = QFrame()
        self.banner.setObjectName("banner")
        bannerLayout = QHBoxLayout(self.banner)
        bannerLayout.setContentsMargins(20, 10, 20, 10)
        bannerLayout.setSpacing(12)
        bannerText = QVBoxLayout()
        bannerText.setSpacing(2)
        self.bannerTitle = Label("", bold=True)
        bannerText.addWidget(self.bannerTitle)
        self.bannerBody = Label("", colors["muted"], wrap=True)
        bannerText.addWidget(self.bannerBody)
        bannerLayout.addLayout(bannerText, 1)
        self.retryButton = Button(QApplication.translate("app", "Try again"))
        self.retryButton.clicked.connect(lambda: self.downloader.LoadCatalog(force=True))
        bannerLayout.addWidget(self.retryButton)
        root.addWidget(self.banner)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body, 1)

        # Games
        self.gameList = QListWidget()
        self.gameList.setFixedWidth(SIDEBAR_WIDTH)
        self.gameList.setAccessibleName(QApplication.translate("app", "Games"))
        self.gameList.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.gameList.setStyleSheet(
            f"""
            QListWidget {{ background: {colors["surface"].name()}; border: none;
                border-right: 1px solid {colors["border"].name()}; border-radius: 0; outline: none; }}
            QListWidget::item {{ border-radius: {Theme.Radius()}px; margin: 1px 6px; }}
            QListWidget::item:selected {{ background: {colors["accentSoft"].name()}; }}
            QListWidget::item:hover:!selected {{ background: {colors["raised"].name()}; }}
            """
        )
        self.gameList.currentItemChanged.connect(self.OnGameChanged)
        body.addWidget(self.gameList)

        # The selected game's packs
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        body.addLayout(right, 1)

        header = QHBoxLayout()
        header.setContentsMargins(24, 18, 24, 14)
        header.setSpacing(16)
        self.headerLogo = LogoTile(112, 48, colors)
        header.addWidget(self.headerLogo)
        headerText = QVBoxLayout()
        headerText.setSpacing(4)
        self.headerTitle = Label("", scale=1.45, bold=True)
        headerText.addWidget(self.headerTitle)
        self.headerMeta = Label("", colors["muted"])
        headerText.addWidget(self.headerMeta)
        header.addLayout(headerText, 1)
        self.openFolderButton = Button(QApplication.translate("app", "Open folder"))
        self.openFolderButton.clicked.connect(lambda: self.OpenFolder(self.currentGame))
        header.addWidget(self.openFolderButton)
        self.headerWidget = QWidget()
        self.headerWidget.setLayout(header)
        right.addWidget(self.headerWidget)

        self.baseBanner = QFrame()
        self.baseBanner.setObjectName("baseBanner")
        self.baseBanner.setStyleSheet(
            f"QFrame#baseBanner {{ background: {colors['surface'].name()};"
            f"border: 1px solid {colors['border'].name()}; border-radius: {Theme.Radius() + 2}px; }}"
        )
        baseLayout = QVBoxLayout(self.baseBanner)
        baseLayout.setContentsMargins(16, 12, 16, 12)
        baseLayout.setSpacing(4)
        self.baseTitle = Label("", colors["info"], bold=True)
        baseLayout.addWidget(self.baseTitle)
        self.baseBody = Label("", colors["muted"], wrap=True)
        baseLayout.addWidget(self.baseBody)
        baseWrap = QHBoxLayout()
        baseWrap.setContentsMargins(24, 0, 24, 14)
        baseWrap.addWidget(self.baseBanner)
        right.addLayout(baseWrap)

        self.packScroll = QScrollArea()
        self.packScroll.setWidgetResizable(True)
        self.packScroll.setFrameShape(QFrame.Shape.NoFrame)
        self.packScroll.setStyleSheet(
            f"QScrollArea {{ border-top: 1px solid {colors['border'].name()}; border-radius: 0; }}"
        )
        right.addWidget(self.packScroll, 1)

        self.emptyLabel = Label("", colors["muted"], wrap=True)
        self.emptyLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(self.emptyLabel, 1)

        # What's selected, and the button to download it
        selectionBar = QFrame()
        selectionBar.setObjectName("selectionBar")
        selectionBar.setStyleSheet(
            f"QFrame#selectionBar {{ background: {colors['surface'].name()};"
            f"border-top: 1px solid {colors['border'].name()}; }}"
        )
        barLayout = QHBoxLayout(selectionBar)
        barLayout.setContentsMargins(24, 12, 24, 12)
        barLayout.setSpacing(12)
        barText = QVBoxLayout()
        barText.setSpacing(2)
        self.selectionLabel = Label("", bold=True)
        barText.addWidget(self.selectionLabel)
        self.freeLabel = Label("", colors["muted"], scale=0.9)
        barText.addWidget(self.freeLabel)
        barLayout.addLayout(barText, 1)
        self.clearButton = Button(QApplication.translate("app", "Clear"))
        self.clearButton.clicked.connect(self.ClearSelection)
        barLayout.addWidget(self.clearButton)
        self.downloadButton = QPushButton()
        self.downloadButton.setAutoDefault(True)
        self.downloadButton.setIcon(ThemedIcon("assets/icons/download.svg"))
        self.downloadButton.setDefault(True)
        self.downloadButton.clicked.connect(self.DownloadSelected)
        barLayout.addWidget(self.downloadButton)
        right.addWidget(selectionBar)

        self.downloadsPanel = DownloadsPanel(self)
        root.addWidget(self.downloadsPanel)

    def Open(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.search.setFocus()

    # =====================================================
    # DATA
    # =====================================================
    def RefreshAll(self):
        try:
            self.installedGames = GameAssetManager.instance.games
            self.offline = self.downloader.catalog is None
            self.catalog = (
                InstalledCatalog(self.installedGames) if self.offline else self.downloader.catalog
            )
            self.updates = [] if self.offline else self.downloader.Updates()
            # Packs that got installed or can't be picked any more leave the selection
            for game in list(self.selection):
                self.selection[game] = {
                    p
                    for p in self.selection[game]
                    if game in self.catalog
                    and p in self.catalog[game]["assets"]
                    and AssetCatalog.PackState(self.catalog, self.installedGames, game, p)
                    != STATE_INSTALLED
                }
            self.RefreshBanner()
            self.RebuildGameList()
            self.RefreshFilterButtons()
            self.ApplyFilter()
            self.RefreshSelectionBar()
        except Exception:
            logger.error(traceback.format_exc())

    def PackState(self, game, pack):
        if self.downloader.JustInstalled(game, pack):
            return STATE_INSTALLED
        return AssetCatalog.PackState(self.catalog, self.installedGames, game, pack)

    def IsInstalledGame(self, game):
        return bool(AssetCatalog.InstalledPacks(self.catalog, self.installedGames, game))

    def GameUpdates(self, game):
        return [p for g, p in self.updates if g == game]

    def IsAutoBase(self, game, pack):
        """Base files the game needs for the packs picked for it."""
        return (
            not self.offline
            and pack == BASE_FILES
            and BASE_FILES in self.catalog.get(game, {}).get("assets", {})
            and not AssetCatalog.HasBaseFiles(self.installedGames, game)
            and not self.downloader.JustInstalled(game, BASE_FILES)
            and bool(self.selection.get(game))
            and self.downloader.ActiveJob(game, BASE_FILES) is None
        )

    def SelectedPacks(self):
        """[(game, pack)] to download, with the base files games need."""
        packs = []
        for game, chosen in self.selection.items():
            if chosen and self.IsAutoBase(game, BASE_FILES) and BASE_FILES not in chosen:
                packs.append((game, BASE_FILES))
            packs += [(game, p) for p in AssetCatalog.Packs(self.catalog, game) if p in chosen]
        return packs

    def GameLogo(self, game, width, height):
        key = (game, width, height)
        if key in self.logoCache:
            return self.logoCache[key]
        installed = self.installedGames.get(game, {}).get("logo_path")
        source = installed or self.downloader.logos.get(game)
        logo = Logo(source, width, height)
        if logo is not None:
            self.logoCache[key] = logo
        return logo

    def FreeSpaceText(self):
        try:
            return QApplication.translate("app", "{0} free").format(
                AssetCatalog.FormatSize(AssetCatalog.FreeSpace())
            )
        except OSError:
            return ""

    # =====================================================
    # BANNER AND FILTERS
    # =====================================================
    def RefreshBanner(self):
        colors = self.colors
        downloader = self.downloader
        if downloader.catalog is None and downloader.catalogLoading:
            title = QApplication.translate("app", "Loading the pack list…")
            body = ""
            color = colors["info"]
        elif downloader.catalog is None and downloader.catalogError:
            title = QApplication.translate("app", "Can't reach the asset server")
            body = QApplication.translate(
                "app",
                "Showing the packs you already have. New packs and updates need a connection.",
            )
            color = colors["warn"]
        elif downloader.catalogError:
            title = QApplication.translate("app", "Couldn't check for new packs")
            body = QApplication.translate("app", "Showing the list from earlier.")
            color = colors["warn"]
        else:
            self.banner.hide()
            return

        self.bannerTitle.setText(title)
        self.bannerBody.setText(body)
        self.bannerBody.setVisible(bool(body))
        self.banner.setToolTip(downloader.catalogError or "")
        self.retryButton.setVisible(not downloader.catalogLoading)
        self.banner.setStyleSheet(
            f"QFrame#banner {{ background: {colors['surface'].name()};"
            f"border-bottom: 2px solid {color.name()}; }}"
        )
        self.bannerTitle.setStyleSheet(f"color: {color.name()};")
        self.banner.show()

    def RefreshFilterButtons(self):
        counts = {
            FILTER_ALL: len(self.catalog),
            FILTER_INSTALLED: sum(1 for g in self.catalog if self.IsInstalledGame(g)),
            FILTER_UPDATES: len({g for g, _ in self.updates}),
        }
        names = {
            FILTER_ALL: QApplication.translate("app", "All games"),
            FILTER_INSTALLED: QApplication.translate("app", "Installed"),
            FILTER_UPDATES: QApplication.translate("app", "Updates"),
        }
        for mode, button in self.filterButtons.items():
            button.setText(f"{names[mode]}  {counts[mode]}")
        self.filterButtons[FILTER_UPDATES].setVisible(not self.offline)
        if self.offline and self.filterMode == FILTER_UPDATES:
            self.filterMode = FILTER_ALL
            self.filterButtons[FILTER_ALL].setChecked(True)
        self.search.setPlaceholderText(
            QApplication.translate("app", "Search {0} games and their packs").format(
                len(self.catalog)
            )
        )
        self.reviewButton.setText(
            QApplication.translate("app", "Review {0} updates").format(len(self.updates))
            if len(self.updates) != 1
            else QApplication.translate("app", "Review 1 update")
        )
        self.reviewButton.setVisible(bool(self.updates))
        self.refreshButton.setEnabled(not self.downloader.catalogLoading)

    def SetFilter(self, mode):
        self.filterMode = mode
        self.ApplyFilter()

    # =====================================================
    # GAME LIST
    # =====================================================
    def RebuildGameList(self):
        current = self.currentGame
        self.gameList.blockSignals(True)
        self.gameList.clear()
        self.gameItems = {}
        self.gameRows = {}
        colors = self.colors

        names = {g: str(self.catalog[g].get("name", g)) for g in self.catalog}
        ordered = sorted(self.catalog, key=lambda g: names[g].casefold())
        installed = [g for g in ordered if self.IsInstalledGame(g)]
        others = [g for g in ordered if g not in installed]

        self.sectionItems = []
        for title, games in (
            (QApplication.translate("app", "INSTALLED"), installed),
            (QApplication.translate("app", "MORE GAMES"), others),
        ):
            if not games:
                continue
            header = QListWidgetItem(title)
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            font = header.font()
            font.setBold(True)
            font.setPointSizeF(font.pointSizeF() * 0.85)
            header.setFont(font)
            header.setForeground(colors["muted"])
            header.setSizeHint(QSize(0, 34))
            header.setData(Qt.ItemDataRole.UserRole + 1, games)
            self.gameList.addItem(header)
            self.sectionItems.append(header)

            for game in games:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, game)
                item.setSizeHint(QSize(0, 56))
                row = GameRow(names[game], colors)
                self.RefreshGameRow(game, row)
                self.gameList.addItem(item)
                self.gameList.setItemWidget(item, row)
                self.gameItems[game] = item
                self.gameRows[game] = row

                logo = self.GameLogo(game, LOGO_WIDTH - 8, LOGO_HEIGHT - 8)
                if logo is not None:
                    row.SetLogo(logo)
                elif not self.offline:
                    self.downloader.RequestLogo(game, self.OnLogoLoaded)

        self.currentGame = current
        self.gameList.blockSignals(False)

    def RefreshGameRow(self, game, row):
        packs = AssetCatalog.Packs(self.catalog, game)
        if self.offline:
            row.SetInfo(
                QApplication.translate("app", "{0} installed").format(PackCount(len(packs)))
            )
        elif self.IsInstalledGame(game):
            installed = len(AssetCatalog.InstalledPacks(self.catalog, self.installedGames, game))
            updates = len(self.GameUpdates(game))
            badge = ""
            if updates == 1:
                badge = QApplication.translate("app", "1 update")
            elif updates > 1:
                badge = QApplication.translate("app", "{0} updates").format(updates)
            row.SetInfo(
                QApplication.translate("app", "{0} of {1} installed").format(
                    installed, PackCount(len(packs))
                ),
                badge,
            )
        else:
            size = sum(AssetCatalog.PackSize(self.catalog, game, p) for p in packs)
            row.SetInfo(f"{PackCount(len(packs))} · {AssetCatalog.FormatSize(size)}")

    def OnLogoLoaded(self, game, data):
        if data is None:
            return
        for key in [k for k in self.logoCache if k[0] == game]:
            del self.logoCache[key]
        row = self.gameRows.get(game)
        if row is not None:
            row.SetLogo(self.GameLogo(game, LOGO_WIDTH - 8, LOGO_HEIGHT - 8))
        if game == self.currentGame:
            self.headerLogo.setPixmap(self.GameLogo(game, 96, 36) or QPixmap())

    def GameVisible(self, game):
        if self.filterMode == FILTER_INSTALLED and not self.IsInstalledGame(game):
            return False
        if self.filterMode == FILTER_UPDATES and not self.GameUpdates(game):
            return False
        return bool(AssetCatalog.MatchingPacks(self.catalog, game, self.search.text()))

    def ApplyFilter(self):
        firstVisible = None
        for game, item in self.gameItems.items():
            visible = self.GameVisible(game)
            item.setHidden(not visible)
        for header in self.sectionItems:
            games = header.data(Qt.ItemDataRole.UserRole + 1)
            header.setHidden(not any(not self.gameItems[g].isHidden() for g in games))

        for i in range(self.gameList.count()):
            item = self.gameList.item(i)
            game = item.data(Qt.ItemDataRole.UserRole)
            if game and not item.isHidden():
                firstVisible = game
                break

        game = self.currentGame
        if game is None or game not in self.gameItems or self.gameItems[game].isHidden():
            game = firstVisible
        self.SelectGame(game)

    def SelectGame(self, game):
        self.gameList.blockSignals(True)
        self.gameList.setCurrentItem(self.gameItems.get(game))
        self.gameList.blockSignals(False)
        self.ShowGame(game)

    def OnGameChanged(self, current, previous):
        game = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        if game:
            self.ShowGame(game)

    # =====================================================
    # PACKS
    # =====================================================
    def ShowGame(self, game):
        self.currentGame = game
        old = self.packScroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self.packRows = {}

        if game is None:
            self.headerWidget.hide()
            self.baseBanner.hide()
            self.packScroll.hide()
            if self.downloader.catalog is None and self.downloader.catalogLoading:
                self.emptyLabel.setText(QApplication.translate("app", "Loading the pack list…"))
            elif self.search.text().strip():
                self.emptyLabel.setText(
                    QApplication.translate("app", "No games or packs match “{0}”.").format(
                        self.search.text().strip()
                    )
                )
            elif self.offline:
                self.emptyLabel.setText(
                    QApplication.translate(
                        "app", "No packs installed yet. Connect to download some."
                    )
                )
            else:
                self.emptyLabel.setText(QApplication.translate("app", "Nothing to show here."))
            self.emptyLabel.show()
            return

        self.emptyLabel.hide()
        self.headerWidget.show()
        self.packScroll.show()
        info = self.catalog[game]
        self.headerTitle.setText(str(info.get("name", game)))
        self.headerLogo.setPixmap(self.GameLogo(game, 96, 36) or QPixmap())
        self.openFolderButton.setEnabled(os.path.isdir(os.path.join(AssetCatalog.GAMES_DIR, game)))
        self.RefreshHeaderMeta()

        needsBase = (
            not self.offline
            and BASE_FILES in info["assets"]
            and not AssetCatalog.HasBaseFiles(self.installedGames, game)
        )
        self.baseBanner.setVisible(needsBase)
        if needsBase:
            self.baseTitle.setText(
                QApplication.translate("app", "{0} needs its base files first").format(
                    info.get("name", game)
                )
            )
            self.baseBody.setText(
                QApplication.translate(
                    "app",
                    "They hold the game's characters and stages ({0}). They're added for you when you pick any pack.",
                ).format(
                    AssetCatalog.FormatSize(AssetCatalog.PackSize(self.catalog, game, BASE_FILES))
                )
            )

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)
        for pack in AssetCatalog.MatchingPacks(self.catalog, game, self.search.text()):
            row = PackRow(self, game, pack)
            self.packRows[pack] = row
            layout.addWidget(row)
        layout.addStretch()
        self.packScroll.setWidget(content)

    def RefreshHeaderMeta(self):
        game = self.currentGame
        if game is None:
            return
        packs = AssetCatalog.Packs(self.catalog, game)
        if self.offline:
            text = QApplication.translate("app", "{0} installed").format(PackCount(len(packs)))
        else:
            installed = len(AssetCatalog.InstalledPacks(self.catalog, self.installedGames, game))
            text = QApplication.translate("app", "{0} · {1} installed").format(
                PackCount(len(packs)), installed
            )
        self.headerMeta.setText(text)

    def RefreshPackRows(self):
        for row in self.packRows.values():
            row.Refresh()

    def SetSelected(self, game, pack, selected):
        chosen = self.selection.setdefault(game, set())
        if selected:
            chosen.add(pack)
        else:
            chosen.discard(pack)
        if game == self.currentGame:
            self.RefreshPackRows()
        self.RefreshSelectionBar()

    def ClearSelection(self):
        self.selection = {}
        self.RefreshPackRows()
        self.RefreshSelectionBar()

    def RefreshSelectionBar(self):
        packs = self.SelectedPacks()
        chosen = sum(len(s) for s in self.selection.values())
        withBase = any(p == BASE_FILES and p not in self.selection.get(g, set()) for g, p in packs)
        size = sum(AssetCatalog.PackSize(self.catalog, g, p) for g, p in packs)

        if self.offline:
            self.selectionLabel.setText(
                QApplication.translate("app", "Downloads need a connection")
            )
        elif chosen == 0:
            self.selectionLabel.setText(QApplication.translate("app", "Pick the packs to download"))
        else:
            text = (
                QApplication.translate("app", "1 pack selected")
                if chosen == 1
                else QApplication.translate("app", "{0} packs selected").format(chosen)
            )
            if withBase:
                text += " " + QApplication.translate("app", "+ base files")
            self.selectionLabel.setText(f"{text} · {AssetCatalog.FormatSize(size)}")
        self.freeLabel.setText(self.FreeSpaceText())
        self.clearButton.setVisible(chosen > 0)
        self.downloadButton.setEnabled(not self.offline and chosen > 0)
        self.downloadButton.setText(
            QApplication.translate("app", "Download {0}").format(PackCount(chosen))
            if chosen
            else QApplication.translate("app", "Download")
        )

    # =====================================================
    # ACTIONS
    # =====================================================
    def DownloadSelected(self):
        packs = self.SelectedPacks()
        if not packs:
            return
        self.selection = {}
        self.downloader.Enqueue(packs)
        self.RefreshSelectionBar()

    def ReviewUpdates(self):
        if not self.updates:
            return
        dialog = UpdatesDialog(self, self.updates)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.Selected():
            self.downloader.Enqueue(dialog.Selected())

    def OpenFolder(self, game, pack=None):
        if game is None:
            return
        path = os.path.join(AssetCatalog.GAMES_DIR, game)
        if pack is not None:
            path = AssetCatalog.PackPath(game, pack)
        if os.path.isdir(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(path)))

    def ConfirmRemove(self, game, pack):
        info = self.catalog[game]
        name = PackName(self.catalog, game, pack)
        answer = QMessageBox.question(
            self,
            QApplication.translate("app", "Remove pack"),
            QApplication.translate(
                "app", "Remove {0} from {1}? You can download it again at any time."
            ).format(name, info.get("name", game)),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.downloader.RemovePack(game, pack)
        except Exception as e:
            logger.error(traceback.format_exc())
            QMessageBox.warning(
                self,
                QApplication.translate("app", "Remove pack"),
                QApplication.translate("app", "Couldn't remove {0}:").format(name) + f"\n{e}",
            )

    # =====================================================
    # DOWNLOADS
    # =====================================================
    def OnJobsChanged(self):
        self.RefreshPackRows()
        self.RefreshSelectionBar()

    def OnJobProgress(self, job):
        if job.game == self.currentGame:
            row = self.packRows.get(job.pack)
            if row is not None:
                row.RefreshJob(job)
