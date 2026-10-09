import locale
import os
import traceback

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtWidgets import *

# One pronoun per line. The player widgets suggest these as you type.
PRONOUNS_FILE = "./user_data/pronouns_list.txt"

# Added to the list once, so there's something to pick from the start.
# Removing them afterwards sticks.
DEFAULT_PRONOUNS = [
    "he/him",
    "she/her",
    "they/them",
    "he/they",
    "she/they",
    "they/he",
    "they/she",
    "any/all",
    "it/its",
    "xe/xem",
]
DEFAULTS_ADDED_SETTING = "pronouns.defaults_added"


def NormalizePronouns(pronouns) -> list[str]:
    """Strips the pronouns and removes empty ones and duplicates, keeping the order"""
    return list(dict.fromkeys(p.strip() for p in pronouns if isinstance(p, str) and p.strip()))


class PronounHelper:
    # Shared by every pronoun completer, so a change shows up everywhere
    model: QStringListModel = None

    def Model() -> QStringListModel:
        if PronounHelper.model is None:
            PronounHelper.model = QStringListModel()
            PronounHelper.model.setStringList(PronounHelper.Load())
            PronounHelper.AddDefaults()
        return PronounHelper.model

    def AddDefaults():
        """Adds the default pronouns the first time the list is loaded"""
        # Imported here, so the helper can be used without the settings
        from ..SettingsManager import SettingsManager

        if SettingsManager.Get(DEFAULTS_ADDED_SETTING, False):
            return
        pronouns = PronounHelper.model.stringList()
        if PronounHelper.Save(pronouns + DEFAULT_PRONOUNS):
            SettingsManager.Set(DEFAULTS_ADDED_SETTING, True)

    def Load() -> list[str]:
        if not os.path.isfile(PRONOUNS_FILE):
            try:
                with open(PRONOUNS_FILE, "w", encoding="utf-8"):
                    logger.info(f"creating {PRONOUNS_FILE}")
            except:
                logger.error(traceback.format_exc())
            return []

        # Older versions wrote the file in the system's encoding
        for encoding in ["utf-8", locale.getpreferredencoding(False)]:
            try:
                with open(PRONOUNS_FILE, encoding=encoding) as f:
                    return NormalizePronouns(f.read().splitlines())
            except UnicodeDecodeError:
                continue
            except:
                logger.error(traceback.format_exc())
                break
        return []

    def Save(pronouns) -> bool:
        pronouns = NormalizePronouns(pronouns)
        try:
            with open(PRONOUNS_FILE, "w", encoding="utf-8") as f:
                f.writelines(p + "\n" for p in pronouns)
        except:
            logger.error(traceback.format_exc())
            return False

        model = PronounHelper.Model()
        if model.stringList() != pronouns:
            model.setStringList(pronouns)
        return True

    def Add(pronoun: str):
        """Adds a pronoun to the list if it isn't there yet"""
        pronouns = PronounHelper.Model().stringList()
        if pronoun and pronoun.strip() and pronoun.strip() not in pronouns:
            PronounHelper.Save(pronouns + [pronoun])

    def SetupField(lineEdit: QLineEdit):
        """Makes a pronoun field an editable dropdown: an arrow lists every
        pronoun, and typing suggests the matching ones or a new pronoun"""
        # Imported here, so the helper can be used without the theme
        from ..Theme import ThemedIcon
        from .QtHelper import OnFirstFocus

        completer = QCompleter(PronounHelper.Model(), lineEdit)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(12)
        # The field can be narrow; the list shouldn't cut the pronouns off.
        # Set once the field is used, so the list isn't created for every card
        OnFirstFocus([lineEdit], lambda: completer.popup().setMinimumWidth(140))
        lineEdit.setCompleter(completer)
        # Picking a pronoun saves it right away, like a combo box would
        completer.activated[str].connect(lambda text: lineEdit.editingFinished.emit())

        def ShowAll():
            lineEdit.setFocus()
            completer.setCompletionPrefix("")
            completer.complete()

        action = lineEdit.addAction(
            ThemedIcon("./assets/icons/chevron_down.svg"),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        action.setToolTip(QApplication.translate("app", "Show all pronouns"))
        action.triggered.connect(ShowAll)
        return completer
