from qtpy import uic
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .Helpers.DirHelper import ResolvePath
from .Helpers.VersionHelper import PROJECT_URL, get_program_version


class AboutWidget(QDialog):
    def __init__(self, *args):
        super().__init__(*args)
        uic.loadUi(ResolvePath("src/layout/About.ui"), self)

        self.findChild(QLabel, "title").setText(f"HyperDrive v{get_program_version()}")

        try:
            icon = QPixmap("./assets/icons/icon.png").scaledToWidth(128)
        except:
            icon = QPixmap()

        self.findChild(QLabel, "icon").setPixmap(icon)

        links = [
            (QApplication.translate("About", "Source code"), PROJECT_URL),
            (QApplication.translate("About", "Releases"), f"{PROJECT_URL}/releases"),
            (QApplication.translate("About", "Report an issue"), f"{PROJECT_URL}/issues"),
        ]
        self.findChild(QLabel, "links").setText(
            " · ".join(f'<a href="{url}">{text}</a>' for text, url in links)
        )
