import json

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .DirHelper import ResolvePath

# GitHub repository ("owner/name") HyperDrive is published from. Unset until
# the project moves to its new repository, which leaves the updater and the
# alerts feed as stubs: no releases or alerts are fetched.
REPOSITORY = None

# Where HyperDrive's source, releases and issues are, for the About dialog
# and the Help menu
PROJECT_URL = "https://github.com/Voidscape-Development/HyperDrive"


def get_beta_status(feature):
    try:
        versions = json.load(open(ResolvePath("./assets/versions.json"), encoding="utf-8"))
    except Exception as e:
        logger.error("Local version file not found")
        versions = {}

    return feature in versions.get("beta_features", [])


def add_beta_label(text, feature):
    if get_beta_status(feature):
        beta_label = (
            str(QApplication.translate("punctuation", "["))
            + str(QApplication.translate("app", "beta")).upper()
            + str(QApplication.translate("punctuation", "]"))
        )
        if str(QApplication.translate("punctuation", "]")) == "]":
            return beta_label + " " + text
        else:
            return beta_label + text
    else:
        return text


def get_supported_providers():
    try:
        versions = json.load(open(ResolvePath("./assets/versions.json"), encoding="utf-8"))
    except Exception as e:
        logger.error("Local version file not found")
        versions = {}

    return versions.get("supported_providers", [])
