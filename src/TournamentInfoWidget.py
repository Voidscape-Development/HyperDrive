# The Tournament Info tab: what the layouts show about the event itself
# (tournamentInfo.* in the program state). It's filled in from the loaded
# tournament and anything can be changed afterwards: a field changed since
# says so, with a button to go back to the tournament's value.
import os
import shutil
import time
import traceback

import requests
from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtNetwork import QNetworkAccessManager, QNetworkRequest
from qtpy.QtWidgets import *

from .Helpers.LocaleHelper import LocaleHelper
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .Theme import Blend, Theme, ThemedIcon
from .TournamentDataManager import TournamentDataManager

LOGO_PATH = "./layout/logo.png"

# The fields, by their key in tournamentInfo (also their widget's object name,
# which the web dashboard finds them by)
TEXT_FIELDS = ["tournamentName", "eventName", "address", "cityState", "shortLink"]
DATE_FIELDS = ["startAt", "endAt"]
NUMBER_FIELDS = ["numEntrants"]

# What the "Sent to layouts" list shows, in order
SUMMARY_KEYS = [
    "tournamentName",
    "eventName",
    "startAt",
    "endAt",
    "numEntrants",
    "address",
    "cityState",
    "shortLink",
    "logo",
    "banner",
]

PROVIDER_NAMES = {"StartGG": "start.gg", "ParryGG": "parry.gg"}

# Below this width, the side column goes under the form
NARROW_WIDTH = 820


class ElidedLabel(QLabel):
    """A one-line label that ends in "…" when it's too narrow for its text."""

    def __init__(self, text=""):
        super().__init__(text)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.contentsRect()
        text = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, rect.width())
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        painter.drawText(rect, int(self.alignment()), text)


class LogoTile(QLabel):
    """The tournament logo, which takes an image file dropped on it."""

    fileDropped = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("logoTile")
        self.setAcceptDrops(True)
        self.setFixedSize(112, 112)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _ImagePath(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and os.path.splitext(path)[1].lower() in (".png", ".jpg", ".jpeg", ".bmp"):
                return path
        return None

    def _SetDragging(self, dragging):
        self.setProperty("dragging", dragging)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event):
        if self._ImagePath(event):
            event.acceptProposedAction()
            self._SetDragging(True)

    def dragLeaveEvent(self, event):
        self._SetDragging(False)

    def dropEvent(self, event):
        self._SetDragging(False)
        path = self._ImagePath(event)
        if path:
            event.acceptProposedAction()
            self.fileDropped.emit(path)


