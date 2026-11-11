import contextlib
import json
import os
import shutil
import threading
import time
import traceback

import orjson
import requests
from loguru import logger
from PIL import Image
from qtpy.QtCore import QCoreApplication, QObject, QThread, QTimer, Signal, Slot

from .Helpers.DictHelper import deep_clone, deep_clones, deep_get, deep_set, deep_unset
from .SettingsManager import SettingsManager


class StateManagerSignals(QObject):
    state_big_change = Signal()
    state_updated = Signal(dict)


class StateManagerSaveScheduler(QObject):
    """Coalesces the saves requested by Set()/Unset() into one save.

    Lives on the GUI thread; request can be emitted from any thread.
    """

    request = Signal()

    def __init__(self):
        super().__init__()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(StateManager.SAVE_DEBOUNCE_MS)
        self.timer.timeout.connect(StateManager.FlushPendingSave)
        self.request.connect(self.Start)

    @Slot()
    def Start(self):
        # Not restarted while active, so a stream of changes can't postpone
        # the save indefinitely.
        if not self.timer.isActive():
            self.timer.start()


# The three kinds of change, named as the layouts, the web app and the Stream
# Deck plugin know them (they're the names DeepDiff gave them): the first two
# set the value at a path, the last removes the key at a path.
ADDED = "dictionary_item_added"
CHANGED = "values_changed"
REMOVED = "dictionary_item_removed"

_MISSING = object()
_SCALARS = frozenset((str, int, float, bool, type(None)))
_COMPARE_OPTIONS = orjson.OPT_NON_STR_KEYS | orjson.OPT_SORT_KEYS


def SameValue(a, b):
    """True if a and b are the same to whoever reads the state as JSON.

    == alone takes 1, 1.0 and True for equal, which they aren't in the
    exported files nor in the layouts. A tuple and a list with the same
    items are the same: both are a JSON array."""
    if a is b:
        return True
    typeA, typeB = type(a), type(b)
    if typeA in _SCALARS and typeB in _SCALARS:
        if typeA is not typeB:
            return False
        # NaN isn't equal to itself, and would be a change on every save
        return a == b or (typeA is float and a != a and b != b)
    try:
        return orjson.dumps(a, option=_COMPARE_OPTIONS) == orjson.dumps(b, option=_COMPARE_OPTIONS)
    except Exception:
        # Not JSON (an object, an int over 64 bits)
        try:
            return typeA is typeB and bool(a == b)
        except Exception:
            return False


def DiffStates(old, new, changedPaths=None, maxDelta=None, everyChange=True):
    """What turns the dict old into the dict new, as (changes, delta).

    changes has every difference as (path, action, old value, new value),
    path being a tuple of keys: a key added to (ADDED) or removed from
    (REMOVED) a dict, or a value that isn't the same (CHANGED). Only dicts
    are gone into: anything else (a list too) changes as a whole. No path in
    changes is inside another's, and where a key is removed from a dict that
    another is added to, the removal comes first (1 and "1" are the same key
    once in JSON).

    delta is changes, except that a dict with more than maxDelta changes in
    it is one change of the whole dict, (path, CHANGED, None, the dict):
    too many changes for a delta would have every client sent the whole
    state, when such a dict can be sent whole itself. Never old and new
    themselves, which have no path. When only the delta is needed,
    everyChange=False saves looking for every change in such a dict: None
    is returned for changes then.

    changedPaths limits the comparison to these paths (tuples of keys) and
    what's in them; old and new must be the same everywhere else. Without
    it, or with the empty path among them, everything is compared.
    """
    changes = []
    # The dicts with too many changes, as (where their changes start and
    # end in changes, path, dict)
    whole = []
    stop = None if everyChange else maxDelta
    if not changedPaths or () in changedPaths:
        if not (old == new and SameValue(old, new)):
            _DiffDict(old, new, (), changes, whole, maxDelta, stop)
    else:
        # Tree of the paths, None where everything from there on is compared
        tree = {}
        for path in changedPaths:
            node = tree
            for key in path[:-1]:
                child = node.get(key, _MISSING)
                if child is None:
                    break
                if child is _MISSING:
                    child = node[key] = {}
                node = child
            else:
                node[path[-1]] = None
        _DiffTree(old, new, (), tree, changes, whole, maxDelta, stop)

    if not whole:
        return (changes if everyChange else None), changes

    # From the end, where a dict comes before the dicts in it
    parts = []
    position = len(changes)
    for start, end, path, value in reversed(whole):
        if end > position:
            # In a dict that's sent whole itself
            continue
        parts.append(changes[end:position])
        parts.append([(path, CHANGED, None, value)])
        position = start
    parts.append(changes[:position])
    delta = [change for part in reversed(parts) for change in part]
    return (changes if everyChange else None), delta


