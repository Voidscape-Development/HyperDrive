import copy
import textwrap

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from ..ColorButton import ColorButton
from ..Settings.Controls import (
    Badge,
    Banner,
    ChangedDot,
    Description,
    NoDefaultButtons,
    ResetButton,
    SettingRow,
    SettingsPage,
    ThemeCard,
    ToggleSwitch,
)
from ..SettingsManager import SettingsManager
from ..Theme import ThemedIcon
from .LayoutThemePreview import (
    KIND_SCOREBOARD,
    SECTION_KINDS,
    FillBrush,
    KindLabels,
    LayoutThemePreview,
)
from .LayoutThemes import (
    APPLY_COLORS_FIELDS,
    DEFAULT_GRADIENT_POSITION,
    DEFAULT_THEME,
    FIELD_CHECKBOX,
    FIELD_COLOR,
    FIELD_DROPDOWN,
    FIELD_FILL,
    FIELD_FONT,
    FIELD_NUMBER,
    ExportLayoutTheme,
    GradientDirectionLabels,
    ImportLayoutTheme,
    LayoutThemes,
    LayoutThemeSchema,
    NormalizeValue,
)

# Edits are saved and exported after this long without another change
APPLY_DELAY_MS = 150

GALLERY_WIDTH = 228
PREVIEW_WIDTH = 300

# Whether hovering an option points at what it changes in the preview
HIGHLIGHT_SETTING = "layout_themes.preview_highlight"

# The switch shown above the sections instead of in General
APPLY_COLORS = ("general", "apply_colors")


def _tr(text):
    return QApplication.translate("layout_themes", text)


def OtherTitles():
    """The title of the group of a section's options that aren't colors or
    what's shown, for the sections that need one"""
    return {"general": _tr("Text and corners"), "bracket": _tr("Bracket focus layout")}


def ShortLabels():
    """The labels of what layouts show, in the "Show" grid of each section"""
    return {
        "pronouns_display": _tr("Pronouns"),
        "seed_display": _tr("Seed number"),
        "social_media_display": _tr("Social media"),
        "country_flag_display": _tr("Country flag"),
        "state_flag_display": _tr("State flag"),
        "avatar_display": _tr("Avatar"),
        "losers_display": _tr("Losers [L] badge"),
        "character_display": _tr("Character"),
        "round_names_display": _tr("Round names"),
        "identifier_display": _tr("Set letters (A, B...)"),
        "pending_display": _tr("Where players come from"),
        "dim_losers": _tr("Dim set losers"),
        "game_diff_display": _tr("Game difference"),
        "points_display": _tr("Points"),
        "buchholz_display": _tr("Buchholz (swiss)"),
        "stage_names_display": _tr("Stage names"),
        "striker_display": _tr("Who struck or picked"),
        "first_set_display": _tr("The set being played"),
        "eta_display": _tr("When sets should start"),
        "station_display": _tr("Stations"),
    }


def IsShowField(field):
    return field.type == FIELD_CHECKBOX and not field.group and field.key in ShortLabels()


def DrawLayoutTheme(values):
    """Paints a small sample of a layout theme, for its card"""

    def Draw(painter, rect):
        painter.fillRect(rect, FillBrush(values["general"]["background"], rect))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(values["general"]["primary_color"]))
        radius = min(values["general"]["chip_radius"], 3)
        painter.drawRoundedRect(QRectF(rect.left() + 6, rect.top() + 6, 15, 5), radius, radius)
        stripe = QRectF(rect.left(), rect.bottom() - 6, rect.width(), 6)
        painter.fillRect(
            QRectF(stripe.left(), stripe.top(), stripe.width() / 2, 6),
            QColor(values["teams"]["team1_color"]),
        )
        painter.fillRect(
            QRectF(stripe.center().x(), stripe.top(), stripe.width() / 2, 6),
            QColor(values["teams"]["team2_color"]),
        )

    return Draw