class TournamentInfoWidget(QDockWidget):
    def __init__(self, *args):
        super().__init__(*args)

        self.setWindowTitle(QApplication.translate("app", "Tournament Info"))

        # The values the last load from the tournament gave each field, to
        # tell which ones were changed since
        self.loaded = {}
        self.loadedAt = None
        self.bannerPixmap = None
        self.ready = False

        self.network = QNetworkAccessManager(self)
        self.bannerReply = None

        self.contents = QWidget()
        outer = QVBoxLayout(self.contents)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.setWidget(self.contents)

        outer.addWidget(self.BuildHeader())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, 1)

        body = QWidget()
        self.bodyLayout = QBoxLayout(QBoxLayout.Direction.LeftToRight, body)
        self.bodyLayout.setContentsMargins(16, 14, 16, 14)
        self.bodyLayout.setSpacing(14)
        scroll.setWidget(body)

        form = QVBoxLayout()
        form.setSpacing(12)
        form.addWidget(self.BuildIdentityCard())
        form.addWidget(self.BuildDetailsCard())
        form.addWidget(self.BuildBannerCard())
        form.addStretch(1)
        self.bodyLayout.addLayout(form, 1)

        self.rail = QWidget()
        rail = QVBoxLayout(self.rail)
        rail.setContentsMargins(0, 0, 0, 0)
        rail.setSpacing(12)
        rail.addWidget(self.BuildPreviewCard())
        rail.addWidget(self.BuildSummaryCard())
        rail.addStretch(1)
        self.bodyLayout.addWidget(self.rail)

        self.ConnectFields()

        TournamentDataManager.instance.signals.tournament_data_updated.connect(self.UpdateData)
        TournamentDataManager.instance.signals.tournament_changed.connect(self.UpdateHeader)

        self.ready = True
        self.ApplyStyle()
        self.UpdateIcon()
        self.UpdateBanner()
        self.UpdateEdited()

    # =====================================================
    # BUILDING
    # =====================================================
    def Card(self, title, note=None):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(title)
        label.setObjectName("cardTitle")
        row.addWidget(label)
        if note:
            noteLabel = QLabel(note)
            noteLabel.setObjectName("muted")
            row.addWidget(noteLabel)
        row.addStretch(1)
        layout.addLayout(row)
        return card, layout, row

    def Field(self, label, keys, widget):
        """A field's label, its "Edited" badge and revert button, over
        widget (a widget or a layout). keys are the fields it shows."""
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        row = QHBoxLayout()
        row.setSpacing(8)
        title = QLabel(label)
        title.setObjectName("fieldLabel")
        row.addWidget(title)
        badge = QLabel(QApplication.translate("app", "Edited"))
        badge.setObjectName("editedBadge")
        badge.setContentsMargins(6, 1, 6, 1)
        badge.setVisible(False)
        row.addWidget(badge)
        row.addStretch(1)
        revert = QToolButton()
        revert.setObjectName("linkButton")
        revert.setText(QApplication.translate("app", "Revert"))
        revert.setCursor(Qt.CursorShape.PointingHandCursor)
        revert.setVisible(False)
        revert.clicked.connect(lambda: self.Revert(keys))
        row.addWidget(revert)
        layout.addLayout(row)

        if isinstance(widget, QLayout):
            layout.addLayout(widget)
        else:
            layout.addWidget(widget)
            title.setBuddy(widget)

        self.blocks.append((keys, badge, revert))
        return block

    def BuildHeader(self):
        header = QFrame()
        header.setObjectName("header")
        row = QHBoxLayout(header)
        row.setContentsMargins(16, 10, 16, 10)
        row.setSpacing(12)

        self.statusDot = QLabel()
        self.statusDot.setObjectName("statusDot")
        self.statusDot.setFixedSize(8, 8)
        row.addWidget(self.statusDot)

        text = QVBoxLayout()
        text.setSpacing(1)
        self.headerTitle = QLabel()
        self.headerTitle.setObjectName("cardTitle")
        text.addWidget(self.headerTitle)
        self.headerDetail = QLabel()
        self.headerDetail.setObjectName("muted")
        self.headerDetail.setTextFormat(Qt.TextFormat.RichText)
        self.headerDetail.setMinimumWidth(0)
        self.headerDetail.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text.addWidget(self.headerDetail)
        row.addLayout(text, 1)

        self.btClearInfo = QPushButton(QApplication.translate("app", "Clear all"))
        self.btClearInfo.setObjectName("btClearInfo")
        self.btClearInfo.setToolTip(
            QApplication.translate("app", "Empty every field, including the tournament's images")
        )
        self.btClearInfo.clicked.connect(lambda: [self.UpdateData({})])
        row.addWidget(self.btClearInfo)

        self.btLoadInfoFromTournament = QPushButton()
        self.btLoadInfoFromTournament.setObjectName("btLoadInfoFromTournament")
        self.btLoadInfoFromTournament.setIcon(ThemedIcon("assets/icons/refresh.svg"))
        self.btLoadInfoFromTournament.setDefault(True)
        self.btLoadInfoFromTournament.setAutoDefault(False)
        self.btLoadInfoFromTournament.setToolTip(
            QApplication.translate(
                "app", "Fill every field in from the tournament again, replacing your changes"
            )
        )
        self.btLoadInfoFromTournament.clicked.connect(
            lambda: [TournamentDataManager.instance.GetTournamentData()]
        )
        row.addWidget(self.btLoadInfoFromTournament)
        return header

    def BuildIdentityCard(self):
        self.blocks = []
        self.fields = {}

        card, layout, _ = self.Card(QApplication.translate("app", "Identity"))
        row = QHBoxLayout()
        row.setSpacing(18)
        layout.addLayout(row)

        logo = QVBoxLayout()
        logo.setSpacing(8)
        self.iconView = LogoTile()
        self.iconView.setToolTip(
            QApplication.translate(
                "app", "The tournament's logo. Drop an image here to use it instead."
            )
        )
        self.iconView.fileDropped.connect(self.LoadIconFile)
        logo.addWidget(self.iconView, 0, Qt.AlignmentFlag.AlignHCenter)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        for name, icon, tip, slot in [
            (
                "btLoadIconFile",
                "upload.svg",
                QApplication.translate("app", "Load local file"),
                self.LoadIcon,
            ),
            (
                "btDownloadIcon",
                "download.svg",
                QApplication.translate("app", "Download tournament icon"),
                self.DownloadIcon,
            ),
            (
                "btClearIcon",
                "undo.svg",
                QApplication.translate("app", "Go back to the default icon"),
                self.SetDefaultIcon,
            ),
        ]:
            button = QToolButton()
            button.setObjectName(name)
            button.setIcon(ThemedIcon(f"assets/icons/{icon}"))
            button.setIconSize(QSize(16, 16))
            button.setToolTip(tip)
            button.setAccessibleName(tip)
            button.clicked.connect(lambda checked=False, slot=slot: slot())
            buttons.addWidget(button)
            setattr(self, name, button)
        logo.addLayout(buttons)
        hint = QLabel(QApplication.translate("app", "Drop an image here"))
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        logo.addWidget(hint)
        logo.addStretch(1)
        row.addLayout(logo)

        names = QVBoxLayout()
        names.setSpacing(12)
        tournamentName = self.TextField("tournamentName")
        font = tournamentName.font()
        font.setPointSizeF(font.pointSizeF() * 1.25)
        font.setBold(True)
        tournamentName.setFont(font)
        names.addWidget(
            self.Field(
                QApplication.translate("app", "Tournament Name"),
                ["tournamentName"],
                tournamentName,
            )
        )
        names.addWidget(
            self.Field(
                QApplication.translate("app", "Event Name"),
                ["eventName"],
                self.TextField("eventName"),
            )
        )
        names.addStretch(1)
        row.addLayout(names, 1)
        return card

    def BuildDetailsCard(self):
        card, layout, _ = self.Card(QApplication.translate("app", "Details"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        layout.addLayout(grid)

        dates = QHBoxLayout()
        dates.setSpacing(8)
        dates.addWidget(self.DateField("startAt"), 1)
        to = QLabel(QApplication.translate("app", "to"))
        to.setObjectName("muted")
        dates.addWidget(to)
        dates.addWidget(self.DateField("endAt"), 1)
        grid.addWidget(self.Field(QApplication.translate("app", "Dates"), DATE_FIELDS, dates), 0, 0)

        entrants = QSpinBox()
        entrants.setObjectName("numEntrants")
        entrants.setMaximum(99999)
        entrants.setAccessibleName(QApplication.translate("app", "Entrant Number"))
        self.fields["numEntrants"] = entrants
        grid.addWidget(
            self.Field(QApplication.translate("app", "Entrants"), ["numEntrants"], entrants),
            0,
            1,
        )

        address = self.TextField("address")
        address.addAction(
            ThemedIcon("assets/icons/location.svg"), QLineEdit.ActionPosition.LeadingPosition
        )
        grid.addWidget(
            self.Field(QApplication.translate("app", "Location"), ["address"], address),
            1,
            0,
        )

        # For layouts that don't show the whole address
        cityState = self.TextField("cityState")
        cityState.setPlaceholderText(QApplication.translate("app", "e.g. Springfield, IL"))
        cityState.setToolTip(
            QApplication.translate(
                "app", "The venue's city and state, for layouts that don't show the whole address"
            )
        )
        grid.addWidget(
            self.Field(QApplication.translate("app", "City, State"), ["cityState"], cityState),
            1,
            1,
        )

        shortLink = self.TextField("shortLink")
        copy = shortLink.addAction(
            ThemedIcon("assets/icons/copy.svg"), QLineEdit.ActionPosition.TrailingPosition
        )
        copy.setToolTip(QApplication.translate("app", "Copy"))
        copy.triggered.connect(lambda: QApplication.clipboard().setText(shortLink.text()))
        grid.addWidget(
            self.Field(QApplication.translate("app", "Short Link"), ["shortLink"], shortLink),
            2,
            0,
            1,
            2,
        )
        return card

    def BuildBannerCard(self):
        card, layout, title = self.Card(
            QApplication.translate("app", "Banner"),
            QApplication.translate("app", "from the tournament, for layouts that show one"),
        )
        self.btRestoreBanner = QToolButton()
        self.btRestoreBanner.setObjectName("linkButton")
        self.btRestoreBanner.setText(QApplication.translate("app", "Restore"))
        self.btRestoreBanner.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btRestoreBanner.clicked.connect(lambda: self.SetBanner(self.loaded.get("banner", "")))
        title.addWidget(self.btRestoreBanner)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.bannerView = QLabel()
        self.bannerView.setObjectName("bannerView")
        self.bannerView.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bannerView.setFixedHeight(96)
        self.bannerView.setMinimumWidth(120)
        self.bannerView.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        row.addWidget(self.bannerView, 1)
        self.btRemoveBanner = QToolButton()
        self.btRemoveBanner.setIcon(ThemedIcon("assets/icons/cancel.svg"))
        self.btRemoveBanner.setIconSize(QSize(16, 16))
        self.btRemoveBanner.setToolTip(QApplication.translate("app", "Remove the banner"))
        self.btRemoveBanner.setAccessibleName(self.btRemoveBanner.toolTip())
        self.btRemoveBanner.clicked.connect(lambda: self.SetBanner(""))
        row.addWidget(self.btRemoveBanner, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(row)
        return card

    def BuildPreviewCard(self):
        card, layout, _ = self.Card(QApplication.translate("app", "On stream"))
        self.preview = QFrame()
        self.preview.setObjectName("preview")
        self.preview.setFixedHeight(124)
        preview = QVBoxLayout(self.preview)
        preview.setContentsMargins(10, 10, 10, 10)

        self.previewLink = QLabel()
        self.previewLink.setObjectName("chip")
        self.previewLink.setContentsMargins(6, 1, 6, 1)
        preview.addWidget(self.previewLink, 0, Qt.AlignmentFlag.AlignRight)
        preview.addStretch(1)

        lowerThird = QFrame()
        lowerThird.setObjectName("lowerThird")
        third = QHBoxLayout(lowerThird)
        third.setContentsMargins(8, 6, 8, 6)
        third.setSpacing(8)
        self.previewLogo = QLabel()
        self.previewLogo.setFixedSize(30, 30)
        third.addWidget(self.previewLogo)
        lines = QVBoxLayout()
        lines.setSpacing(0)
        self.previewName = ElidedLabel()
        font = self.previewName.font()
        font.setBold(True)
        self.previewName.setFont(font)
        lines.addWidget(self.previewName)
        self.previewDetail = ElidedLabel()
        self.previewDetail.setObjectName("muted")
        lines.addWidget(self.previewDetail)
        third.addLayout(lines, 1)
        preview.addWidget(lowerThird)
        layout.addWidget(self.preview)

        note = QLabel(
            QApplication.translate("app", "A rough idea of how layouts use these fields.")
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        return card

    def BuildSummaryCard(self):
        card, layout, _ = self.Card(
            QApplication.translate("app", "Sent to layouts"), "tournamentInfo.*"
        )
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        self.summaryValues = {}
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        for i, key in enumerate(SUMMARY_KEYS):
            name = QLabel(key)
            name.setObjectName("muted")
            name.setFont(mono)
            grid.addWidget(name, i, 0)
            value = ElidedLabel()
            value.setFont(mono)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(value, i, 1)
            self.summaryValues[key] = value
        layout.addLayout(grid)
        return card

    def TextField(self, key):
        field = QLineEdit()
        field.setObjectName(key)
        self.fields[key] = field
        return field

    def DateField(self, key):
        field = QDateEdit()
        field.setObjectName(key)
        field.setCalendarPopup(True)
        field.setMinimumDate(QDate(2000, 1, 1))
        self.fields[key] = field
        return field

    def ConnectFields(self):
        for key in DATE_FIELDS:
            self.fields[key].dateChanged.connect(
                lambda value, key=key: [
                    StateManager.Set(
                        f"tournamentInfo.{key}",
                        value.toString(
                            QLocale(LocaleHelper.exportLocale).dateFormat(
                                QLocale.FormatType.ShortFormat
                            )
                        ),
                    ),
                    self.FieldChanged(),
                ]
            )

        for key in TEXT_FIELDS:
            field = self.fields[key]
            field.editingFinished.connect(
                lambda key=key, field=field: [
                    StateManager.Set(f"tournamentInfo.{key}", field.text()),
                    self.RefreshSummary(),
                ]
            )
            field.textChanged.connect(lambda _: self.UpdateEdited())
            field.editingFinished.emit()

        for key in NUMBER_FIELDS:
            self.fields[key].valueChanged.connect(
                lambda value, key=key: [
                    StateManager.Set(f"tournamentInfo.{key}", value),
                    self.FieldChanged(),
                ]
            )

    # =====================================================
    # CHANGES SINCE THE LAST LOAD
    # =====================================================
    def FieldValue(self, key):
        field = self.fields[key]
        if isinstance(field, QDateEdit):
            return field.date()
        if isinstance(field, QSpinBox):
            return field.value()
        return field.text()

    def IsEdited(self, key):
        return key in self.loaded and self.FieldValue(key) != self.loaded[key]

    def BannerRemoved(self):
        return bool(self.loaded.get("banner")) and not StateManager.Get("tournamentInfo.banner")

    def EditedCount(self):
        return sum(1 for key in self.fields if self.IsEdited(key)) + int(self.BannerRemoved())

    def LoadedText(self, key):
        value = self.loaded.get(key)
        if isinstance(value, QDate):
            return QLocale().toString(value, QLocale.FormatType.ShortFormat)
        return str(value)

    def Revert(self, keys):
        for key in keys:
            if key not in self.loaded:
                continue
            field = self.fields[key]
            if isinstance(field, QDateEdit):
                field.setDate(self.loaded[key])
            elif isinstance(field, QSpinBox):
                field.setValue(self.loaded[key])
            else:
                field.setText(self.loaded[key])
                field.editingFinished.emit()

    def FieldChanged(self):
        self.UpdateEdited()
        self.RefreshSummary()

    def UpdateEdited(self):
        if not self.ready:
            return
        for keys, badge, revert in self.blocks:
            edited = [key for key in keys if self.IsEdited(key)]
            badge.setVisible(bool(edited))
            revert.setVisible(bool(edited))
            if edited:
                revert.setToolTip(
                    QApplication.translate("app", "Go back to the tournament's value: {0}").format(
                        ", ".join(self.LoadedText(key) for key in edited)
                    )
                )
            for key in keys:
                field = self.fields[key]
                if field.property("edited") != (key in edited):
                    field.setProperty("edited", key in edited)
                    field.style().unpolish(field)
                    field.style().polish(field)
        self.btRestoreBanner.setVisible(self.BannerRemoved())
        self.UpdateHeader()

    # =====================================================
    # HEADER
    # =====================================================
    def UpdateHeader(self):
        if not self.ready:
            return
        provider = TournamentDataManager.instance.provider
        source = PROVIDER_NAMES.get(getattr(provider, "name", ""), "") if provider else ""

        if source:
            self.btLoadInfoFromTournament.setText(
                QApplication.translate("app", "Load from {0}").format(source)
            )
        else:
            self.btLoadInfoFromTournament.setText(
                QApplication.translate("app", "Load from tournament")
            )
        self.btLoadInfoFromTournament.setEnabled(provider is not None)
        self.btDownloadIcon.setEnabled(provider is not None)

        if provider is None:
            title = QApplication.translate("app", "No tournament loaded")
            parts = [
                QApplication.translate(
                    "app", "Fill these in by hand, or load a tournament to fill them in."
                )
            ]
        elif self.loadedAt is None:
            title = QApplication.translate("app", "Not loaded from the tournament")
            parts = [
                QApplication.translate("app", "{0} fills these in from the tournament.").format(
                    self.btLoadInfoFromTournament.text()
                )
            ]
        else:
            title = (
                QApplication.translate("app", "Loaded from {0}").format(source)
                if source
                else QApplication.translate("app", "Loaded from the tournament")
            )
            parts = [
                str(getattr(provider, "url", "") or "").replace("https://", ""),
                QApplication.translate("app", "at {0}").format(
                    QLocale().toString(self.loadedAt, QLocale.FormatType.ShortFormat)
                ),
            ]

        self.statusDot.setProperty("status", "ok" if provider is not None and self.loadedAt else "")
        self.statusDot.style().unpolish(self.statusDot)
        self.statusDot.style().polish(self.statusDot)

        detail = " · ".join(p.replace("&", "&amp;").replace("<", "&lt;") for p in parts if p)
        edited = self.EditedCount()
        if edited:
            accent = Theme.Colors()["accentText"].name()
            text = (
                QApplication.translate("app", "1 field changed by you")
                if edited == 1
                else QApplication.translate("app", "{0} fields changed by you").format(edited)
            )
            detail += f" · <span style='color: {accent}'>{text}</span>"
        self.headerTitle.setText(title)
        self.headerDetail.setText(detail)

    # =====================================================
    # SIDE COLUMN
    # =====================================================
    def RefreshSummary(self):
        if not self.ready:
            return
        colors = Theme.Colors()
        edited = {key for key in self.fields if self.IsEdited(key)}
        if self.BannerRemoved():
            edited.add("banner")
        for key, label in self.summaryValues.items():
            value = StateManager.Get(f"tournamentInfo.{key}", "")
            text = "" if value is None else str(value)
            if text == "" or text == "0" and key == "numEntrants":
                shown, color = QApplication.translate("app", "empty"), colors["muted"]
            else:
                shown, color = text, colors["text"]
            if key in edited:
                shown, color = "● " + shown, colors["accentText"]
            label.setText(shown)
            label.setToolTip(text)
            label.setStyleSheet(f"color: {color.name()};")

        name = StateManager.Get("tournamentInfo.tournamentName", "") or QApplication.translate(
            "app", "Tournament Name"
        )
        self.previewName.setText(name)
        details = [StateManager.Get("tournamentInfo.eventName", "") or ""]
        entrants = StateManager.Get("tournamentInfo.numEntrants", 0) or 0
        if entrants:
            details.append(QApplication.translate("app", "{0} entrants").format(entrants))
        self.previewDetail.setText(" · ".join(d for d in details if d))
        link = StateManager.Get("tournamentInfo.shortLink", "") or ""
        self.previewLink.setText(link)
        self.previewLink.setVisible(bool(link))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        narrow = self.width() < NARROW_WIDTH
        self.bodyLayout.setDirection(
            QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight
        )
        if narrow:
            self.rail.setMinimumWidth(0)
            self.rail.setMaximumWidth(16777215)
        else:
            self.rail.setFixedWidth(280)
        self.ShowBanner()

    # =====================================================
    # STYLE
    # =====================================================
    def ApplyStyle(self):
        colors = Theme.Colors()
        c = {k: v.name() for k, v in colors.items()}
        r = Theme.Radius()
        previewBackground = Blend(colors["window"], QColor("#000000"), 0.45).name()
        self.contents.setStyleSheet(
            f"""
            QFrame#header {{ border-bottom: 1px solid {c["raised"]}; }}
            QFrame#card {{
                background: {c["surface"]}; border: 1px solid {c["raised"]};
                border-radius: {r + 4}px;
            }}
            QLabel#cardTitle {{ font-weight: bold; }}
            QLabel#fieldLabel {{ font-weight: bold; color: {c["muted"]}; }}
            QLabel#muted {{ color: {c["muted"]}; }}
            QLabel#editedBadge {{
                background: {c["accent"]}; color: {c["onAccent"]};
                border-radius: 4px; font-weight: bold;
            }}
            QToolButton#linkButton {{
                background: transparent; border: none; padding: 0px; color: {c["accentText"]};
            }}
            QToolButton#linkButton:hover {{ text-decoration: underline; }}
            QLineEdit[edited="true"], QAbstractSpinBox[edited="true"] {{
                border-color: {c["accent"]};
            }}
            QLabel#logoTile {{
                background: {c["raised"]}; border: 1px solid {c["border"]};
                border-radius: {r + 4}px;
            }}
            QLabel#logoTile[dragging="true"] {{ border: 2px dashed {c["accent"]}; }}
            QLabel#bannerView {{
                background: {c["raised"]}; border: 1px dashed {c["border"]};
                border-radius: {r + 2}px; color: {c["muted"]};
            }}
            QFrame#preview {{
                background: {previewBackground}; border: 1px solid {c["raised"]};
                border-radius: {r + 2}px;
            }}
            QFrame#lowerThird {{
                background: {c["surface"]}; border: 1px solid {c["border"]};
                border-radius: {r}px;
            }}
            QLabel#chip {{
                background: {c["accent"]}; color: {c["onAccent"]};
                border-radius: 4px; font-weight: bold;
            }}
            """
        )
        self.UpdateHeader()
        self.RefreshSummary()

    def changeEvent(self, event):
        # The theme changed
        if event.type() == QEvent.Type.PaletteChange and getattr(self, "ready", False):
            self.ApplyStyle()
        super().changeEvent(event)

    # =====================================================
    # ICON
    # =====================================================
    def UpdateIcon(self):
        icon = QPixmap(LOGO_PATH)
        if icon.isNull():
            # Something's wrong with the icon
            icon = QPixmap("./assets/icons/cancel.svg")
        ratio = self.devicePixelRatioF()
        scaled = icon.scaled(
            QSize(84, 84) * ratio,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(ratio)
        self.iconView.setPixmap(scaled)
        small = icon.scaled(
            QSize(30, 30) * ratio,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        small.setDevicePixelRatio(ratio)
        self.previewLogo.setPixmap(small)

    def LoadIcon(self):
        fileName = QFileDialog.getOpenFileName(
            self,
            QApplication.translate("app", "Open Image"),
            ".",
            QApplication.translate("app", "Image Files") + " (*.png *.jpg *.jpeg *.bmp)",
        )[0]
        if fileName:
            self.LoadIconFile(fileName)

    def LoadIconFile(self, fileName):
        try:
            pix = QPixmap(fileName)
            if not pix.isNull():
                pix.save(LOGO_PATH)
        except Exception:
            logger.error(traceback.format_exc())

        self.UpdateIcon()

    def DownloadIcon(self):
        try:
            url = TournamentDataManager.instance.provider.GetIconURL()

            logger.info(f"Icon URL: {url}")

            headers = {
                "client-version": "20",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
            }

            response = requests.get(url, headers=headers)
            data = response.content

            pix = QPixmap()
            pix.loadFromData(data)

            pix.save(LOGO_PATH)
        except Exception:
            logger.error(traceback.format_exc())

        self.UpdateIcon()

    def SetDefaultIcon(self):
        try:
            shutil.copy("./assets/icons/icon.png", LOGO_PATH)
        except Exception:
            logger.error(traceback.format_exc())

        self.UpdateIcon()

    # =====================================================
    # BANNER
    # =====================================================
    def SetBanner(self, url):
        StateManager.Set("tournamentInfo.banner", url or "")
        self.UpdateBanner()
        self.UpdateEdited()
        self.RefreshSummary()

    def UpdateBanner(self):
        url = StateManager.Get("tournamentInfo.banner", "") or ""
        self.btRemoveBanner.setEnabled(bool(url))
        if self.bannerReply is not None:
            self.bannerReply.abort()
            self.bannerReply = None
        self.bannerPixmap = None
        if not url:
            self.bannerView.setText(QApplication.translate("app", "No banner"))
            self.bannerView.setPixmap(QPixmap())
            return
        self.bannerView.setText(QApplication.translate("app", "Loading the banner…"))
        if not url.startswith(("http:", "https:", "file:")):
            self.bannerView.setText(url)
            return
        reply = self.network.get(QNetworkRequest(QUrl(url)))
        reply.finished.connect(lambda reply=reply: self.BannerLoaded(reply))
        self.bannerReply = reply

    def BannerLoaded(self, reply):
        if reply is not self.bannerReply:
            reply.deleteLater()
            return
        self.bannerReply = None
        pixmap = QPixmap()
        pixmap.loadFromData(reply.readAll())
        reply.deleteLater()
        if pixmap.isNull():
            self.bannerView.setText(QApplication.translate("app", "The banner could not be loaded"))
            return
        self.bannerPixmap = pixmap
        self.ShowBanner()

    def ShowBanner(self):
        if self.bannerPixmap is None:
            return
        ratio = self.devicePixelRatioF()
        size = QSize(max(self.bannerView.width() - 4, 1), self.bannerView.height() - 4)
        scaled = self.bannerPixmap.scaled(
            size * ratio,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(ratio)
        self.bannerView.setPixmap(scaled)

    # =====================================================
    # TOURNAMENT DATA
    # =====================================================
    def UpdateData(self, data):
        logger.info("Tournament Data: " + str(data))

        if not data.get("initial_load"):
            for key in TEXT_FIELDS:
                self.fields[key].setText("")
                self.fields[key].editingFinished.emit()
            for key in NUMBER_FIELDS:
                self.fields[key].setValue(0)
            # The tournament's images, which have no field
            StateManager.Set("tournamentInfo.logo", "")
            StateManager.Set("tournamentInfo.banner", "")

        loaded = {}
        for key in data.keys():
            try:
                field = self.fields.get(key)

                if field is not None and data[key] is not None:
                    if isinstance(field, QDateEdit):
                        # A timestamp, shown as a date in local time. None
                        # given: the field is left as it is
                        if data[key] == "":
                            continue
                        local = time.localtime(float(data[key]))
                        field.setDate(QDate(local.tm_year, local.tm_mon, local.tm_mday))
                    elif isinstance(field, QSpinBox):
                        field.setValue(int(data[key]))
                    else:
                        field.setText(str(data[key]))
                        field.editingFinished.emit()
                    loaded[key] = self.FieldValue(key)
                else:
                    exceptions = ["endAt", "eventStartAt", "eventEndAt"]
                    info = data.get(key)

                    if key in exceptions and data.get(key) not in ("", None):
                        unix_timestamp = float(data[key])
                        local_datetime = time.strftime("%x", time.localtime(unix_timestamp))
                        info = local_datetime

                    StateManager.Set(f"tournamentInfo.{key}", info)
                    if key == "banner":
                        loaded[key] = info or ""
            except Exception:
                logger.error(traceback.format_exc())
                SettingsManager.Set("TOURNAMENT_URL", "")
                error_message = (
                    QApplication.translate("app", "The tournament URL could not be loaded.")
                    + "\n"
                    + QApplication.translate(
                        "app",
                        "Make sure that your tournament URL is correctly formatted and points to an existing event, and try again.",
                    )
                )
                self.DisplayErrorMessage(error_message)
                break

        self.loaded = loaded
        self.loadedAt = QTime.currentTime() if loaded else None
        self.UpdateBanner()
        self.UpdateEdited()
        self.RefreshSummary()

    def DisplayErrorMessage(self, message):
        msgBox = QMessageBox()
        msgBox.setWindowIcon(QIcon("assets/icons/icon.png"))
        msgBox.setWindowTitle(QApplication.translate("app", "Error"))
        msgBox.setText(QApplication.translate("app", "Error"))
        msgBox.setInformativeText(message)
        msgBox.setIcon(QMessageBox.Critical)
        msgBox.exec()
