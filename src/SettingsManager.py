import os
import threading
import time

import orjson
from loguru import logger

from .Helpers.DictHelper import *


class SettingsManager:
    PATH = "./user_data/settings.json"
    # The names of the files kept next to it start with "settings.json" too:
    # the web server refuses to serve those (they hold the API keys)
    TEMP_PATH = PATH + ".tmp"
    BROKEN_PATH = PATH + ".broken"

    settings = {}
    load_error: str | None = None
    first_launch = False

    # Set() is called from the GUI and from the web server's threads. Held
    # while the settings change and while they're written, so writes can't
    # overlap or land out of order. Get() doesn't take it: it only reads
    # dicts, and must not wait for a write to the disk.
    lock = threading.RLock()

    # True when settings.json couldn't be read and couldn't be moved aside
    # either: it's then never written to, as that would replace what may be
    # the user's only copy of their settings with nearly empty ones.
    save_disabled = False

    # Settings of removed features, dropped from settings.json on load.
    # bsky_account held a Bluesky app password in plain text.
    REMOVED_KEYS = [
        "bsky_account",
        "thumbnail_config",
        "general.disable_thumbnail_widget",
        "hotkeys",
    ]

    @staticmethod
    def SaveSettings():
        with SettingsManager.lock:
            if SettingsManager.save_disabled:
                return
            encoded = orjson.dumps(
                SettingsManager.settings, option=orjson.OPT_NON_STR_KEYS | orjson.OPT_INDENT_2
            )
            SettingsManager._Write(encoded)

    @staticmethod
    def _Write(encoded: bytes):
        """Writes to a temp file which then replaces settings.json, so a crash
        (or an error) while writing leaves the previous settings in place
        instead of a truncated file."""
        path, temp = SettingsManager.PATH, SettingsManager.TEMP_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(temp, "wb") as file:
            file.write(encoded)
            file.flush()
            try:
                os.fsync(file.fileno())
            except OSError:
                pass

        # On Windows the replace fails while another program (an editor, an
        # antivirus, a backup tool) has settings.json open
        for attempt in range(3):
            try:
                os.replace(temp, path)
                return
            except PermissionError:
                time.sleep(0.05)

        # Still open elsewhere: written in place, which is what used to be
        # done on every save. The temp file is only removed once that worked.
        with open(path, "wb") as file:
            file.write(encoded)
        try:
            os.remove(temp)
        except OSError:
            pass

    @staticmethod
    def _KeepBroken():
        """Moves a settings.json that couldn't be loaded out of the way, and
        returns where to (None if it couldn't be moved). Earlier broken files
        are kept: one of them may be the one with the user's settings."""
        dest = SettingsManager.BROKEN_PATH
        number = 1
        while os.path.exists(dest):
            number += 1
            dest = f"{SettingsManager.BROKEN_PATH}.{number}"
        try:
            os.replace(SettingsManager.PATH, dest)
            return dest
        except OSError as e:
            logger.error(f"Couldn't move {SettingsManager.PATH} to {dest}: {e}")
            return None

    @staticmethod
    def LoadSettings():
        with SettingsManager.lock:
            SettingsManager.load_error = None
            SettingsManager.save_disabled = False
            try:
                with open(SettingsManager.PATH, "rb") as file:
                    settings = orjson.loads(file.read())
                if not isinstance(settings, dict):
                    raise ValueError(f"Expected an object, found a {type(settings).__name__}")
                SettingsManager.settings = settings
            except FileNotFoundError:
                SettingsManager.settings = {}
            except Exception as e:
                SettingsManager.settings = {}
                error = f"{SettingsManager.PATH}\n\n{e}\n\n"
                # A file that can't even be read (permissions, a locked file)
                # isn't broken, and is left where it is
                kept = None if isinstance(e, OSError) else SettingsManager._KeepBroken()
                if kept:
                    error += (
                        f"The file was kept as {kept}. HyperDrive starts with its default settings."
                    )
                else:
                    SettingsManager.save_disabled = True
                    error += (
                        "The file was left as it is: HyperDrive starts with its default "
                        "settings, and the changes made to them won't be saved."
                    )
                logger.error(error)
                SettingsManager.load_error = error
                return

            removed = [
                k
                for k in SettingsManager.REMOVED_KEYS
                if deep_get(SettingsManager.settings, k) is not None
            ]
            for key in removed:
                deep_unset(SettingsManager.settings, key)
            if removed:
                SettingsManager._SaveSafely()

    @staticmethod
    def _SaveSafely():
        # Called through the class, so the tests can replace SaveSettings
        try:
            SettingsManager.SaveSettings()
        except Exception as e:
            # The setting is changed in memory and saved with the next one;
            # the widget that changed it must not fail over a full disk.
            logger.error(f"Couldn't save {SettingsManager.PATH}: {e}")

    @staticmethod
    def Set(key: str, value):
        with SettingsManager.lock:
            deep_set(SettingsManager.settings, key, value)
            SettingsManager._SaveSafely()

    @staticmethod
    def Unset(key: str):
        with SettingsManager.lock:
            deep_unset(SettingsManager.settings, key)
            SettingsManager._SaveSafely()

    @staticmethod
    def Get(key: str, default=None):
        return deep_get(SettingsManager.settings, key, default)


# No settings yet: HyperDrive is running for the first time (the guide opens
# on its Getting Started page)
SettingsManager.first_launch = not os.path.isfile(SettingsManager.PATH)
if SettingsManager.first_launch:
    SettingsManager._SaveSafely()

SettingsManager.LoadSettings()