class FillEditor(QWidget):
    """A color, or a linear gradient between two colors, meeting at a
    position. The gradient's controls only show while it's on."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.color = ColorButton(disable_right_click=True, enable_alpha_selection=True)
        self.color.colorChanged.connect(lambda c: self.changed.emit())
        layout.addWidget(self.color)

        self.gradient = QCheckBox(_tr("Gradient"))
        self.gradient.toggled.connect(lambda v: [self.UpdateEnabled(), self.changed.emit()])
        layout.addWidget(self.gradient)

        self.color2 = ColorButton(disable_right_click=True, enable_alpha_selection=True)
        self.color2.colorChanged.connect(lambda c: self.changed.emit())
        layout.addWidget(self.color2)

        self.direction = QComboBox()
        for value, label in GradientDirectionLabels():
            self.direction.addItem(label, value)
        self.direction.currentIndexChanged.connect(lambda i: self.changed.emit())
        layout.addWidget(self.direction)

        self.position = QSpinBox()
        self.position.setRange(0, 100)
        self.position.setSuffix(" %")
        self.position.setValue(DEFAULT_GRADIENT_POSITION)
        self.position.setToolTip(
            _tr(
                "Where the two colors meet, from the first color's side: 50% is an even blend. Lower keeps the first color closer to its side, higher spreads it further.",
            )
        )
        self.position.valueChanged.connect(lambda v: self.changed.emit())
        layout.addWidget(self.position)

        self.UpdateEnabled()

    # =====================================================
    # VALUE
    # =====================================================
    def Value(self):
        return {
            "color": self.color.color(),
            "color2": self.color2.color(),
            "gradient": self.gradient.isChecked(),
            "direction": self.direction.currentData(),
            "position": self.position.value(),
        }

    def SetValue(self, value):
        for w in (self.color, self.color2, self.gradient, self.direction, self.position):
            w.blockSignals(True)
        self.color.setColor(value["color"])
        self.color2.setColor(value["color2"])
        self.gradient.setChecked(value["gradient"])
        self.direction.setCurrentIndex(max(self.direction.findData(value["direction"]), 0))
        self.position.setValue(value.get("position", DEFAULT_GRADIENT_POSITION))
        for w in (self.color, self.color2, self.gradient, self.direction, self.position):
            w.blockSignals(False)
        self.UpdateEnabled()

    def UpdateEnabled(self):
        for w in (self.color2, self.direction, self.position):
            w.setVisible(self.gradient.isChecked())


class FieldEditor:
    """The control for one theme field, with a way to read and fill it.
    A checkbox field is a switch, or with style "check" a checkbox with
    its label, or with style "choice" a dropdown of choices (off, on)."""

    def __init__(self, field, onChange, style=None, choices=None, label=None):
        self.field = field
        type = field.type

        if type == FIELD_CHECKBOX and style == "check":
            self.widget = QCheckBox(label or field.label)
            self.widget.toggled.connect(lambda v: onChange())
            self.get = self.widget.isChecked
            self.set = self.widget.setChecked
        elif type == FIELD_CHECKBOX and style == "choice":
            self.widget = QComboBox()
            for value, text in zip((False, True), choices):
                self.widget.addItem(text, value)
            self.widget.currentIndexChanged.connect(lambda i: onChange())
            self.get = self.widget.currentData
            self.set = lambda v: self.widget.setCurrentIndex(1 if v else 0)
        elif type == FIELD_CHECKBOX:
            self.widget = ToggleSwitch()
            self.widget.toggled.connect(lambda v: onChange())
            self.get = self.widget.isChecked
            self.set = self.widget.setChecked
        elif type == FIELD_COLOR:
            self.widget = ColorButton(disable_right_click=True, enable_alpha_selection=True)
            self.widget.colorChanged.connect(lambda c: onChange())
            self.get = self.widget.color
            self.set = self.widget.setColor
        elif type == FIELD_FILL:
            self.widget = FillEditor()
            self.widget.changed.connect(onChange)
            self.get = self.widget.Value
            self.set = self.widget.SetValue
        elif type == FIELD_DROPDOWN:
            self.widget = QComboBox()
            for value, text in field.options:
                self.widget.addItem(text, value)
            self.widget.currentIndexChanged.connect(lambda i: onChange())
            self.get = self.widget.currentData
            self.set = lambda v: self.widget.setCurrentIndex(max(self.widget.findData(v), 0))
        elif type == FIELD_NUMBER:
            self.widget = QSpinBox()
            self.widget.setRange(field.minimum, field.maximum)
            if field.suffix:
                self.widget.setSuffix(" " + field.suffix)
            self.widget.setFixedWidth(110)
            self.widget.valueChanged.connect(lambda v: onChange())
            self.get = self.widget.value
            self.set = self.widget.setValue
        elif type == FIELD_FONT:
            self.widget = QComboBox()
            self.widget.setMaxVisibleItems(20)
            self.widget.addItem(_tr("Layout default"), "")
            for family in QFontDatabase.families():
                self.widget.addItem(family, family)
            self.widget.currentIndexChanged.connect(lambda i: onChange())
            self.get = self.widget.currentData
            self.set = self.SetFont
        else:
            self.widget = QLineEdit()
            self.widget.textChanged.connect(lambda t: onChange())
            self.get = self.widget.text
            self.set = self.widget.setText

        if field.tooltip and style == "check":
            self.widget.setToolTip("\n".join(textwrap.wrap(field.tooltip, 40)))

    def SetFont(self, family):
        index = self.widget.findData(family)
        if index < 0:
            # A font from a shared theme that isn't installed here
            self.widget.addItem(family, family)
            index = self.widget.count() - 1
        self.widget.setCurrentIndex(index)

    def Fill(self, value):
        self.widget.blockSignals(True)
        try:
            self.set(value)
        finally:
            self.widget.blockSignals(False)
        self.widget.update()


class SectionPage(SettingsPage):
    """A section's fields, in groups: what's shown, colors, the rest, and
    the bracket's focus glow table. Keeps what the search can find."""

    def __init__(self, section):
        super().__init__()
        self.section = section
        # (widget, its group, the text the search looks in)
        self.searchable = []
        # What the search hides, kept hidden by whatever else shows widgets
        self.hiddenBySearch = set()
        self.body.setContentsMargins(0, 12, 6, 12)

    def Searchable(self, widget, group, *texts):
        self.searchable.append((widget, group, " ".join(t for t in texts if t).lower()))

    def Filter(self, words):
        """Hides what the words don't find, and says if anything is left"""
        found = False
        shown = {}
        self.hiddenBySearch = set()
        for widget, group, text in self.searchable:
            match = all(word in text for word in words)
            widget.setHidden(not match)
            if not match:
                self.hiddenBySearch.add(widget)
            found = found or match
            shown[group] = shown.get(group, False) or match
        for group, anyShown in shown.items():
            group.UpdateSeparators()
            group.setVisible(anyShown)
        return found


