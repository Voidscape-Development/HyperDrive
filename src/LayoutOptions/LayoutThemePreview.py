# A small picture of what a layout theme looks like on stream, drawn from its
# values: a scoreboard, a bracket, a stage strike, the stream queue, standings
# or a versus screen. It's an approximation of the layouts, to see a change
# right away; the layouts themselves update live too.
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from ..Theme import Blend, Theme
from .LayoutThemes import APPLY_COLORS_FIELDS, DEFAULT_GRADIENT_POSITION, DefaultValues

# The preview is drawn at this size and scaled to the widget, 16:9 like a stream
WIDTH = 480
HEIGHT = 270

KIND_SCOREBOARD = "scoreboard"
KIND_BRACKET = "bracket"
KIND_STAGE_STRIKE = "stage_strike"
KIND_STREAM_QUEUE = "stream_queue"
KIND_STANDINGS = "standings"
KIND_VERSUS = "versus"

# The fields that change how all text looks
TEXT_KEYS = (
    "general.text_color",
    "general.font_family",
    "general.text_case",
    "general.text_outline",
)
# The bracket's focus glow fields, for every focus mode
GLOW_KEYS = tuple(
    f"bracket.focus_glow{kind}_{mode}"
    for mode in ("sets", "rounds", "side", "player", "follow", "tour")
    for kind in ("", "_custom", "_color")
)

# Gray stand-ins for pictures (stages, avatars, characters, flags)
PICTURE = QColor("#59607a")
PICTURE_DARK = QColor("#3a3f52")


def _tr(text):
    return QApplication.translate("layout_themes", text)


def KindLabels():
    return [
        (KIND_SCOREBOARD, _tr("Scoreboard")),
        (KIND_BRACKET, _tr("Bracket")),
        (KIND_STAGE_STRIKE, _tr("Stage strike")),
        (KIND_STREAM_QUEUE, _tr("Stream queue")),
        (KIND_STANDINGS, _tr("Standings")),
        (KIND_VERSUS, _tr("Versus")),
    ]


# The picture that shows a section best
SECTION_KINDS = {
    "bracket": KIND_BRACKET,
    "stage_strike": KIND_STAGE_STRIKE,
    "stream_queue": KIND_STREAM_QUEUE,
    "standings": KIND_STANDINGS,
    "versus": KIND_VERSUS,
}

GRADIENT_POINTS = {
    # direction: (start, end) as fractions of the width and height
    "to top left": ((1, 1), (0, 0)),
    "to top": ((0, 1), (0, 0)),
    "to top right": ((0, 1), (1, 0)),
    "to left": ((1, 0), (0, 0)),
    "to right": ((0, 0), (1, 0)),
    "to bottom left": ((1, 0), (0, 1)),
    "to bottom": ((0, 0), (0, 1)),
    "to bottom right": ((0, 0), (1, 1)),
}


def FillBrush(fill, rect):
    """A theme fill (a color, or a gradient between two) as a brush"""
    color = QColor(fill["color"])
    if not fill.get("gradient"):
        return QBrush(color)
    color2 = QColor(fill["color2"])
    (x1, y1), (x2, y2) = GRADIENT_POINTS.get(fill.get("direction"), GRADIENT_POINTS["to right"])
    gradient = QLinearGradient(
        rect.left() + rect.width() * x1,
        rect.top() + rect.height() * y1,
        rect.left() + rect.width() * x2,
        rect.top() + rect.height() * y2,
    )
    # Where the two colors meet: 50 is an even blend
    position = min(max(fill.get("position", DEFAULT_GRADIENT_POSITION), 1), 99) / 100
    gradient.setColorAt(0, color)
    gradient.setColorAt(position, Blend(color, color2, 0.5))
    gradient.setColorAt(1, color2)
    return QBrush(gradient)


