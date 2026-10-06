import json

from qtpy import uic
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .Helpers.TSHDirHelper import TSHResolve

REPOSITORY_URL = "https://github.com/Voidscape-Development/HyperDrive"


class TSHAboutWidget(QDialog):
    def __init__(self, *args):
        super().__init__(*args)
        uic.loadUi(TSHResolve("src/layout/TSHAbout.ui"), self)

        try:
            version = json.load(open(TSHResolve("assets/versions.json"), encoding="utf-8")).get(
                "program", "?"
            )
        except Exception as e:
            version = "?"

        self.findChild(QLabel, "title").setText(f"HyperDrive v{version}")

        try:
            icon = QPixmap("./assets/icons/icon.png").scaledToWidth(128)
        except:
            icon = QPixmap()

        self.findChild(QLabel, "icon").setPixmap(icon)

        links = [
            (QApplication.translate("About", "Source code"), REPOSITORY_URL),
            (QApplication.translate("About", "Releases"), f"{REPOSITORY_URL}/releases"),
            (QApplication.translate("About", "Report an issue"), f"{REPOSITORY_URL}/issues"),
        ]
        self.findChild(QLabel, "links").setText(
            " · ".join(f'<a href="{url}">{text}</a>' for text, url in links)
        )
