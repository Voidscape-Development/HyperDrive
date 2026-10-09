import platform
import traceback

import pynput
from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .Helpers.DictHelper import deep_clone
from .SettingsManager import SettingsManager


class HotkeysSignals(QObject):
    team1_score_up = Signal()
    team1_score_down = Signal()
    team2_score_up = Signal()
    team2_score_down = Signal()
    reset_scores = Signal()
    load_set = Signal()
    swap_teams = Signal()
    refresh_phase_group = Signal()
    limit_export = Signal()
    bracket_focus_all = Signal()
    bracket_focus_previous_round = Signal()
    bracket_focus_next_round = Signal()
    bracket_focus_follow = Signal()
    bracket_focus_tour = Signal()


class Hotkeys(QObject):
    instance: "Hotkeys" = None
    signals = HotkeysSignals()
    parent: QWidget = None
    shortcuts = {}

    keys = {
        "load_set": "Ctrl+O",
        "team1_score_up": "Ctrl+F1",
        "team1_score_down": "Ctrl+F2",
        "team2_score_up": "Ctrl+F3",
        "team2_score_down": "Ctrl+F4",
        "reset_scores": "Ctrl+R",
        "swap_teams": "Ctrl+S",
        "refresh_phase_group": "Ctrl+P",
        "limit_export": "Ctrl+B",
        "bracket_focus_all": "Ctrl+F5",
        "bracket_focus_previous_round": "Ctrl+F6",
        "bracket_focus_next_round": "Ctrl+F7",
        "bracket_focus_follow": "Ctrl+F8",
        "bracket_focus_tour": "Ctrl+F9",
    }

    loaded_keys = {}

    pynputListener = None

    def __init__(self) -> None:
        super().__init__()
        self.LoadUserHotkeys()

    def UiMounted(self, parent):
        self.parent = parent
        self.SetupHotkeys()

    def ReloadHotkeys(self):
        self.LoadUserHotkeys()
        self.SetupHotkeys()

    def SetupHotkeys(self):
        if self.pynputListener:
            self.pynputListener.stop()

        shortcuts = {}

        for key, value in self.loaded_keys.items():
            pynputShortcut = Hotkeys.qshortcut_to_pynput(value)

            if pynputShortcut != None and pynputShortcut != "":
                shortcuts[pynputShortcut] = lambda key=key, value=value: self.HotkeyTriggered(
                    key, value
                )

        self.pynputListener = pynput.keyboard.GlobalHotKeys(shortcuts)

        if platform.system() == "Darwin":
            logger.error("macOS detected, deactivating hotkeys for now")
            return

        self.pynputListener.start()

    def HotkeyTriggered(self, k, v):
        if SettingsManager.Get("hotkeys.hotkeys_enabled", True):
            logger.info(f"Activated {k} by pressing {v}")
            getattr(self.signals, k).emit()

    def LoadUserHotkeys(self):
        user_keys = SettingsManager.Get("hotkeys", {})
        self.loaded_keys = deep_clone(self.keys)

        # Update keys
        self.loaded_keys.update((k, v) for k, v in user_keys.items() if k in self.keys)

        logger.info("User hotkeys loaded")

    def qshortcut_to_pynput(qshortcut_str):
        try:
            qshortcut_str = qshortcut_str.lower()

            parts = qshortcut_str.split("+")

            for i, part in enumerate(parts):
                if len(parts[i]) > 1:
                    if parts[i] not in ("ctrl", "shift", "alt"):
                        key = getattr(pynput.keyboard.Key, parts[i])
                        parts[i] = f"{key.value.vk}"

                    parts[i] = f"<{parts[i]}>"

            return "+".join(parts)
        except:
            logger.error(f"Could not convert qshortcut {qshortcut_str} to pynput")
            logger.error(traceback.format_exc())
            return None


Hotkeys.instance = Hotkeys()