class HoverWatcher(QObject):
    """Tells the window which option is under the mouse or has the keyboard
    focus, so the preview can point at what it changes"""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        # widget -> (section key, [fields])
        self.targets = {}

    def Watch(self, widget, sectionKey, fields):
        self.targets[widget] = (sectionKey, fields)
        widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        target = self.targets.get(obj)
        if target is not None:
            if event.type() in (QEvent.Type.Enter, QEvent.Type.FocusIn):
                self.window.PointAt(obj, *target)
            elif event.type() in (QEvent.Type.Leave, QEvent.Type.FocusOut):
                self.window.StopPointing(obj)
        return False


class LayoutThemeWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle(_tr("Layout Themes"))

        self.editing = None  # the user theme being edited, as a theme dict
        self.updating = False  # set while the controls are being filled in
        # The built-in theme a copy was just made from, to undo it
        self.copiedFrom = None

        self.applyTimer = QTimer(self)
        self.applyTimer.setSingleShot(True)
        self.applyTimer.setInterval(APPLY_DELAY_MS)
        self.applyTimer.timeout.connect(self.SaveEdits)

        # (section, field) -> FieldEditor
        self.editors = {}
        # (section, field) -> the row showing it, with its dot and reset button
        self.rows = {}
        # The rows of each focus mode's glow: (dot, reset, [fields])
        self.glowRows = []
        # The labels of the fields that need the theme's colors on, and the
        # notes saying so
        self.colorLabels = []
        self.colorNotes = []
        # Pointing the preview at the option under the mouse: the option's
        # widget, and the kind the preview showed before it switched to one
        # that draws the option
        self.hover = HoverWatcher(self)
        self.pointingAt = None
        self.kindBeforePointing = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.BuildGallery())
        layout.addLayout(self.BuildEditor(), 1)
        layout.addWidget(self.BuildPreview())

        NoDefaultButtons(self)
        QShortcut(QKeySequence.StandardKey.Find, self, self.FocusSearch)
        self.resize(1260, 760)
        self.Refresh()

    # =====================================================
    # BUILDING
    # =====================================================
    def BuildGallery(self):
        gallery = QFrame()
        gallery.setObjectName("settingsSidebar")
        gallery.setFixedWidth(GALLERY_WIDTH)
        layout = QVBoxLayout(gallery)
        layout.setContentsMargins(10, 14, 10, 10)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(6, 0, 0, 4)
        header.addWidget(self.Heading(_tr("Your themes")), 1)
        importButton = QToolButton()
        importButton.setIcon(ThemedIcon("assets/icons/download.svg"))
        importButton.setToolTip(_tr("Import a theme file..."))
        importButton.setAutoRaise(True)
        importButton.clicked.connect(self.Import)
        header.addWidget(importButton)
        newButton = QToolButton()
        newButton.setIcon(ThemedIcon("assets/icons/plus.svg"))
        newButton.setToolTip(_tr("New theme from the one in use..."))
        newButton.setAutoRaise(True)
        newButton.clicked.connect(self.NewTheme)
        header.addWidget(newButton)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self.cardsLayout = QVBoxLayout(inner)
        self.cardsLayout.setContentsMargins(0, 0, 0, 0)
        self.cardsLayout.setSpacing(2)
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)
        self.cardGroup = QButtonGroup(self)
        self.cardWidgets = []
        return gallery

    def Heading(self, text):
        label = QLabel(text.upper())
        label.setObjectName("settingsDescription")
        font = label.font()
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() * 0.8)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 106)
        label.setFont(font)
        return label

    def BuildEditor(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 16, 14, 0)
        layout.setSpacing(10)

        # The theme's name and what can be done with it
        header = QHBoxLayout()
        header.setSpacing(6)
        self.nameLabel = QLabel()
        font = self.nameLabel.font()
        font.setPointSizeF(font.pointSizeF() * 1.4)
        font.setBold(True)
        self.nameLabel.setFont(font)
        header.addWidget(self.nameLabel)
        self.builtinBadge = Badge(_tr("Built-in"))
        header.addWidget(self.builtinBadge, 0, Qt.AlignmentFlag.AlignVCenter)
        self.renameButton = QToolButton()
        self.renameButton.setIcon(ThemedIcon("assets/icons/pencil.svg"))
        self.renameButton.setToolTip(_tr("Rename..."))
        self.renameButton.setAutoRaise(True)
        self.renameButton.clicked.connect(self.Rename)
        header.addWidget(self.renameButton)
        header.addStretch(1)
        self.duplicateButton = QPushButton(_tr("Duplicate"))
        self.duplicateButton.setIcon(ThemedIcon("assets/icons/copy.svg"))
        self.duplicateButton.setToolTip(_tr("Starts a new theme from this one"))
        self.duplicateButton.clicked.connect(self.NewTheme)
        header.addWidget(self.duplicateButton)
        self.exportButton = QPushButton(_tr("Export..."))
        self.exportButton.setIcon(ThemedIcon("assets/icons/export.svg"))
        self.exportButton.setToolTip(_tr("Saves the theme in use to a file you can share"))
        self.exportButton.clicked.connect(self.Export)
        header.addWidget(self.exportButton)
        self.deleteButton = QToolButton()
        self.deleteButton.setIcon(ThemedIcon("assets/icons/cancel.svg"))
        self.deleteButton.setToolTip(_tr("Delete"))
        self.deleteButton.clicked.connect(self.Delete)
        header.addWidget(self.deleteButton)
        layout.addLayout(header)

        self.builtinBanner = Banner(
            _tr("Built-in themes stay as they are"),
            _tr("Change any option and HyperDrive makes it your own copy, and switches to it."),
            icon="assets/icons/lock.svg",
        )
        self.builtinBanner.AddButton(_tr("Customize a copy"), primary=True).clicked.connect(
            lambda: self.CopyBuiltin()
        )
        layout.addWidget(self.builtinBanner)

        self.copiedBanner = Banner("", icon="assets/icons/copy.svg")
        self.copiedBanner.AddButton(_tr("Undo")).clicked.connect(self.UndoCopy)
        self.copiedBanner.AddButton(_tr("OK")).clicked.connect(self.copiedBanner.hide)
        self.copiedBanner.hide()
        layout.addWidget(self.copiedBanner)

        # "Use this theme's colors in layouts", above everything it affects
        section = next(s for s in LayoutThemeSchema() if s.key == APPLY_COLORS[0])
        field = next(f for f in section.fields if f.key == APPLY_COLORS[1])
        editor = FieldEditor(field, lambda: self.Edited(APPLY_COLORS[0], field))
        self.editors[APPLY_COLORS] = editor
        colors = Banner(
            _tr("Use this theme's colors, fonts and corners in layouts"),
            _tr(
                "Off: each layout keeps its own look. What's shown and animations apply either way."
            ),
            kind="accent",
        )
        colors.layout().insertWidget(0, editor.widget, 0, Qt.AlignmentFlag.AlignVCenter)
        editor.widget.setAccessibleName(_tr("Use this theme's colors in layouts"))
        layout.addWidget(colors)

        self.search = QLineEdit()
        self.search.setPlaceholderText(_tr("Find an option in any section"))
        self.search.setClearButtonEnabled(True)
        self.search.addAction(
            ThemedIcon("assets/icons/search.svg"), QLineEdit.ActionPosition.LeadingPosition
        )
        self.search.textChanged.connect(self.Search)
        layout.addWidget(self.search)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(True)
        # Nine sections: tighter tabs so they all fit
        self.tabs.tabBar().setStyleSheet("QTabBar::tab { padding: 6px 9px; }")
        self.tabs.currentChanged.connect(self.TabChanged)
        self.pages = []
        for section in LayoutThemeSchema():
            page = self.BuildSection(section)
            self.pages.append(page)
            self.tabs.addTab(page, section.label)
        layout.addWidget(self.tabs, 1)
        return layout

    def BuildSection(self, section):
        page = SectionPage(section)
        show = [f for f in section.fields if IsShowField(f)]
        colors = [
            f
            for f in section.fields
            if (section.key, f.key) in APPLY_COLORS_FIELDS and not IsShowField(f)
        ]
        glow = [f for f in section.fields if f.group]
        other = [
            f
            for f in section.fields
            if f not in show
            and f not in colors
            and f not in glow
            and (section.key, f.key) != APPLY_COLORS
        ]

        if len(show) >= 3:
            group = page.AddGroup(_tr("Show"))
            grid = QWidget()
            gridLayout = QGridLayout(grid)
            gridLayout.setContentsMargins(16, 2, 16, 10)
            gridLayout.setHorizontalSpacing(16)
            gridLayout.setVerticalSpacing(6)
            labels = ShortLabels()
            for i, field in enumerate(show):
                editor = FieldEditor(
                    field,
                    lambda s=section.key, f=field: self.Edited(s, f),
                    style="check",
                    label=labels[field.key],
                )
                self.editors[(section.key, field.key)] = editor
                gridLayout.addWidget(editor.widget, i // 3, i % 3)
                self.hover.Watch(editor.widget, section.key, [field])
                page.Searchable(editor.widget, group, labels[field.key], field.label, field.tooltip)
            for column in range(3):
                gridLayout.setColumnStretch(column, 1)
            group.AddWidget(grid)
        else:
            other = show + other

        if colors:
            group = page.AddGroup(_tr("Colors"))
            note = Description(_tr("Used once this theme's colors are on"))
            note.setWordWrap(False)
            group.header.addWidget(note)
            self.colorNotes.append(note)
            self.AddRows(page, group, section, colors)
        if other:
            group = page.AddGroup(OtherTitles().get(section.key))
            self.AddRows(page, group, section, other)
        if glow:
            self.BuildGlowTable(page, section, glow)
        page.Finish()
        return page

    def AddRows(self, page, group, section, fields):
        for field in fields:
            key = (section.key, field.key)
            editor = FieldEditor(field, lambda s=section.key, f=field: self.Edited(s, f))
            self.editors[key] = editor
            row = SettingRow(
                field.label, editor.widget, field.tooltip, indent=bool(field.enabled_by)
            )
            row.resetClicked.connect(lambda s=section.key, f=field: self.Reset(s, [f]))
            if key in APPLY_COLORS_FIELDS:
                self.colorLabels.append(row.label)
            self.rows[key] = row
            group.AddRow(row)
            self.hover.Watch(row, section.key, [field])
            self.hover.Watch(editor.widget, section.key, [field])
            page.Searchable(row, group, field.label, field.tooltip)

    def BuildGlowTable(self, page, section, fields):
        """The focus glow fields, one row per focus mode: the glow, and its
        color (the focus highlight, or its own)"""
        group = page.AddGroup(_tr("Focus glow"), _tr("Bracket focus layout, per focus mode"))
        table = QWidget()
        grid = QGridLayout(table)
        grid.setContentsMargins(16, 4, 8, 10)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        for column, text in enumerate((_tr("Mode"), _tr("Glow"), _tr("Color"))):
            grid.addWidget(self.Heading(text), 0, column + 1)
        modes = {}
        for field in fields:
            modes.setdefault(field.group, []).append(field)
        for row, (name, modeFields) in enumerate(modes.items(), start=1):
            glowField, customField, colorField = modeFields
            # "Focus glow: round mode" -> "Round mode"
            title = name.split(":", 1)[-1].strip()
            title = title[:1].upper() + title[1:]
            label = QLabel(title)
            dot = ChangedDot()
            dot.hide()
            grid.addWidget(dot, row, 0)
            grid.addWidget(label, row, 1)
            glow = FieldEditor(glowField, lambda f=glowField: self.Edited(section.key, f))
            glow.widget.setAccessibleName(_tr("Glow: {0}").format(title))
            grid.addWidget(glow.widget, row, 2)
            custom = FieldEditor(
                customField,
                lambda f=customField: self.Edited(section.key, f),
                style="choice",
                choices=(_tr("Focus highlight"), _tr("Own color")),
            )
            color = FieldEditor(colorField, lambda f=colorField: self.Edited(section.key, f))
            cell = QHBoxLayout()
            cell.addWidget(custom.widget)
            cell.addWidget(color.widget)
            cell.addStretch()
            grid.addLayout(cell, row, 3)
            reset = ResetButton(_tr('Reset "{0}" to default').format(title))
            reset.hide()
            reset.clicked.connect(lambda checked=False, f=modeFields: self.Reset(section.key, f))
            grid.addWidget(reset, row, 4)
            for field, editor in zip(modeFields, (glow, custom, color)):
                self.editors[(section.key, field.key)] = editor
            self.glowRows.append((section.key, dot, reset, modeFields, label))
            for widget in (dot, label, glow.widget, custom.widget, color.widget, reset):
                page.Searchable(widget, group, title, name, _tr("Focus glow"))
            for widget in (label, glow.widget, custom.widget, color.widget):
                self.hover.Watch(widget, section.key, modeFields)
        grid.setColumnStretch(3, 1)
        group.AddWidget(table)

    def BuildPreview(self):
        pane = QFrame()
        pane.setObjectName("settingsAside")
        pane.setFixedWidth(PREVIEW_WIDTH)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(14, 16, 14, 14)
        layout.setSpacing(10)
        header = QHBoxLayout()
        header.addWidget(self.Heading(_tr("Preview")), 1)
        self.previewKind = QComboBox()
        for kind, label in KindLabels():
            self.previewKind.addItem(label, kind)
        self.previewKind.currentIndexChanged.connect(self.PreviewKindChanged)
        header.addWidget(self.previewKind)
        layout.addLayout(header)
        self.preview = LayoutThemePreview()
        layout.addWidget(self.preview)

        # The other kinds, small: clicking one shows it above
        layout.addSpacing(6)
        layout.addWidget(self.Heading(_tr("Also shown")))
        thumbnails = QGridLayout()
        thumbnails.setSpacing(8)
        self.thumbnails = []
        for i, (kind, label) in enumerate(KindLabels()):
            thumbnail = LayoutThemePreview(thumbnail=True)
            thumbnail.SetKind(kind)
            thumbnail.setToolTip(label)
            thumbnail.setAccessibleName(label)
            thumbnail.clicked.connect(
                lambda k=kind: self.previewKind.setCurrentIndex(self.previewKind.findData(k))
            )
            self.thumbnails.append(thumbnail)
            thumbnails.addWidget(thumbnail, i // 2, i % 2)
        layout.addLayout(thumbnails)
        self.PreviewKindChanged()
        layout.addSpacing(4)
        self.highlightCheck = QCheckBox(_tr("Point at what an option changes"))
        self.highlightCheck.setToolTip(
            _tr(
                "Hovering an option, or tabbing to it, outlines what it changes in the preview and dims the rest"
            )
        )
        self.highlightCheck.setChecked(bool(SettingsManager.Get(HIGHLIGHT_SETTING, True)))
        self.highlightCheck.toggled.connect(self.HighlightToggled)
        layout.addWidget(self.highlightCheck)
        layout.addStretch(1)
        layout.addWidget(
            Description(
                _tr(
                    "An approximation drawn by HyperDrive. Your layouts in OBS update live as well."
                )
            )
        )
        return pane

    # =====================================================
    # POINTING AT AN OPTION
    # =====================================================
    def PointAt(self, widget, sectionKey, fields):
        if not self.highlightCheck.isChecked():
            return
        keys = [f"{sectionKey}.{field.key}" for field in fields]
        kinds = self.preview.KindsShowing(keys)
        current = self.previewKind.currentData()
        if kinds and current not in kinds:
            # Shows the option in a preview that draws it, until the mouse
            # leaves it
            if self.kindBeforePointing is None:
                self.kindBeforePointing = current
            self.previewKind.blockSignals(True)
            self.previewKind.setCurrentIndex(self.previewKind.findData(kinds[0]))
            self.previewKind.blockSignals(False)
            self.preview.SetKind(kinds[0])
        elif not kinds and self.kindBeforePointing is not None:
            self.RestoreKind()
        values = self.Theme()["values"][sectionKey]
        off = len(fields) == 1 and fields[0].type == FIELD_CHECKBOX and not values[fields[0].key]
        note = _tr("Off, so it isn't shown") if off else _tr("Not in the preview")
        self.pointingAt = widget
        self.preview.SetHighlight(keys, note)

    def StopPointing(self, widget):
        if widget is not self.pointingAt:
            return
        self.pointingAt = None
        self.preview.SetHighlight(None)
        # Not at once: moving to the next option shouldn't flicker
        QTimer.singleShot(250, self.RestoreKindIfIdle)

    def RestoreKindIfIdle(self):
        if self.pointingAt is None:
            self.RestoreKind()

    def RestoreKind(self):
        if self.kindBeforePointing is None:
            return
        self.previewKind.blockSignals(True)
        self.previewKind.setCurrentIndex(self.previewKind.findData(self.kindBeforePointing))
        self.previewKind.blockSignals(False)
        self.preview.SetKind(self.kindBeforePointing)
        self.kindBeforePointing = None

    def HighlightToggled(self, on):
        SettingsManager.Set(HIGHLIGHT_SETTING, on)
        if not on:
            self.pointingAt = None
            self.preview.SetHighlight(None)
            self.RestoreKind()

    def PreviewKindChanged(self, index=None):
        kind = self.previewKind.currentData()
        # Picked by hand: stays when the mouse leaves an option
        self.kindBeforePointing = None
        self.preview.SetKind(kind)
        for thumbnail in getattr(self, "thumbnails", []):
            thumbnail.SetSelected(thumbnail.kind == kind)

    # =====================================================
    # REFRESHING
    # =====================================================
    def Theme(self):
        """The theme on screen: the one being edited, or the built-in one"""
        return self.editing if self.editing is not None else LayoutThemes.Active()

    def Refresh(self):
        # Fills the controls in from the saved themes
        self.updating = True
        active = LayoutThemes.ActiveName()
        theme = LayoutThemes.Active()
        builtin = LayoutThemes.IsBuiltin(active)
        self.editing = None if builtin else copy.deepcopy(theme)

        self.RefreshGallery()
        self.nameLabel.setText(LayoutThemes.DisplayName(active))
        self.builtinBadge.setVisible(builtin)
        self.renameButton.setVisible(not builtin)
        self.deleteButton.setVisible(not builtin)
        self.builtinBanner.setVisible(builtin)

        for (sectionKey, fieldKey), editor in self.editors.items():
            editor.Fill(theme["values"][sectionKey][fieldKey])
        self.UpdateStates(theme)
        self.updating = False

    def RefreshGallery(self):
        # Taken out of the layout at once: deleteLater() only deletes them
        # once the event loop runs, and they'd be laid out until then
        for widget in self.cardWidgets:
            if isinstance(widget, QAbstractButton):
                self.cardGroup.removeButton(widget)
            self.cardsLayout.removeWidget(widget)
            widget.hide()
            widget.deleteLater()
        self.cardWidgets = []
        active = LayoutThemes.ActiveName()
        inUse = _tr("● In use")

        def Add(name, theme, subtitle=""):
            card = ThemeCard(
                LayoutThemes.DisplayName(name),
                DrawLayoutTheme(theme["values"]),
                inUse if name == active else subtitle,
                layout="list",
            )
            card.setChecked(name == active)
            card.clicked.connect(lambda checked=False, n=name: self.SelectTheme(n))
            if not LayoutThemes.IsBuiltin(name):
                card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                card.customContextMenuRequested.connect(
                    lambda pos, c=card, n=name: self.CardMenu(c, n, pos)
                )
            self.cardGroup.addButton(card)
            self.cardsLayout.addWidget(card)
            self.cardWidgets.append(card)

        userThemes = LayoutThemes.UserThemes()
        for name in sorted(userThemes, key=str.lower):
            Add(name, userThemes[name])
        if not userThemes:
            empty = Description(_tr("Change any option of a built-in theme to make your own."))
            empty.setContentsMargins(6, 0, 6, 6)
            self.cardsLayout.addWidget(empty)
            self.cardWidgets.append(empty)
        heading = self.Heading(_tr("Built-in"))
        heading.setContentsMargins(6, 14, 0, 4)
        self.cardsLayout.addWidget(heading)
        self.cardWidgets.append(heading)
        for name in LayoutThemes.BuiltinNames():
            Add(
                name,
                LayoutThemes.BuiltinTheme(name),
                _tr("Each layout's own look") if name == DEFAULT_THEME else "",
            )
        stretch = QWidget()
        stretch.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.cardsLayout.addWidget(stretch, 1)
        self.cardWidgets.append(stretch)

    def UpdateStates(self, theme):
        """Everything that follows the values: dimmed and disabled fields,
        the changed dots and the preview"""
        values = theme["values"]
        applyColors = values["general"]["apply_colors"]
        for label in self.colorLabels:
            label.setEnabled(applyColors)
        for note in self.colorNotes:
            note.setVisible(not applyColors)
        # Fields with enabled_by are only editable while their switch is on.
        # A glow's own color only shows while it's picked.
        for (sectionKey, fieldKey), editor in self.editors.items():
            enabledBy = editor.field.enabled_by
            if enabledBy:
                on = bool(values[sectionKey].get(enabledBy))
                row = self.rows.get((sectionKey, fieldKey))
                if row is not None:
                    row.setEnabled(on)
                else:
                    page = self.pages[self.SectionIndex(sectionKey)]
                    editor.widget.setVisible(on and editor.widget not in page.hiddenBySearch)
        for (sectionKey, fieldKey), row in self.rows.items():
            field = self.editors[(sectionKey, fieldKey)].field
            row.SetChanged(not self.IsDefault(values, sectionKey, field))
        for sectionKey, dot, reset, fields, label in self.glowRows:
            changed = any(not self.IsDefault(values, sectionKey, f) for f in fields)
            dot.setVisible(changed)
            reset.setVisible(changed)
        self.preview.SetValues(values)
        for thumbnail in self.thumbnails:
            thumbnail.SetValues(values)

    @staticmethod
    def IsDefault(values, sectionKey, field):
        # Saved values are normalized (colors as #aarrggbb), defaults aren't
        return values[sectionKey][field.key] == NormalizeValue(field, field.default)

    def SectionIndex(self, sectionKey):
        return next(i for i, page in enumerate(self.pages) if page.section.key == sectionKey)

    # =====================================================
    # THEME SELECTION
    # =====================================================
    def SelectTheme(self, name):
        if self.updating:
            return
        self.SaveEdits()
        self.copiedBanner.hide()
        LayoutThemes.SetActive(name)
        self.Refresh()

    def CardMenu(self, card, name, pos):
        if LayoutThemes.ActiveName() != name:
            self.SelectTheme(name)
        menu = QMenu(self)
        menu.addAction(ThemedIcon("assets/icons/pencil.svg"), _tr("Rename..."), self.Rename)
        menu.addAction(ThemedIcon("assets/icons/copy.svg"), _tr("Duplicate"), self.NewTheme)
        menu.addAction(ThemedIcon("assets/icons/export.svg"), _tr("Export..."), self.Export)
        menu.addSeparator()
        menu.addAction(ThemedIcon("assets/icons/cancel.svg"), _tr("Delete"), self.Delete)
        menu.exec(card.mapToGlobal(pos))

    def TabChanged(self, index):
        # Also called while the tabs are added, before the preview exists
        if hasattr(self, "previewKind") and 0 <= index < len(self.pages):
            kind = SECTION_KINDS.get(self.pages[index].section.key, KIND_SCOREBOARD)
            self.previewKind.setCurrentIndex(max(self.previewKind.findData(kind), 0))

    # =====================================================
    # SEARCH
    # =====================================================
    def FocusSearch(self):
        self.search.setFocus()
        self.search.selectAll()

    def Search(self, text):
        words = text.lower().split()
        first = None
        for i, page in enumerate(self.pages):
            found = page.Filter(words)
            self.tabs.setTabEnabled(i, found or not words)
            if found and first is None:
                first = i
        if words and first is not None and not self.tabs.isTabEnabled(self.tabs.currentIndex()):
            self.tabs.setCurrentIndex(first)
        # The search showed the glows' own colors again
        self.UpdateStates(self.Theme())

    # =====================================================
    # EDITING FIELDS
    # =====================================================
    def Edited(self, sectionKey, field):
        if self.updating:
            return
        editor = self.editors[(sectionKey, field.key)]
        value = NormalizeValue(field, editor.get())
        if self.editing is None:
            # A built-in theme: the change goes to a copy of it
            self.CopyBuiltin()
        self.editing["values"][sectionKey][field.key] = value
        self.UpdateStates(self.editing)
        self.applyTimer.start()

    def Reset(self, sectionKey, fields):
        for field in fields:
            self.editors[(sectionKey, field.key)].Fill(field.default)
        for field in fields:
            self.Edited(sectionKey, field)

    def SaveEdits(self):
        if self.applyTimer.isActive():
            self.applyTimer.stop()
        if self.editing is None:
            return
        LayoutThemes.SaveTheme(self.editing)
        # Its card shows its colors
        for card in self.cardGroup.buttons():
            if card.isChecked():
                card.draw = DrawLayoutTheme(self.editing["values"])
                card.update()

    def CopyBuiltin(self):
        """Makes the built-in theme in use the user's own copy, and switches
        to it. The controls keep what they show."""
        builtin = LayoutThemes.ActiveName()
        if not LayoutThemes.IsBuiltin(builtin):
            return
        current = LayoutThemes.Active()
        name = LayoutThemes.UniqueName(
            _tr("{0} (custom)").format(LayoutThemes.DisplayName(builtin))
        )
        theme = LayoutThemes.SaveTheme({"name": name, "values": copy.deepcopy(current["values"])})
        LayoutThemes.SetActive(theme["name"])
        self.editing = copy.deepcopy(theme)
        self.copiedFrom = builtin
        self.copiedBanner.SetText(
            _tr('Made your own copy, "{0}"').format(theme["name"]),
            _tr("{0} stays as it was. Your changes go to the copy.").format(
                LayoutThemes.DisplayName(builtin)
            ),
        )
        self.copiedBanner.show()
        self.builtinBanner.hide()
        self.builtinBadge.hide()
        self.renameButton.show()
        self.deleteButton.show()
        self.nameLabel.setText(theme["name"])
        updating, self.updating = self.updating, True
        self.RefreshGallery()
        self.updating = updating

    def UndoCopy(self):
        if self.editing is None or self.copiedFrom is None:
            return
        self.applyTimer.stop()
        name = self.editing["name"]
        self.editing = None
        LayoutThemes.DeleteTheme(name)
        LayoutThemes.SetActive(self.copiedFrom)
        self.copiedFrom = None
        self.copiedBanner.hide()
        self.Refresh()

    # =====================================================
    # MANAGING THEMES
    # =====================================================
    def AskName(self, title, name):
        name, ok = QInputDialog.getText(
            self, title, _tr("Theme name"), QLineEdit.EchoMode.Normal, name
        )
        name = name.strip()
        return name if ok and name else None

    def NewTheme(self):
        self.SaveEdits()
        current = LayoutThemes.Active()
        name = self.AskName(
            _tr("New theme"),
            LayoutThemes.UniqueName(
                _tr("{0} (custom)").format(LayoutThemes.DisplayName(current["name"]))
            ),
        )
        if not name:
            return
        theme = LayoutThemes.SaveTheme(
            {"name": LayoutThemes.UniqueName(name), "values": copy.deepcopy(current["values"])}
        )
        self.SelectTheme(theme["name"])

    def Rename(self):
        if self.editing is None:
            return
        self.SaveEdits()
        oldName = self.editing["name"]
        name = self.AskName(_tr("Rename theme"), oldName)
        if not name or name == oldName:
            return
        theme = LayoutThemes.SaveTheme(
            dict(self.editing, name=LayoutThemes.UniqueName(name)), oldName
        )
        self.copiedBanner.hide()
        self.SelectTheme(theme["name"])

    def Delete(self):
        if self.editing is None:
            return
        name = self.editing["name"]
        answer = QMessageBox.question(
            self, _tr("Delete theme"), _tr('Delete the theme "{0}"?').format(name)
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.applyTimer.stop()
        self.editing = None
        self.copiedBanner.hide()
        LayoutThemes.DeleteTheme(name)
        self.Refresh()

    # =====================================================
    # IMPORT AND EXPORT
    # =====================================================
    def Import(self):
        self.SaveEdits()
        path, _ = QFileDialog.getOpenFileName(
            self, _tr("Import theme"), "", _tr("HyperDrive layout theme") + " (*.json)"
        )
        if not path:
            return
        try:
            theme = ImportLayoutTheme(path)
        except ValueError as e:
            logger.error(f"Could not import layout theme {path}: {e}")
            QMessageBox.warning(
                self, _tr("Import theme"), _tr("This file isn't a HyperDrive layout theme.")
            )
            return
        theme["name"] = LayoutThemes.UniqueName(theme["name"])
        LayoutThemes.SaveTheme(theme)
        self.SelectTheme(theme["name"])

    def Export(self):
        self.SaveEdits()
        theme = dict(LayoutThemes.Active())
        theme["name"] = LayoutThemes.DisplayName(theme["name"])
        path, _ = QFileDialog.getSaveFileName(
            self,
            _tr("Export theme"),
            f"{theme['name']}.json",
            _tr("HyperDrive layout theme") + " (*.json)",
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            ExportLayoutTheme(theme, path)
        except OSError as e:
            logger.error(f"Could not export layout theme to {path}: {e}")
            QMessageBox.warning(
                self, _tr("Export theme"), _tr("The theme could not be saved.") + f"\n\n{e}"
            )

    # =====================================================
    # EVENTS
    # =====================================================
    def closeEvent(self, event):
        self.SaveEdits()
        super().closeEvent(event)

    def done(self, result):
        self.SaveEdits()
        super().done(result)
