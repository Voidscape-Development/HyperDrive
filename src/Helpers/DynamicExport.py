import os
import re
import threading

import orjson
from loguru import logger

from ..Scheduler import Scheduler
from ..SettingsManager import SettingsManager
from ..StateManager import StateManager


class DynamicExport:
    """Exports the files in a person's folder in user_data/custom_player_export/
    to `<path>.custom`, for layouts to show (see docs/layout-data.md).

    A person's folder is named after their tag, or their sponsor and tag
    ("TEAM Tag"), in any case. Each file is exported by its name without
    the extension: text files as their contents, .json files as what they
    hold, anything else (images, videos...) as its path.
    """

    BASE_DIR = "./user_data/custom_player_export"
    SETTING = "general.custom_player_export"
    # Scheduler job that checks the folders for changes
    JOB = "custom_player_export"
    # How often the folders are checked for changes while enabled
    POLL_INTERVAL_MS = 1000

    TEXT_EXTENSIONS = (".txt", ".csv", ".xml", ".html", ".md")
    # Files the OS puts in folders
    IGNORED_FILES = ("desktop.ini", "thumbs.db")

    # Ordered after a widget's dataLock and before StateManager.lock
    lock = threading.RLock()
    # Path -> (tag, sponsor) of the person exported there
    _people: dict[str, tuple[str, str]] = {}
    # Path -> the folder and files last exported there, to tell when they change
    _signatures: dict[str, tuple] = {}

    def Enabled() -> bool:
        return SettingsManager.Get(DynamicExport.SETTING, True)

    def SettingChanged():
        """Starts or stops checking the folders for changes, as the setting
        says, and exports the custom data again, or clears it when disabled."""
        scheduler = Scheduler.instance
        if DynamicExport.JOB not in scheduler.jobs:
            scheduler.Register(
                DynamicExport.JOB,
                lambda done: [DynamicExport.Refresh(), done()],
                DynamicExport.POLL_INTERVAL_MS,
            )
        if DynamicExport.Enabled():
            scheduler.Start(DynamicExport.JOB)
        elif scheduler.IsEnabled(DynamicExport.JOB):
            scheduler.Stop(DynamicExport.JOB)
        DynamicExport.Refresh(force=True)

    def ExportCustomPlayerData(name: str, team: str, path: str):
        """Exports the custom data of the person now at path, and keeps it
        up to date while their files change."""
        with DynamicExport.lock:
            DynamicExport._people[path] = (name, team)
            DynamicExport._Export(path, DynamicExport._Folders(), force=True)

    def Refresh(force=False):
        """Exports again the custom data whose files changed since it was
        exported (or all of it, with force), e.g. on a timer."""
        with DynamicExport.lock:
            if not DynamicExport._people:
                return
            folders = DynamicExport._Folders()
            for path in list(DynamicExport._people):
                # Unset when its widget is removed
                if StateManager.Get(path) is None:
                    DynamicExport._people.pop(path, None)
                    DynamicExport._signatures.pop(path, None)
                    continue
                DynamicExport._Export(path, folders, force=force)

    def _Sanitize(name: str) -> str:
        return re.sub(r"[,/|;:<>\\?*]", "_", name).strip().upper()

    def _Folders() -> dict[str, str]:
        """The people's folders, by sanitized upper case name"""
        folders = {}
        if not DynamicExport.Enabled() or not os.path.isdir(DynamicExport.BASE_DIR):
            return folders
        try:
            for entry in os.scandir(DynamicExport.BASE_DIR):
                if entry.is_dir():
                    folders[DynamicExport._Sanitize(entry.name)] = (
                        f"{DynamicExport.BASE_DIR}/{entry.name}"
                    )
        except OSError as e:
            logger.warning(f"Could not read {DynamicExport.BASE_DIR}: {e}")
        return folders

    def _MatchFolder(name: str, team: str, folders: dict[str, str]) -> str | None:
        if not name.strip():
            return None
        # The tag first, so a sponsor change doesn't lose the player's folder
        candidates = [name]
        if team.strip():
            candidates.append(f"{team} {name}")
        for candidate in candidates:
            folder = folders.get(DynamicExport._Sanitize(candidate))
            if folder is not None:
                return folder
        return None

    def _Files(folder: str) -> list[os.DirEntry]:
        try:
            entries = [
                e
                for e in os.scandir(folder)
                if e.is_file()
                and not e.name.startswith(".")
                and e.name.lower() not in DynamicExport.IGNORED_FILES
            ]
        except OSError as e:
            logger.warning(f"Could not read {folder}: {e}")
            return []
        return sorted(entries, key=lambda e: e.name.lower())

    def _Export(path: str, folders: dict[str, str], force=False):
        name, team = DynamicExport._people[path]
        folder = DynamicExport._MatchFolder(name, team, folders)
        files = DynamicExport._Files(folder) if folder else []

        signature = []
        for entry in files:
            try:
                stat = entry.stat()
            except OSError:
                continue
            signature.append((entry.name, stat.st_mtime_ns, stat.st_size))
        signature = (folder, tuple(signature))

        if not force and DynamicExport._signatures.get(path) == signature:
            return
        DynamicExport._signatures[path] = signature

        custom = {}
        for entry in files:
            stem, ext = os.path.splitext(entry.name)
            # State paths are split on dots
            key = stem.strip().replace(".", "_")
            if not key:
                continue
            if key in custom:
                logger.warning(f"{folder}: more than one file is named {key}, keeping the first")
                continue
            value = DynamicExport._Value(entry, ext.lower(), folder)
            if value is not None:
                custom[key] = value

        key = f"{path}.custom"
        if custom:
            if StateManager.Get(key) != custom:
                StateManager.Set(key, custom)
        elif StateManager.Get(key) is not None:
            StateManager.Unset(key)

    def _Value(entry: os.DirEntry, ext: str, folder: str):
        if ext == ".json":
            try:
                with open(entry.path, "rb") as f:
                    return orjson.loads(f.read())
            except OSError as e:
                logger.warning(f"Could not read {entry.path}: {e}")
                return None
            except orjson.JSONDecodeError as e:
                logger.warning(f"{entry.path} isn't valid JSON, exporting it as text: {e}")
                ext = ".txt"

        if ext in DynamicExport.TEXT_EXTENSIONS:
            try:
                with open(entry.path, encoding="utf-8-sig") as f:
                    value = f.read()
            except (OSError, UnicodeDecodeError) as e:
                logger.warning(f"Could not read {entry.path} as text: {e}")
                return None
            # Editors end files with a newline that layouts would show
            return value.rstrip("\r\n") if ext == ".txt" else value

        # Same form as the other paths layouts get, e.g. avatar
        return f"{folder}/{entry.name}"