def _DiffTree(old, new, path, tree, changes, whole, maxDelta, stop):
    """Compares the keys of tree in the dicts old and new. Returns how many
    changes the delta has for them, as _DiffDict does."""
    start = len(changes)
    count = 0
    for key, subtree in tree.items():
        oldValue = old.get(key, _MISSING)
        newValue = new.get(key, _MISSING)
        if newValue is _MISSING:
            if oldValue is not _MISSING:
                changes.append((path + (key,), REMOVED, oldValue, None))
                count += 1
        elif oldValue is _MISSING:
            changes.append((path + (key,), ADDED, None, newValue))
            count += 1
        elif isinstance(oldValue, dict) and isinstance(newValue, dict):
            if subtree is not None:
                count += _DiffTree(
                    oldValue, newValue, path + (key,), subtree, changes, whole, maxDelta, stop
                )
            elif not (oldValue == newValue and SameValue(oldValue, newValue)):
                count += _DiffDict(
                    oldValue, newValue, path + (key,), changes, whole, maxDelta, stop
                )
            if stop is not None and count > stop and path:
                # Sent whole, whatever else changed in it
                break
        elif not SameValue(oldValue, newValue):
            # The value at the path, or one on the way to it that isn't a
            # dict on both sides: that's what changed then, as a whole
            changes.append((path + (key,), CHANGED, oldValue, newValue))
            count += 1
    if maxDelta is not None and count > maxDelta and path:
        whole.append((start, len(changes), path, new))
        return 1
    return count


def _DiffDict(old, new, path, changes, whole, maxDelta, stop):
    """Compares every key of the dicts old and new."""
    start = len(changes)
    count = 0
    # Most dicts keep their keys, which is quicker to find out this way
    if old.keys() != new.keys():
        for key, oldValue in old.items():
            if key not in new:
                changes.append((path + (key,), REMOVED, oldValue, None))
                count += 1
    for key, newValue in new.items():
        oldValue = old.get(key, _MISSING)
        if oldValue is _MISSING:
            changes.append((path + (key,), ADDED, None, newValue))
            count += 1
        elif oldValue is newValue:
            continue
        elif type(newValue) in _SCALARS:
            # Most values: not worth a call
            if not (type(oldValue) is type(newValue) and oldValue == newValue) and not SameValue(
                oldValue, newValue
            ):
                changes.append((path + (key,), CHANGED, oldValue, newValue))
                count += 1
        elif isinstance(newValue, dict) and isinstance(oldValue, dict):
            # Both compare at C speed, which settles what didn't change (most
            # of a bracket set again with one new score) without walking it
            if not (oldValue == newValue and SameValue(oldValue, newValue)):
                count += _DiffDict(
                    oldValue, newValue, path + (key,), changes, whole, maxDelta, stop
                )
                if stop is not None and count > stop and path:
                    # Sent whole, whatever else changed in it
                    break
        elif not SameValue(oldValue, newValue):
            changes.append((path + (key,), CHANGED, oldValue, newValue))
            count += 1
    if maxDelta is not None and count > maxDelta and path:
        whole.append((start, len(changes), path, new))
        return 1
    return count


def _WithoutTuples(value):
    """value with lists for its tuples, which is what it is once saved and
    sent: they're the same to SameValue, so they're exported the same."""
    if isinstance(value, (list, tuple)):
        return [_WithoutTuples(v) for v in value]
    if isinstance(value, dict):
        return {k: _WithoutTuples(v) for k, v in value.items()}
    return value


