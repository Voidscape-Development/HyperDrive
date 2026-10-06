import locale
import os
import traceback

from loguru import logger
from qtpy.QtCore import *

# One pronoun per line. The player widgets suggest these as you type.
PRONOUNS_FILE = "./user_data/pronouns_list.txt"


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
        return PronounHelper.model

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
