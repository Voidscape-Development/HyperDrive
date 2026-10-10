# Character icons when a game's icon pack doesn't have one for a character:
# which other installed packs to take it from, and a placeholder with the
# character's initials when none has it (rather than the "no character"
# cross, which made it look like nothing was picked).
from qtpy.QtCore import QRectF, Qt
from qtpy.QtGui import QColor, QFont, QPainter, QPalette, QPixmap
from qtpy.QtWidgets import QApplication

# Packs that don't picture the characters themselves
NON_CHARACTER_TYPES = {
    "stage_icon",
    "variant_icon",
    "stage_bg",
    "logo",
    "banner",
    "background",
}


def _Types(asset):
    types = (asset or {}).get("type") or []
    return [types] if isinstance(types, str) else list(types)


def _Rank(asset):
    types = _Types(asset)
    if any(t.startswith("icon") for t in types):
        return 0
    if "portrait" in types:
        return 1
    if any(t.startswith("full") for t in types):
        return 2
    return 3


def IconPackOrder(assets, primary):
    """The packs to look for a character's icon in: the icon pack, then the
    other installed packs picturing characters, other icons first, then
    portraits, then full art."""
    order = [primary] if primary in (assets or {}) else []
    others = [
        key
        for key, asset in (assets or {}).items()
        if key != primary
        and key != "base_files"
        and not NON_CHARACTER_TYPES.intersection(_Types(asset))
    ]
    order += sorted(others, key=lambda key: (_Rank(assets[key]), key))
    return order


def Initials(name):
    """Up to two letters standing for a character, e.g. "BL" for Baby Luigi."""
    words = [w for w in str(name or "").replace("_", " ").replace("-", " ").split() if w]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def PlaceholderPixmap(name, width, height=None):
    """A tile with the character's initials, for characters without an icon."""
    height = height or width
    ratio = QApplication.instance().devicePixelRatio() if QApplication.instance() else 1
    pixmap = QPixmap(int(width * ratio), int(height * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)

    palette = QApplication.palette()
    background = QColor(palette.color(QPalette.ColorRole.Mid))
    background.setAlphaF(0.35)
    text = palette.color(QPalette.ColorRole.Text)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    rect = QRectF(1, 1, width - 2, height - 2)
    radius = min(width, height) * 0.18
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(background)
    painter.drawRoundedRect(rect, radius, radius)

    font = QFont(painter.font())
    font.setBold(True)
    font.setPixelSize(max(6, int(min(width, height) * 0.4)))
    painter.setFont(font)
    painter.setPen(text)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, Initials(name))
    painter.end()
    return pixmap