class StateManager:
    # The state as of the last save: what the layouts and the exported files
    # have. Never shares a dict or a list with state.
    lastSavedState = {}
    state = {}
    saveBlocked = 0
    signals = StateManagerSignals()
    # Paths set or unset since the last save, as tuples of keys: only these
    # are compared with lastSavedState
    changedPaths = []
    deltaIndex = 0
    load_error: str | None = None

    # Held while the state changes and while it's saved: Set() is called from
    # worker threads too. Get() doesn't take it.
    lock = threading.RLock()
    loop = None

    # Set()/Unset() don't save right away: changes made within this window are
    # exported together in a single save.
    SAVE_DEBOUNCE_MS = 40
    savePending = False
    saveScheduler: StateManagerSaveScheduler | None = None

    # More changes than this are sent as a whole new state instead of a delta
    # (and a dict with more changes than this in it as the whole dict)
    MAX_DELTA = 100

    # Timestamp of the last 0 -> 1 transition of saveBlocked, used by the
    # watchdog to detect a BlockSaving() that never got its ReleaseSaving().
    saveBlockedSince = None

    # If saving stays blocked for longer than this (seconds) while there are
    # pending changes, we assume a block was leaked and force a save.
    DEFAULT_BLOCK_WATCHDOG_SECONDS = 30

    # State paths (as tuples of keys) whose subtrees are excluded from the out/ file export.
    # Use this for large lookup tables that are only useful as JSON (e.g. game.stages).
    EXPORT_EXCLUDED_PREFIXES = (("game", "stages"),)

    # =====================================================
    # SAVE BLOCKS
    # =====================================================
    @staticmethod
    @contextlib.contextmanager
    def SaveBlock(watchdog=True):
        StateManager.BlockSaving(watchdog=watchdog)
        try:
            yield
        finally:
            StateManager.ReleaseSaving()

    @staticmethod
    def BlockSaving(watchdog=True):
        # watchdog=False marks a block that is expected to be long lived (app
        # startup), so the stuck-block watchdog doesn't fire on it.
        with StateManager.lock:
            StateManager.saveBlocked += 1
            if StateManager.saveBlocked == 1:
                StateManager.saveBlockedSince = time.time() if watchdog else None
            if SettingsManager.Get("general.statemanager_logging", False):
                logger.debug(
                    "Initial Block - Current Blocking Status: " + str(StateManager.saveBlocked)
                )

    @staticmethod
    def ReleaseSaving():
        with StateManager.lock:
            StateManager.saveBlocked -= 1
            if SettingsManager.Get("general.statemanager_logging", False):
                logger.debug(
                    "Release Block - Current Blocking Status: " + str(StateManager.saveBlocked)
                )

            # More releases than blocks would leave the counter negative, which
            # silently disables every future export just like a leaked block.
            if StateManager.saveBlocked < 0:
                logger.error(
                    "StateManager save block counter went negative "
                    f"({StateManager.saveBlocked}); there is a ReleaseSaving() "
                    "without a matching BlockSaving(). Resetting to 0."
                )
                StateManager.saveBlocked = 0

            if StateManager.saveBlocked == 0:
                StateManager.saveBlockedSince = None
                StateManager.SaveState()

    @staticmethod
    def ResetSaveBlock(reason: str):
        """Force saving back to an unblocked state and export immediately.

        Used to recover from an unbalanced BlockSaving() (usually an exception
        thrown between BlockSaving() and ReleaseSaving()), which would
        otherwise stop every export until the application is restarted.
        """
        with StateManager.lock:
            if StateManager.saveBlocked == 0:
                return
            logger.error(
                f"StateManager saving was stuck blocked ({StateManager.saveBlocked}): "
                f"{reason}. Forcing a save."
            )
            StateManager.saveBlocked = 0
            StateManager.saveBlockedSince = None
            StateManager.SaveState()

    @staticmethod
    def CheckSaveBlockWatchdog():
        """Recover the export if saving has been blocked for too long."""
        with StateManager.lock:
            blockedSince = StateManager.saveBlockedSince

            if StateManager.saveBlocked <= 0 or blockedSince is None:
                return

            timeout = SettingsManager.Get(
                "general.statemanager_block_timeout", StateManager.DEFAULT_BLOCK_WATCHDOG_SECONDS
            )

            if timeout <= 0:
                return

            blockedFor = time.time() - blockedSince

            if blockedFor > timeout:
                StateManager.ResetSaveBlock(
                    f"saving has been blocked for {blockedFor:.1f}s, which points to a "
                    "BlockSaving() without a matching ReleaseSaving()"
                )

    # =====================================================
    # SAVING
    # =====================================================
    @staticmethod
    def SaveState():
        with StateManager.lock:
            # Checked with the lock held: another thread may be blocking
            # saving right now, to change several values together
            if StateManager.saveBlocked != 0:
                return

            StateManager.savePending = False
            try:
                StateManager.DoSaveState()
            except Exception:
                # An export failure must never escape into a caller that is
                # holding a save block: it would skip that caller's
                # ReleaseSaving() and disable every future export.
                logger.error(traceback.format_exc())

    @staticmethod
    def RequestSave():
        """Schedule a save shortly, merging it with any other changes made until then."""
        with StateManager.lock:
            StateManager.savePending = True

            if StateManager.saveScheduler is None:
                app = QCoreApplication.instance()
                if app is None:
                    # No event loop to run the timer on, save right away
                    StateManager.SaveState()
                    return
                scheduler = StateManagerSaveScheduler()
                scheduler.moveToThread(app.thread())
                StateManager.saveScheduler = scheduler

            if QThread.currentThread() == StateManager.saveScheduler.thread():
                StateManager.saveScheduler.Start()
            else:
                StateManager.saveScheduler.request.emit()

    @staticmethod
    def FlushPendingSave():
        """Save now if there are changes waiting for a scheduled save."""
        with StateManager.lock:
            if StateManager.savePending:
                StateManager.SaveState()

    @staticmethod
    def DoSaveState():
        """Sends what changed since the last save to the layouts and exports
        it. Called with the lock held.

        Everything comes from one comparison of lastSavedState with the
        state, at the paths that were set or unset (see DiffStates): the
        delta sent to the layouts, the files written to and removed from
        out/, and lastSavedState's own update.
        """
        changedPaths = StateManager.changedPaths

        # Cleared up front: a change we cannot diff must not be retried on every
        # subsequent save, or a single bad key would stall the export for good.
        StateManager.changedPaths = []

        exportFiles = not SettingsManager.Get("general.disable_export", False)

        try:
            changes, delta = DiffStates(
                StateManager.lastSavedState,
                StateManager.state,
                changedPaths,
                StateManager.MAX_DELTA,
                # Every change has its files; the delta alone needs fewer
                everyChange=exportFiles,
            )
        except Exception:
            # No telling what changed: everything is sent and saved again
            logger.error(traceback.format_exc())
            StateManager.UpdateLastSavedState(None)
            StateManager._SendBigChange()
            StateManager.ExportJson()
            return

        if not delta:
            return

        # Before anything that could fail: the changes are found once, and
        # what isn't in lastSavedState now would never reach the layouts
        message = [] if len(delta) <= StateManager.MAX_DELTA else None
        if not StateManager.UpdateLastSavedState(delta, message):
            message = None

        try:
            if message is None:
                # Too much for a delta
                StateManager._SendBigChange()
            else:
                StateManager.deltaIndex += 1
                StateManager.signals.state_updated.emit(
                    {"delta_index": StateManager.deltaIndex, "delta": message}
                )
        except Exception:
            logger.error(traceback.format_exc())

        StateManager.ExportJson()

        try:
            if exportFiles:
                StateManager.ExportChanges(changes)
        except Exception:
            logger.error(traceback.format_exc())

    @staticmethod
    def _SendBigChange():
        StateManager.deltaIndex += 1
        StateManager.signals.state_big_change.emit()

    @staticmethod
    def UpdateLastSavedState(delta, message=None):
        """Apply the delta found by DiffStates to lastSavedState, which
        makes it the same as the state again without cloning all of it.
        With delta=None, or if that fails (False is returned then), the
        whole state is cloned.

        The changes are added to the list message, if given, the way
        they're sent to the layouts: {"path", "action", "value"}, for them
        to set value at path, or to remove the key at path when action is
        REMOVED (which has no value). The values are copies, as they're
        encoded later, in the web server's thread, when the state (and
        lastSavedState) may have changed again.
        """
        if delta is not None:
            try:
                for path, action, _, new in delta:
                    parent = StateManager.lastSavedState
                    for key in path[:-1]:
                        parent = parent[key]
                    if action == REMOVED:
                        del parent[path[-1]]
                        if message is not None:
                            message.append({"path": list(path), "action": action})
                        continue
                    if type(new) in _SCALARS:
                        saved = sent = new
                    elif message is None:
                        saved = deep_clone(new)
                    else:
                        saved, sent = deep_clones(new, 2)
                    parent[path[-1]] = saved
                    if message is not None:
                        message.append({"path": list(path), "action": action, "value": sent})
                return True
            except Exception:
                logger.warning(traceback.format_exc())

        StateManager.lastSavedState = deep_clone(StateManager.state)
        return False

    @staticmethod
    def ExportJson():
        """Write the state to out/program_state.json. Never raises."""

        def EncodeFallback(value):
            # Without this a single value orjson can't handle would stop
            # program_state.json from ever being written again.
            logger.warning(
                f"State contains a {type(value).__name__} value which isn't JSON "
                "serializable; exporting it as text"
            )
            return str(value)

        try:
            StateManager.state.update({"timestamp": time.time()})
            try:
                try:
                    encoded = orjson.dumps(
                        StateManager.state, default=EncodeFallback, option=orjson.OPT_NON_STR_KEYS
                    )
                except TypeError:
                    # What orjson refuses without asking (an int over 64 bits)
                    encoded = json.dumps(StateManager.state, default=EncodeFallback).encode()
            finally:
                StateManager.state.pop("timestamp", None)

            # Write to a temp file then atomically replace, so a concurrent
            # reader never sees a truncated file. On Windows the replace can
            # fail if the browser has the destination open; fall back to a
            # direct write in that case.
            os.makedirs("./out", exist_ok=True)
            tmp_path = "./out/program_state.json.tmp"
            with open(tmp_path, "wb") as file:
                file.write(encoded)
            try:
                os.replace(tmp_path, "./out/program_state.json")
            except PermissionError:
                os.remove(tmp_path)
                with open("./out/program_state.json", "wb") as file:
                    file.write(encoded)
        except Exception:
            logger.error(traceback.format_exc())

    # =====================================================
    # READING AND WRITING STATE
    # =====================================================
    @staticmethod
    def LoadState():
        with StateManager.lock:
            StateManager.load_error = None
            try:
                with open("./out/program_state.json", "rb") as file:
                    state = orjson.loads(file.read())
                if not isinstance(state, dict):
                    raise ValueError(f"Expected an object, found a {type(state).__name__}")
                # Left behind by the removed Additional Notes widget
                state.pop("notes", None)
                # Written with every save, and not part of the state
                state.pop("timestamp", None)
                StateManager.state = state
                # Only the changes are copied to lastSavedState from now on,
                # so it must start out matching the loaded state
                StateManager.lastSavedState = deep_clone(StateManager.state)
                StateManager.changedPaths = []
                StateManager.signals.state_big_change.emit()
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.error(traceback.format_exc())
                StateManager.load_error = f"./out/program_state.json\n\n{e}"
                StateManager.state = {}
                # Everything changed: what the layouts and out/ had is
                # removed by this save, or by the next one if saving is blocked
                StateManager.changedPaths = [()]
                StateManager.SaveState()

    @staticmethod
    def Get(key: str, default=None):
        return deep_get(StateManager.state, key, default)

    @staticmethod
    def Set(key: str, value, replace=False):
        """replace used to make a dict that mostly changed skip a slow diff
        (e.g. the teams' stats when they swap). Every value is compared
        fast enough now, so it changes nothing; kept for its callers."""
        with StateManager.lock:
            deep_set(StateManager.state, key, value)
            StateManager._Changed(key)

    @staticmethod
    def Unset(key: str):
        with StateManager.lock:
            deep_unset(StateManager.state, key)
            StateManager._Changed(key)

    @staticmethod
    def _Changed(key: str):
        """Records a change to key and saves it (or checks for a leaked block)"""
        StateManager.changedPaths.append(tuple(key.split(".")))
        if StateManager.saveBlocked == 0:
            StateManager.RequestSave()
        else:
            StateManager.CheckSaveBlockWatchdog()

    # =====================================================
    # FILE EXPORT
    # =====================================================
    # Every value of the state that isn't a dict has a file in out/, named
    # after its path: a/b.txt with the value as text, or a/b.png for a local
    # file ("./...", copied) or an image's address (downloaded). None has no
    # file, and neither has what's in EXPORT_EXCLUDED_PREFIXES.
    @staticmethod
    def ExportChanges(changes):
        """Update the files of out/ with the changes found by DiffStates."""
        for path, action, old, new in changes:
            # One value that can't be exported (a name the file system
            # refuses) mustn't keep the others from being
            try:
                filePath = "/".join(StateManager._FileKey(k) for k in path)
                if action == ADDED:
                    StateManager.CreateFilesDict(filePath, new)
                elif action == REMOVED:
                    StateManager.RemoveFilesDict(filePath, old)
                else:
                    # A value's file is written over, so it's never missing;
                    # unless its name changes or a dict is involved, whose
                    # files have to go
                    newFile = StateManager._FileName(filePath, new)
                    if newFile is None or newFile != StateManager._FileName(filePath, old):
                        StateManager.RemoveFilesDict(filePath, old)
                    StateManager.CreateFilesDict(filePath, new)
            except Exception:
                logger.error(traceback.format_exc())

    @staticmethod
    def _FileKey(key):
        return str(key).replace("/", "_")

    @staticmethod
    def _Excluded(path: str):
        """path being a/b for the state's a.b"""
        for prefix in StateManager.EXPORT_EXCLUDED_PREFIXES:
            excluded = "/".join(StateManager._FileKey(k) for k in prefix)
            if path == excluded or path.startswith(excluded + "/"):
                return True
        return False

    @staticmethod
    def _IsFile(value):
        """True for a value exported as a file of its own type (copied or
        downloaded) instead of as text."""
        if type(value) is not str:
            return False
        return value.startswith("./") or (
            value.startswith("http") and value.endswith((".png", ".jpg"))
        )

    @staticmethod
    def _FileName(path, value):
        """The file exported for value at path; None for a dict (a folder
        with its values' files) and for None (no file)."""
        if value is None or isinstance(value, dict):
            return None
        if StateManager._IsFile(value):
            return f"./out/{path}.{value.rsplit('.', 1)[-1]}"
        return f"./out/{path}.txt"

    @staticmethod
    def _RemoveFile(path: str):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except Exception:
            logger.error(traceback.format_exc())

    @staticmethod
    def CreateFilesDict(path, di):
        if di is None or StateManager._Excluded(path):
            return

        if isinstance(di, dict):
            for k, i in di.items():
                StateManager.CreateFilesDict(path + "/" + StateManager._FileKey(k), i)
            return

        os.makedirs(os.path.dirname(f"./out/{path}"), exist_ok=True)

        dest = StateManager._FileName(path, di)
        if not StateManager._IsFile(di):
            with open(dest, "w", encoding="utf-8") as file:
                file.write(str(_WithoutTuples(di)))
            return

        # A file or an image to download, exported with its extension
        StateManager._RemoveFile(dest)
        try:
            if di.startswith("./"):
                if os.path.exists(di):
                    shutil.copyfile(os.path.abspath(di), dest)
            else:
                # Not waited on: the save runs on the caller's thread
                # (usually the GUI), which must not hang on the network.
                threading.Thread(target=_DownloadImage, args=(di, dest), daemon=True).start()
        except Exception:
            logger.error(traceback.format_exc())

    @staticmethod
    def RemoveFilesDict(path, di):
        """Remove the files CreateFilesDict made for the value di at path."""
        if StateManager._Excluded(path):
            return

        if isinstance(di, dict):
            for k, i in di.items():
                StateManager.RemoveFilesDict(path + "/" + StateManager._FileKey(k), i)
        elif di is not None:
            StateManager._RemoveFile(StateManager._FileName(path, di))

        try:
            if os.path.isdir(f"./out/{path}"):
                shutil.rmtree(f"./out/{path}")
        except Exception:
            logger.error(traceback.format_exc())


def _DownloadImage(url, dlpath):
    try:
        r = requests.get(url, stream=True, timeout=15)
        if r.status_code == 200:
            with open(dlpath, "wb") as f:
                r.raw.decode_content = True
                shutil.copyfileobj(r.raw, f)
        if url.endswith(".jpg"):
            Image.open(dlpath).save(dlpath.rsplit(".", 1)[0] + ".png", format="png")
            os.remove(dlpath)
    except Exception:
        logger.error(traceback.format_exc())


os.makedirs("./out", exist_ok=True)

if not os.path.isfile("./out/program_state.json"):
    StateManager.SaveState()

StateManager.LoadState()