class LayoutThemePreview(QWidget):
    """thumbnail: a small one that's clicked to show its kind in the big one"""

    clicked = Signal()

    def __init__(self, thumbnail=False, parent=None):
        super().__init__(parent)
        self.values = DefaultValues()
        self.defaults = DefaultValues()
        self.kind = KIND_SCOREBOARD
        self.thumbnail = thumbnail
        # A thumbnail of the kind the big preview shows
        self.selected = False
        # The fields of the option under the mouse, as "section.field": what
        # they change is outlined and the rest dimmed
        self.highlight = set()
        # What to say when nothing they change is drawn
        self.highlightNote = ""
        # Where the highlighted fields were drawn, collected while painting
        self.marks = []
        if thumbnail:
            self.setFixedSize(128, 72)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setMinimumSize(240, 135)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(_tr("Preview of the theme"))

    def SetSelected(self, selected):
        self.selected = selected
        self.update()

    def mouseReleaseEvent(self, event):
        if self.thumbnail and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return round(width * HEIGHT / WIDTH)

    def sizeHint(self):
        return QSize(272, 153)

    def SetValues(self, values):
        self.values = values
        self.update()

    def SetKind(self, kind):
        self.kind = kind
        self.update()

    def SetHighlight(self, keys=None, note=""):
        """Points at what the fields change: keys as "section.field". note
        is said when none of them is drawn in this preview."""
        self.highlight = set(keys or [])
        self.highlightNote = note
        self.update()

    def Drawers(self):
        return {
            KIND_SCOREBOARD: self.DrawScoreboard,
            KIND_BRACKET: self.DrawBracket,
            KIND_STAGE_STRIKE: self.DrawStageStrike,
            KIND_STREAM_QUEUE: self.DrawStreamQueue,
            KIND_STANDINGS: self.DrawStandings,
            KIND_VERSUS: self.DrawVersus,
        }

    def KindsShowing(self, keys):
        """The kinds of preview that draw something from these fields, with
        the theme's values as they are"""
        saved = self.highlight, self.marks, self.thumbnail
        self.highlight, self.thumbnail = set(keys), False
        image = QImage(WIDTH // 4, HEIGHT // 4, QImage.Format.Format_ARGB32)
        kinds = []
        for kind, draw in self.Drawers().items():
            self.marks = []
            painter = QPainter(image)
            painter.scale(0.25, 0.25)
            draw(painter)
            painter.end()
            if self.marks:
                kinds.append(kind)
        self.highlight, self.marks, self.thumbnail = saved
        return kinds

    def Mark(self, rect, *keys):
        """Says that rect was drawn from these fields"""
        if self.highlight and not self.thumbnail and self.highlight.intersection(keys):
            self.marks.append(QRectF(rect))

    # =====================================================
    # THE THEME'S VALUES
    # =====================================================
    def V(self, section, key):
        """A value, or the layouts' own when the theme's colors are off"""
        if (section, key) in APPLY_COLORS_FIELDS and not self.values["general"]["apply_colors"]:
            return self.defaults[section][key]
        return self.values[section][key]

    def C(self, section, key):
        return QColor(self.V(section, key))

    def On(self, section, key):
        return bool(self.values[section].get(key))

    def Radius(self, small=False):
        return self.V("general", "chip_radius" if small else "border_radius")

    def Font(self, size, bold=True):
        font = QFont(self.font())
        family = self.values["general"]["font_family"]
        if family:
            font.setFamily(family)
        font.setPixelSize(size)
        font.setBold(bold)
        return font

    def Case(self, text):
        return text.upper() if self.values["general"]["text_case"] != "none" else text

    # =====================================================
    # DRAWING HELPERS
    # =====================================================
    def Box(self, p, rect, brush, radius=None):
        radius = self.Radius() if radius is None else radius
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(brush)
        p.drawRoundedRect(rect, radius, radius)

    def Text(self, p, rect, text, color, size=14, align=Qt.AlignmentFlag.AlignCenter, bold=True):
        font = self.Font(size, bold)
        text = self.Case(text)
        metrics = QFontMetricsF(font)
        text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, rect.width())
        width = metrics.horizontalAdvance(text)
        if align & Qt.AlignmentFlag.AlignLeft:
            x = rect.left()
        elif align & Qt.AlignmentFlag.AlignRight:
            x = rect.right() - width
        else:
            x = rect.center().x() - width / 2
        y = rect.center().y() + (metrics.ascent() - metrics.descent()) / 2
        path = QPainterPath()
        path.addText(QPointF(x, y), font, text)
        if self.values["general"]["text_outline"]:
            outline = QColor("#000000") if QColor(color).lightnessF() > 0.5 else QColor("#ffffff")
            outline.setAlphaF(0.55)
            p.setPen(
                QPen(
                    outline,
                    2,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        p.drawPath(path)

    def Avatar(self, p, center, radius):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(PICTURE)
        p.drawEllipse(center, radius, radius)

    def Flag(self, p, x, y, h=10):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#c8102e"))
        p.drawRect(QRectF(x, y, h * 1.5, h / 2))
        p.setBrush(QColor("#f2f2f2"))
        p.drawRect(QRectF(x, y + h / 2, h * 1.5, h / 2))
        return h * 1.5 + 4

    def Glow(self, p, rect, color):
        for i in range(5, 0, -1):
            glow = QColor(color)
            glow.setAlphaF(0.07 * (6 - i))
            p.setPen(QPen(glow, i * 2.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect, self.Radius(), self.Radius())
        p.setPen(QPen(color, 2))
        p.drawRoundedRect(rect, self.Radius(), self.Radius())

    # =====================================================
    # PAINTING
    # =====================================================
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        scale = min(self.width() / WIDTH, self.height() / HEIGHT)
        p.translate((self.width() - WIDTH * scale) / 2, (self.height() - HEIGHT * scale) / 2)
        p.scale(scale, scale)
        frame = QRectF(0, 0, WIDTH, HEIGHT)
        clip = QPainterPath()
        clip.addRoundedRect(frame, 12, 12)
        p.setClipPath(clip)
        p.fillRect(frame, FillBrush(self.V("general", "background"), frame))
        self.marks = []
        self.Mark(frame, "general.background")
        self.Drawers().get(self.kind, self.DrawScoreboard)(p)
        if self.highlight and not self.thumbnail:
            self.DrawHighlight(p, frame)
        p.setClipping(False)
        colors = Theme.Colors()
        if self.selected:
            p.setPen(QPen(colors["accent"], 2.5 / scale))
        else:
            p.setPen(QPen(colors["border"], 1 / scale))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(frame.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)

    def DrawHighlight(self, p, frame):
        accent = Theme.Colors()["accent"]
        if not self.marks:
            font = QFont(self.font())
            font.setPixelSize(15)
            font.setBold(True)
            metrics = QFontMetricsF(font)
            note = self.highlightNote or _tr("Not in this preview")
            box = QRectF(0, 0, metrics.horizontalAdvance(note) + 28, 32)
            box.moveCenter(QPointF(frame.center().x(), frame.bottom() - 30))
            p.setPen(QPen(accent, 1.5))
            p.setBrush(QColor(0, 0, 0, 190))
            p.drawRoundedRect(box, 8, 8)
            p.setPen(QColor("#ffffff"))
            p.setFont(font)
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, note)
            return
        inside = frame.adjusted(3, 3, -3, -3)
        holes = QPainterPath()
        for rect in self.marks:
            holes.addRoundedRect(rect.adjusted(-3, -3, 3, 3).intersected(inside), 5, 5)
        holes = holes.simplified()
        everything = QPainterPath()
        everything.addRect(frame)
        p.fillPath(everything.subtracted(holes), QColor(0, 0, 0, 150))
        p.setPen(QPen(accent, 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(holes)

    def DrawScoreboard(self, p):
        secondary = self.C("general", "secondary_color")
        text = self.C("general", "text_color")
        primary = self.C("general", "primary_color")
        y, h = 22, 44
        self.Box(p, QRectF(24, y, 180, h), secondary)
        self.Box(p, QRectF(276, y, 180, h), secondary)
        for rect in (QRectF(24, y, 180, h), QRectF(276, y, 180, h)):
            self.Mark(rect, *TEXT_KEYS, "general.secondary_color", "general.border_radius")
        for x, team in ((204, "1"), (240, "2")):
            self.Mark(
                QRectF(x, y, 36, h), f"teams.team{team}_color", f"teams.team{team}_score_color"
            )
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self.C("teams", f"team{team}_color"))
            p.drawRect(QRectF(x, y, 36, h))
            self.Text(
                p,
                QRectF(x, y, 36, h),
                "2" if team == "1" else "1",
                self.C("teams", f"team{team}_score_color"),
                24,
            )
        self.Text(p, QRectF(36, y, 160, h), "Kiyo", text, 18, Qt.AlignmentFlag.AlignLeft)
        self.Text(p, QRectF(284, y, 160, h), "Marlow", text, 18, Qt.AlignmentFlag.AlignRight)
        label = QRectF(165, y + h + 8, 150, 22)
        self.Box(p, label, primary, self.Radius(True))
        self.Text(p, label, _tr("Winners Final"), secondary, 12)
        self.Mark(label, *TEXT_KEYS, "general.primary_color", "general.chip_radius")

        # A player chip
        chip = QRectF(24, 192, 250, 54)
        self.Box(p, chip, FillBrush(self.V("chip", "background"), chip))
        self.Mark(chip, "chip.background", "chip.text_color", "general.border_radius")
        chipText = self.C("chip", "text_color")
        x = chip.left() + 10
        if self.On("chip", "avatar_display"):
            self.Avatar(p, QPointF(x + 16, chip.center().y()), 16)
            self.Mark(QRectF(x, chip.center().y() - 16, 32, 32), "chip.avatar_display")
            x += 40
        if self.On("chip", "seed_display"):
            seed = QRectF(x, chip.top() + 9, 24, 18)
            self.Box(p, seed, primary, self.Radius(True))
            self.Text(p, seed, "3", secondary, 11)
            self.Mark(seed, "chip.seed_display", "general.primary_color", "general.chip_radius")
            x += 30
        if self.On("chip", "country_flag_display"):
            self.Mark(QRectF(x, chip.top() + 13, 15, 10), "chip.country_flag_display")
            x += self.Flag(p, x, chip.top() + 13)
        if self.On("chip", "state_flag_display"):
            p.setBrush(PICTURE)
            p.drawRect(QRectF(x, chip.top() + 13, 10, 10))
            self.Mark(QRectF(x, chip.top() + 13, 10, 10), "chip.state_flag_display")
            x += 14
        self.Text(
            p, QRectF(x, chip.top() + 6, 90, 24), "Kiyo", chipText, 16, Qt.AlignmentFlag.AlignLeft
        )
        x += QFontMetricsF(self.Font(16)).horizontalAdvance(self.Case("Kiyo")) + 8
        if self.On("chip", "losers_display"):
            badge = QRectF(x, chip.top() + 10, 20, 16)
            self.Box(p, badge, primary, self.Radius(True))
            self.Text(p, badge, "L", secondary, 10)
            self.Mark(badge, "chip.losers_display", "general.primary_color")
            x += 26
        if self.On("chip", "pronouns_display"):
            muted = QColor(chipText)
            muted.setAlphaF(0.65)
            self.Text(
                p,
                QRectF(x, chip.top() + 6, 60, 24),
                "he/him",
                muted,
                11,
                Qt.AlignmentFlag.AlignLeft,
                False,
            )
            self.Mark(QRectF(x, chip.top() + 9, 44, 18), "chip.pronouns_display")
        if self.On("chip", "social_media_display"):
            muted = QColor(chipText)
            muted.setAlphaF(0.7)
            left = chip.left() + (50 if self.On("chip", "avatar_display") else 10)
            self.Text(
                p,
                QRectF(left, chip.top() + 30, 150, 18),
                "@kiyo",
                muted,
                11,
                Qt.AlignmentFlag.AlignLeft,
                False,
            )
            self.Mark(QRectF(left, chip.top() + 31, 44, 16), "chip.social_media_display")

    def BracketSet(self, p, rect, top, bottom, winner, letter=None, opacity=1.0):
        p.save()
        p.setOpacity(opacity)
        rowH = rect.height() / 2
        nameBrush = FillBrush(self.V("chip", "background"), rect)
        scoreW = 30
        clip = QPainterPath()
        clip.addRoundedRect(rect, self.Radius(), self.Radius())
        p.setClipPath(clip, Qt.ClipOperation.IntersectClip)
        textColor = self.C("chip", "text_color")
        for i, (name, score) in enumerate((top, bottom)):
            row = QRectF(rect.left(), rect.top() + i * rowH, rect.width(), rowH)
            lost = winner is not None and i != winner
            p.save()
            if lost and self.On("bracket", "dim_losers"):
                p.setOpacity(opacity * 0.45)
            p.fillRect(QRectF(row.left(), row.top(), row.width() - scoreW, rowH), nameBrush)
            scoreRect = QRectF(row.right() - scoreW, row.top(), scoreW, rowH)
            p.fillRect(scoreRect, FillBrush(self.V("bracket", "score_background"), scoreRect))
            self.Mark(scoreRect, "bracket.score_background")
            if winner == i:
                self.Mark(scoreRect, "bracket.winner_color")
            if lost:
                self.Mark(row, "bracket.dim_losers")
            x = row.left() + 6
            pending = name is None
            if not pending and self.On("bracket", "avatar_display"):
                self.Avatar(p, QPointF(x + 7, row.center().y()), 7)
                self.Mark(QRectF(x, row.center().y() - 7, 14, 14), "bracket.avatar_display")
                x += 18
            if not pending and self.On("bracket", "character_display"):
                p.setBrush(PICTURE_DARK)
                p.drawRect(QRectF(x, row.center().y() - 7, 14, 14))
                self.Mark(QRectF(x, row.center().y() - 7, 14, 14), "bracket.character_display")
                x += 18
            if not pending and self.On("bracket", "country_flag_display"):
                self.Mark(QRectF(x, row.center().y() - 4, 12, 8), "bracket.country_flag_display")
                x += self.Flag(p, x, row.center().y() - 4, 8)
            if not pending and self.On("bracket", "state_flag_display"):
                p.setBrush(PICTURE)
                p.drawRect(QRectF(x, row.center().y() - 4, 8, 8))
                self.Mark(QRectF(x, row.center().y() - 4, 8, 8), "bracket.state_flag_display")
                x += 12
            if not pending and self.On("bracket", "seed_display"):
                muted = QColor(textColor)
                muted.setAlphaF(0.6)
                self.Text(
                    p,
                    QRectF(x, row.top(), 14, rowH),
                    str(i + 2),
                    muted,
                    10,
                    Qt.AlignmentFlag.AlignLeft,
                    False,
                )
                self.Mark(QRectF(x - 1, row.center().y() - 7, 10, 14), "bracket.seed_display")
                x += 14
            if pending:
                if self.On("bracket", "pending_display"):
                    muted = QColor(textColor)
                    muted.setAlphaF(0.55)
                    self.Text(
                        p,
                        QRectF(x, row.top(), row.width() - scoreW - 12, rowH),
                        _tr("Winner of B"),
                        muted,
                        11,
                        Qt.AlignmentFlag.AlignLeft,
                        False,
                    )
                    self.Mark(QRectF(x, row.top() + 4, 90, rowH - 8), "bracket.pending_display")
            else:
                self.Text(
                    p,
                    QRectF(x, row.top(), row.right() - scoreW - x - 4, rowH),
                    name,
                    textColor,
                    14,
                    Qt.AlignmentFlag.AlignLeft,
                )
            scoreColor = self.C("bracket", "winner_color") if winner == i else textColor
            self.Text(p, scoreRect, score, scoreColor, 15)
            p.restore()
        p.restore()
        self.Mark(rect, "chip.background", "chip.text_color", "general.border_radius")
        if opacity < 1:
            self.Mark(rect, "bracket.focus_dim")
        if letter and self.On("bracket", "identifier_display"):
            self.Mark(
                QRectF(rect.left() - 16, rect.top() + 4, 14, 20), "bracket.identifier_display"
            )
            muted = QColor(self.C("general", "text_color"))
            muted.setAlphaF(0.6)
            self.Text(
                p,
                QRectF(rect.left() - 16, rect.top(), 14, rect.height()),
                letter,
                muted,
                11,
                Qt.AlignmentFlag.AlignRight,
            )

    def DrawBracket(self, p):
        primary = self.C("general", "primary_color")
        if self.On("bracket", "round_names_display"):
            self.Text(
                p,
                QRectF(32, 14, 180, 20),
                _tr("Winners Semis"),
                primary,
                12,
                Qt.AlignmentFlag.AlignLeft,
            )
            self.Text(
                p,
                QRectF(276, 14, 180, 20),
                _tr("Winners Final"),
                primary,
                12,
                Qt.AlignmentFlag.AlignLeft,
            )
            for x in (32, 276):
                self.Mark(QRectF(x, 14, 110, 20), "bracket.round_names_display")
        a = QRectF(32, 42, 180, 64)
        b = QRectF(32, 162, 180, 64)
        final = QRectF(272, 102, 180, 64)

        lines = self.C("bracket", "lines_color")
        p.setPen(QPen(lines, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        mid = (a.right() + final.left()) / 2
        for rect in (a, b):
            p.drawLine(QPointF(rect.right(), rect.center().y()), QPointF(mid, rect.center().y()))
        p.drawLine(QPointF(mid, a.center().y()), QPointF(mid, b.center().y()))
        p.drawLine(QPointF(mid, final.center().y()), QPointF(final.left(), final.center().y()))
        self.Mark(
            QRectF(
                a.right(), a.center().y(), final.left() - a.right(), b.center().y() - a.center().y()
            ),
            "bracket.lines_color",
        )

        dim = self.values["bracket"]["focus_dim"] / 100
        self.BracketSet(p, b, ("Vale", "2"), ("Marlow", "3"), 1, "B", dim)
        self.BracketSet(p, final, ("Kiyo", "-"), (None, "-"), None, "C", dim)
        self.BracketSet(p, a, ("Kiyo", "3"), ("Rook", "1"), 0, "A")
        if self.On("bracket", "focus_glow_sets"):
            color = (
                self.values["bracket"]["focus_glow_color_sets"]
                if self.On("bracket", "focus_glow_custom_sets")
                else self.values["bracket"]["focus_color"]
            )
            self.Glow(p, a.adjusted(-2, -2, 2, 2), QColor(color))
        self.Mark(a.adjusted(-4, -4, 4, 4), "bracket.focus_color", *GLOW_KEYS)
        if self.On("bracket", "focus_label_display"):
            caption = QRectF(WIDTH - 172, HEIGHT - 40, 150, 24)
            self.Box(p, caption, self.C("general", "secondary_color"), self.Radius(True))
            self.Text(p, caption, _tr("Set A"), primary, 12)
            self.Mark(caption, "bracket.focus_label_display")

    def DrawStageStrike(self, p):
        primary = self.C("general", "primary_color")
        secondary = self.C("general", "secondary_color")
        text = self.C("general", "text_color")
        self.Text(p, QRectF(0, 14, WIDTH, 26), _tr("Game 2 · Strike"), primary, 16)
        self.Mark(QRectF(WIDTH / 2 - 90, 14, 180, 26), "general.primary_color", *TEXT_KEYS)
        names = ["Battlefield", "Final Dest.", "Town", "Smashville", "Pokémon St."]
        w, gap = 80, 10
        x0 = (WIDTH - (5 * w + 4 * gap)) / 2
        for i, name in enumerate(names):
            tile = QRectF(x0 + i * (w + gap), 70, w, 120)
            gradient = QLinearGradient(tile.topLeft(), tile.bottomRight())
            gradient.setColorAt(0, PICTURE)
            gradient.setColorAt(1, PICTURE_DARK)
            self.Box(p, tile, QBrush(gradient))
            if i < 2:
                self.Box(p, tile, self.C("stage_strike", "striked_color"))
                self.Mark(tile, "stage_strike.striked_color")
                if self.On("stage_strike", "striker_display"):
                    self.Text(
                        p,
                        QRectF(tile.left(), tile.top() + 8, w, 16),
                        "Kiyo",
                        self.C("teams", "team1_color"),
                        11,
                    )
                    self.Mark(
                        QRectF(tile.left() + 16, tile.top() + 8, w - 32, 16),
                        "stage_strike.striker_display",
                    )
            if i == 3:
                p.setPen(QPen(self.C("stage_strike", "selected_color"), 3))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(tile.adjusted(1.5, 1.5, -1.5, -1.5), self.Radius(), self.Radius())
                self.Mark(tile, "stage_strike.selected_color")
            if self.On("stage_strike", "stage_names_display"):
                strip = QRectF(tile.left(), tile.bottom() - 24, w, 24)
                p.save()
                clip = QPainterPath()
                clip.addRoundedRect(tile, self.Radius(), self.Radius())
                p.setClipPath(clip, Qt.ClipOperation.IntersectClip)
                p.fillRect(strip, secondary)
                p.restore()
                self.Text(p, strip.adjusted(3, 0, -3, 0), name, text, 10)
                self.Mark(strip, "stage_strike.stage_names_display")

    def DrawStreamQueue(self, p):
        primary = self.C("general", "primary_color")
        text = self.C("chip", "text_color")
        self.Text(
            p, QRectF(24, 14, 200, 26), _tr("Up next"), primary, 18, Qt.AlignmentFlag.AlignLeft
        )
        self.Mark(QRectF(24, 14, 100, 26), "general.primary_color", *TEXT_KEYS)
        sets = [
            ("Kiyo", "Marlow", "4:30 PM", "1"),
            ("Vale", "Rook", "4:55 PM", "2"),
            ("Juno", "Pax", "5:20 PM", "1"),
            ("Ash", "Teo", "5:45 PM", "3"),
        ]
        if not self.On("stream_queue", "first_set_display"):
            sets = sets[1:]
        count = self.values["stream_queue"]["sets_count"]
        if count:
            sets = sets[:count]
        y = 52
        for i, (left, right, eta, station) in enumerate(sets[:4]):
            row = QRectF(24, y, WIDTH - 48, 44)
            self.Box(p, row, FillBrush(self.V("chip", "background"), row))
            self.Mark(row, "chip.background", "chip.text_color", "stream_queue.sets_count")
            if i == 0:
                self.Mark(row, "stream_queue.first_set_display")
            x = row.left() + 12
            if self.On("stream_queue", "avatar_display"):
                self.Avatar(p, QPointF(x + 11, row.center().y()), 11)
                self.Mark(QRectF(x, row.center().y() - 11, 22, 22), "stream_queue.avatar_display")
                x += 28
            self.Text(
                p,
                QRectF(x, row.top(), 230, 44),
                f"{left}  vs  {right}",
                text,
                15,
                Qt.AlignmentFlag.AlignLeft,
            )
            if self.On("stream_queue", "avatar_display"):
                self.Avatar(p, QPointF(x + 220, row.center().y()), 11)
                self.Mark(
                    QRectF(x + 209, row.center().y() - 11, 22, 22), "stream_queue.avatar_display"
                )
            details = []
            if self.On("stream_queue", "station_display"):
                details.append(_tr("Station {0}").format(station))
            if self.On("stream_queue", "eta_display"):
                details.append(eta)
            if details:
                self.Text(
                    p,
                    QRectF(row.right() - 170, row.top(), 158, 44),
                    "  ·  ".join(details),
                    primary,
                    12,
                    Qt.AlignmentFlag.AlignRight,
                    False,
                )
                self.Mark(
                    QRectF(row.right() - 150, row.top() + 10, 138, 24),
                    *(
                        (
                            ["stream_queue.station_display"]
                            if self.On("stream_queue", "station_display")
                            else []
                        )
                        + (
                            ["stream_queue.eta_display"]
                            if self.On("stream_queue", "eta_display")
                            else []
                        )
                    ),
                )
            y += 52

    def DrawStandings(self, p):
        primary = self.C("general", "primary_color")
        secondary = self.C("general", "secondary_color")
        text = self.C("chip", "text_color")
        columns = []
        if self.On("standings", "points_display"):
            columns.append((_tr("Pts"), ["9", "6", "6", "3", "0"], "standings.points_display"))
        if self.On("standings", "game_diff_display"):
            columns.append(
                (_tr("Diff"), ["+6", "+2", "+1", "-3", "-6"], "standings.game_diff_display")
            )
        if self.On("standings", "buchholz_display"):
            columns.append(
                (_tr("Buch."), ["12", "15", "9", "12", "9"], "standings.buchholz_display")
            )
        top = self.values["standings"]["highlight_top"]
        header = QRectF(24, 18, WIDTH - 48, 30)
        self.Box(p, header, secondary)
        self.Mark(header, "general.secondary_color")
        self.Text(
            p,
            header.adjusted(12, 0, 0, 0),
            _tr("Standings"),
            primary,
            13,
            Qt.AlignmentFlag.AlignLeft,
        )
        for i, name in enumerate(["Kiyo", "Marlow", "Vale", "Rook", "Juno"]):
            row = QRectF(24, 56 + i * 40, WIDTH - 48, 34)
            self.Box(p, row, FillBrush(self.V("chip", "background"), row))
            self.Mark(row, "chip.background", "chip.text_color")
            highlighted = i < top
            if highlighted:
                self.Mark(row, "standings.highlight_top")
            if highlighted:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(primary)
                p.drawRect(QRectF(row.left(), row.top(), 5, row.height()))
            self.Text(
                p,
                QRectF(row.left() + 14, row.top(), 24, 34),
                str(i + 1),
                primary if highlighted else text,
                13,
            )
            self.Text(
                p,
                QRectF(row.left() + 46, row.top(), 160, 34),
                name,
                text,
                14,
                Qt.AlignmentFlag.AlignLeft,
            )
            for j, (label, values, key) in enumerate(reversed(columns)):
                cell = QRectF(row.right() - 60 * (j + 1), row.top(), 52, 34)
                self.Mark(cell, key)
                self.Text(p, cell, values[i], text, 13, Qt.AlignmentFlag.AlignRight, False)
                if i == 0:
                    self.Text(
                        p,
                        QRectF(cell.left(), header.top(), 52, 30),
                        label,
                        primary,
                        11,
                        Qt.AlignmentFlag.AlignRight,
                    )

    def DrawVersus(self, p):
        text = self.C("general", "text_color")
        primary = self.C("general", "primary_color")
        for i, (name, sponsor) in enumerate((("Kiyo", "TSM"), ("Marlow", "LG"))):
            team = self.C("teams", f"team{i + 1}_color")
            half = QRectF(i * WIDTH / 2, 0, WIDTH / 2, HEIGHT)
            gradient = QLinearGradient(half.topLeft(), half.bottomLeft())
            gradient.setColorAt(0, team)
            gradient.setColorAt(1, team.darker(220))
            p.save()
            p.setOpacity(0.85)
            p.fillRect(half, QBrush(gradient))
            p.restore()
            self.Mark(half, f"teams.team{i + 1}_color")
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(PICTURE_DARK)
            p.drawEllipse(QPointF(half.center().x(), 105), 52, 52)
            if (
                self.On("versus", "custom_sponsor_colors")
                and self.values["general"]["apply_colors"]
            ):
                sponsorColor = self.C("versus", f"team{i + 1}_sponsor_color")
            else:
                sponsorColor = team.lighter(160)
            sponsorFont = QFontMetricsF(self.Font(20)).horizontalAdvance(self.Case(sponsor) + " ")
            nameWidth = QFontMetricsF(self.Font(26)).horizontalAdvance(self.Case(name))
            left = half.center().x() - (sponsorFont + nameWidth) / 2
            self.Text(
                p,
                QRectF(left, 180, sponsorFont, 40),
                sponsor,
                sponsorColor,
                20,
                Qt.AlignmentFlag.AlignLeft,
            )
            self.Mark(
                QRectF(left, 186, sponsorFont - 4, 28),
                "versus.custom_sponsor_colors",
                f"versus.team{i + 1}_sponsor_color",
            )
            self.Text(
                p,
                QRectF(left + sponsorFont, 178, nameWidth + 4, 44),
                name,
                text,
                26,
                Qt.AlignmentFlag.AlignLeft,
            )
        badge = QRectF(WIDTH / 2 - 28, 86, 56, 40)
        self.Box(p, badge, self.C("general", "secondary_color"), self.Radius(True))
        self.Text(p, badge, "VS", primary, 22)
        self.Mark(badge, "general.primary_color", "general.secondary_color", "general.chip_radius")
