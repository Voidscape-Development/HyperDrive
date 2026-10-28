import contextlib
import os
import shutil
import threading
import time
import traceback

import orjson
import requests
from deepdiff import DeepDiff, Delta, extract
from loguru import logger
from PIL import Image
from qtpy.QtCore import QCoreApplication, QObject, QThread, QTimer, Signal, Slot

from .Helpers.DictHelper import deep_clone, deep_get, deep_set, deep_unset
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


class StateManager:
    lastSavedState = {}
    state = {}
    saveBlocked = 0
    signals = StateManagerSignals()
    # Paths changed since the last save, as tuples of keys: they narrow the
    # diff and update lastSavedState without cloning the whole state
    changedPaths = []
    # Paths set with Set(..., replace=True) since the last save
    replacedPaths = set()
    deltaIndex = 0
    load_error: str | None = None

    lock = threading.RLock()
    loop = None

    # Set()/Unset() don't save right away: changes made within this window are
    # exported together in a single save.
    SAVE_DEBOUNCE_MS = 40
    savePending = False
    saveScheduler: StateManagerSaveScheduler | None = None

    # More changes than this are sent as a whole new state instead of a delta
    MAX_DELTA = 100

    # DeepDiff's threshold_to_diff_deeper: a dict with fewer than this share of
    # its compared keys on both sides is reported as one values_changed.
    DIFF_DEEPER_THRESHOLD = 0.33

    # Timestamp of the last 0 -> 1 transition of saveBlocked, used by the
    # watchdog to detect a BlockSaving() that never got its ReleaseSaving().
    saveBlockedSince = None

    # If saving stays blocked for longer than this (seconds) while there are
    # pending changes, we assume a block was leaked and force a save.
    DEFAULT_BLOCK_WATCHDOG_SECONDS = 30

    # State paths whose subtrees are excluded from the out/ file export.
    # Use this for large lookup tables that are only useful as JSON (e.g. game.stages).
    EXPORT_EXCLUDED_PREFIXES = ("root['game']['stages']",)

    # =====================================================
    # SAVE BLOCKS
    # =====================================================
    @contextlib.contextmanager
    def SaveBlock(watchdog=True):
        StateManager.BlockSaving(watchdog=watchdog)
        try:
            yield
        finally:
            StateManager.ReleaseSaving()

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

    def CheckSaveBlockWatchdog():
        """Recover the export if saving has been blocked for too long."""
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
    def SaveState():
        if StateManager.saveBlocked != 0:
            return

        with StateManager.lock:
            StateManager.savePending = False
            try:
                StateManager.DoSaveState()
            except Exception as e:
                # An export failure must never escape into a caller that is
                # holding a save block: it would skip that caller's
                # ReleaseSaving() and disable every future export.
                logger.error(traceback.format_exc())

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

    def FlushPendingSave():
        """Save now if there are changes waiting for a scheduled save."""
        with StateManager.lock:
            if StateManager.savePending:
                StateManager.SaveState()

    def DoSaveState():
        def EncodeFallback(value):
            # Without this a single value orjson can't handle would stop
            # program_state.json from ever being written again.
            logger.warning(
                f"State contains a {type(value).__name__} value which isn't JSON "
                "serializable; exporting it as text"
            )
            return str(value)

        def ExportAll(ref_diff, replaced, changedPaths):
            try:
                StateManager.state.update({"timestamp": time.time()})
                try:
                    encoded = orjson.dumps(
                        StateManager.state, default=EncodeFallback, option=orjson.OPT_NON_STR_KEYS
                    )

                    # Write to a temp file then atomically replace, so a concurrent
                    # reader never sees a truncated file. On Windows the replace can
                    # fail if the browser has the destination open; fall back to a
                    # direct write in that case.
                    tmp_path = "./out/program_state.json.tmp"
                    with open(tmp_path, "wb") as file:
                        file.write(encoded)
                    try:
                        os.replace(tmp_path, "./out/program_state.json")
                    except PermissionError:
                        os.remove(tmp_path)
                        with open("./out/program_state.json", "wb") as file:
                            file.write(encoded)
                finally:
                    StateManager.state.pop("timestamp", None)

                if not SettingsManager.Get("general.disable_export", False):
                    StateManager.ExportText(StateManager.lastSavedState, ref_diff)
                    for path, (old, new) in replaced.items():
                        StateManager.ExportReplaced(
                            "/".join(k.replace("/", "_") for k in path), old, new
                        )
                StateManager.UpdateLastSavedState(changedPaths)
            except Exception as e:
                logger.error(traceback.format_exc())

        changedPaths = StateManager.changedPaths

        # Cleared up front: a change we cannot diff must not be retried on every
        # subsequent save, or a single bad key would stall the export for good.
        StateManager.changedPaths = []

        # Values set with replace=True skip DeepDiff, which goes through every
        # value inside them
        whole, replaced = StateManager._TakeReplaced(changedPaths)
        diffPaths = [p for p in changedPaths if not any(p[: len(w)] == w for w in whole)]

        try:
            # DeepDiff is slow, and without include_paths it compares the
            # whole state, so only hand it the paths that really differ.
            if whole and not diffPaths:
                diffKeys = []
            else:
                diffKeys = StateManager.NarrowChangedKeys(diffPaths)
            if diffKeys is None or len(diffKeys) > 0:
                diff = DeepDiff(
                    StateManager.lastSavedState,
                    StateManager.state,
                    exclude_types=[type(None)],
                    include_paths=diffKeys,
                    verbose_level=2,  # Necessary to see values of added items.
                    threshold_to_diff_deeper=StateManager.DIFF_DEEPER_THRESHOLD,
                )
            else:
                diff = {}
        except Exception as e:
            logger.error(traceback.format_exc())
            diff = None

        if diff is not None:
            try:
                delta = StateManager.WholeListDeltas(Delta(diff).to_flat_dicts())
                delta += [
                    {"path": list(path), "action": "values_changed", "value": deep_clone(new)}
                    for path, (old, new) in replaced.items()
                ]
                # logger.debug(f"State diff length: {diff_count}")
                if len(delta) > StateManager.MAX_DELTA:
                    StateManager.deltaIndex += 1
                    StateManager.signals.state_big_change.emit()
                elif len(delta) > 0:
                    StateManager.deltaIndex += 1
                    StateManager.signals.state_updated.emit(
                        {"delta_index": StateManager.deltaIndex, "delta": delta}
                    )
            except TypeError:
                changedKeys = sorted({".".join(path) for path in changedPaths})
                logger.warning(f"Couldn't serialize diff. Changed Keys: {changedKeys}")
            except Exception as e:
                logger.error(traceback.format_exc())
                # Overlays can still resync from the full state.
                StateManager.deltaIndex += 1
                StateManager.signals.state_big_change.emit()

        # When the diff couldn't be computed we still export, so that
        # program_state.json keeps tracking the live state.
        if diff is None or len(diff) > 0 or replaced:
            # Without a diff (or without changed keys, which makes DeepDiff
            # compare everything) we can't tell what changed, so resync
            # lastSavedState completely.
            ExportAll(
                diff if diff is not None else {},
                replaced,
                changedPaths if diff is not None and changedPaths else None,
            )

    def _TakeReplaced(changedPaths):
        """The paths set with replace=True since the last save, as the set of
        paths left out of the diff and {path: (old value, new value)} for the
        ones that changed. Only dicts on both sides with much changed in them
        are replaced as a whole, and not when a parent of theirs changed too:
        the diff has them then, and sends only what changed."""
        paths = StateManager.replacedPaths
        StateManager.replacedPaths = set()

        def Lookup(root, path):
            for k in path:
                if not isinstance(root, dict) or k not in root:
                    return None
                root = root[k]
            return root

        whole = set()
        candidates = {}
        for path in paths:
            if not all(StateManager._IsPlainKey(k) for k in path) or any(
                len(p) < len(path) and path[: len(p)] == p for p in changedPaths
            ):
                continue
            old = Lookup(StateManager.lastSavedState, path)
            new = Lookup(StateManager.state, path)
            if type(old) is not dict or type(new) is not dict:
                continue
            if StateManager._SameValue(old, new):
                whole.add(path)
                continue
            candidates[path] = (old, new, *StateManager._ChangedValues(old, new))

        # Mostly changed, or too much changed together for a delta (the
        # layouts would get the whole state instead)
        tooMany = sum(c[2] for c in candidates.values()) > StateManager.MAX_DELTA
        replaced = {}
        for path, (old, new, changed, total) in candidates.items():
            if tooMany or changed * 2 >= total:
                whole.add(path)
                replaced[path] = (old, new)
        return whole, replaced

    def _ChangedValues(old, new):
        """How many of the values in new (in its dicts and lists) differ from
        old's, and how many values there are in new."""
        if isinstance(new, dict):
            pairs = [(old.get(k) if type(old) is dict else None, v) for k, v in new.items()]
        elif isinstance(new, (list, tuple)):
            same = type(old) is type(new)
            pairs = [(old[i] if same and i < len(old) else None, v) for i, v in enumerate(new)]
        else:
            return (0 if type(old) is type(new) and old == new else 1), 1
        changed = total = 0
        for o, n in pairs:
            c, t = StateManager._ChangedValues(o, n)
            changed += c
            total += t
        return changed, total

    def UpdateLastSavedState(changedPaths):
        """Copy the changed paths of the state into lastSavedState.

        Much cheaper than cloning the whole state on every save. With
        changedPaths=None the whole state is cloned.
        """
        if changedPaths is not None:
            try:
                # Parents first, so a child copied later isn't overwritten
                for path in sorted(set(changedPaths), key=len):
                    src = StateManager.state
                    exists = True
                    for k in path:
                        if isinstance(src, dict) and k in src:
                            src = src[k]
                        else:
                            exists = False
                            break

                    dst = StateManager.lastSavedState
                    for k in path[:-1]:
                        if k not in dst:
                            if not exists:
                                break
                            dst[k] = {}
                        dst = dst[k]
                        if not isinstance(dst, dict):
                            raise TypeError(f"Can't update lastSavedState at {path}")
                    else:
                        if exists:
                            dst[path[-1]] = deep_clone(src)
                        else:
                            dst.pop(path[-1], None)
                return
            except Exception:
                logger.warning(traceback.format_exc())

        StateManager.lastSavedState = deep_clone(StateManager.state)

    # =====================================================
    # NARROWING CHANGES
    # =====================================================
    def NarrowChangedKeys(changedPaths):
        """Return DeepDiff include_paths giving the same diff as changedPaths.

        DeepDiff rebuilds its whole tree for every included path, so paths
        whose values didn't change are left out and changed dicts are narrowed
        down to the keys that changed. At every dict level DeepDiff is made to
        see enough keys to take the same decision as with the original paths
        (see DIFF_DEEPER_THRESHOLD), so the resulting diff is identical.

        Without changedPaths DeepDiff compares the whole state: [] is returned
        if it is unchanged, None (no include_paths) otherwise.
        """
        if not changedPaths:
            if StateManager._SameValue(StateManager.lastSavedState, StateManager.state):
                return []
            return None

        if not all(StateManager._IsPlainKey(k) for path in changedPaths for k in path):
            return list(set("root" + "".join(f"['{k}']" for k in path) for path in changedPaths))

        # Tree of the changed paths, True where a whole subtree is included
        tree = {}
        for path in changedPaths:
            node = tree
            for k in path[:-1]:
                if node.get(k) is True:
                    break
                node = node.setdefault(k, {})
            else:
                node[path[-1]] = True

        result = []
        StateManager._NarrowLevel(
            StateManager.lastSavedState, StateManager.state, "root", tree, result
        )
        return result

    def _IsPlainKey(k):
        # Keys that DeepDiff writes as ['key'] in its paths
        return type(k) is str and repr(k) == f"'{k}'"

    def _SameValue(a, b):
        """True if DeepDiff would find no difference between a and b."""
        if a is b:
            return True
        try:
            if type(a) is not type(b) or a != b:
                return False
            if isinstance(a, (dict, list, tuple, float)):
                # == alone treats 1, 1.0 and True as equal, DeepDiff doesn't
                option = orjson.OPT_NON_STR_KEYS | orjson.OPT_SORT_KEYS
                return orjson.dumps(a, option=option) == orjson.dumps(b, option=option)
            return True
        except Exception:
            return False

    def _DiffDeeper(intersect, union):
        # Mirrors DeepDiff: a dict is reported as a single values_changed when
        # too few of its compared keys exist on both sides.
        return not (union > 1 and intersect / union < StateManager.DIFF_DEEPER_THRESHOLD)

    def _OriginalPaths(key, tree, result):
        if tree is True:
            result.append(key)
        else:
            for k, subtree in tree.items():
                StateManager._OriginalPaths(f"{key}['{k}']", subtree, result)

    def _NarrowLevel(old, new, key, tree, result):
        """Narrow the paths of tree, where DeepDiff only compares the keys of
        old and new that are in tree."""
        if tree is True:
            StateManager._NarrowWhole(old, new, key, result)
            return

        if (
            type(old) is not dict
            or type(new) is not dict
            or not all(StateManager._IsPlainKey(k) for k in old)
            or not all(StateManager._IsPlainKey(k) for k in new)
        ):
            StateManager._OriginalPaths(key, tree, result)
            return

        added = [k for k in tree if k in new and k not in old]
        removed = [k for k in tree if k in old and k not in new]
        both = [k for k in tree if k in old and k in new]

        if not StateManager._DiffDeeper(len(both), len(added) + len(removed) + len(both)):
            # DeepDiff reports this dict as a whole, keep what it compares
            StateManager._OriginalPaths(key, tree, result)
            return

        StateManager._NarrowChildren(
            old,
            new,
            key,
            result,
            added,
            removed,
            both,
            lambda k, childKey, out: StateManager._NarrowLevel(
                old[k], new[k], childKey, tree[k], out
            ),
            lambda k, childKey, out: StateManager._OriginalPaths(childKey, tree[k], out),
        )

    def _NarrowWhole(old, new, key, result):
        """Narrow key, where DeepDiff compares the whole subtree."""
        if StateManager._SameValue(old, new):
            return

        if (
            type(old) is not dict
            or type(new) is not dict
            or not all(StateManager._IsPlainKey(k) for k in old)
            or not all(StateManager._IsPlainKey(k) for k in new)
        ):
            result.append(key)
            return

        added = [k for k in new if k not in old]
        removed = [k for k in old if k not in new]
        both = [k for k in old if k in new]

        if not StateManager._DiffDeeper(len(both), len(added) + len(removed) + len(both)):
            result.append(key)
            return

        narrowed = []
        StateManager._NarrowChildren(
            old,
            new,
            key,
            narrowed,
            added,
            removed,
            both,
            lambda k, childKey, out: StateManager._NarrowWhole(old[k], new[k], childKey, out),
            lambda k, childKey, out: out.append(childKey),
        )

        # DeepDiff checks every key it walks against every include path, so
        # n paths cost about n * n, and the dict as one path about its size:
        # less when most of it changed (e.g. the teams' stats swapped)
        limit = len(narrowed) ** 2
        if len(narrowed) > 1 and StateManager._SmallerThan(old, new, limit=limit):
            result.append(key)
        else:
            result.extend(narrowed)

    def _SmallerThan(*values, limit):
        """True if the values have fewer than limit dicts, lists and values
        in them, counting no further than limit."""
        stack = list(values)
        count = 0
        while stack:
            value = stack.pop()
            count += 1
            if count >= limit:
                return False
            if isinstance(value, dict):
                stack.extend(value.values())
            elif isinstance(value, (list, tuple)):
                stack.extend(value)
        return True

    def _NarrowChildren(old, new, key, result, added, removed, both, narrow, keep):
        changed = 0
        unchanged = []
        for k in both:
            childResult = []
            narrow(k, f"{key}['{k}']", childResult)
            if childResult:
                changed += 1
                result.extend(childResult)
            else:
                unchanged.append(k)

        reported = len(added) + len(removed) + changed
        if reported == 0:
            return

        for k in added + removed:
            result.append(f"{key}['{k}']")

        # Leaving the unchanged keys out could make DeepDiff report this dict
        # as a whole, so keep some of them in that case
        for k in unchanged:
            if StateManager._DiffDeeper(changed, reported):
                break
            keep(k, f"{key}['{k}']", result)
            changed += 1
            reported += 1

    def WholeListDeltas(deltas):
        """Changes inside lists (items added, removed or moved, which
        DeepDiff gives by index or as opcodes) as one change of the whole
        list, with its new value: the layouts and the web app only know how
        to set and remove keys."""

        def ListPath(d):
            action = d.get("action") or ""
            if action.startswith("iterable_items_"):
                return tuple(d["path"])
            if action.startswith("iterable_item_"):
                return tuple(d["path"][:-1])
            return None

        lists = {ListPath(d) for d in deltas} - {None}
        if not lists:
            return deltas
        # Only the outermost lists: they hold the changes of lists in them
        lists = {p for p in lists if not any(p[: len(o)] == o for o in lists if o != p)}

        result = [d for d in deltas if not any(tuple(d["path"][: len(p)]) == p for p in lists)]
        for path in sorted(lists, key=str):
            value = StateManager.state
            try:
                for key in path:
                    value = value[key]
            except (KeyError, IndexError, TypeError):
                # The list itself is gone
                continue
            result.append(
                {"path": list(path), "action": "values_changed", "value": deep_clone(value)}
            )
        return result

    # =====================================================
    # READING AND WRITING STATE
    # =====================================================
    def LoadState():
        StateManager.load_error = None
        try:
            with open("./out/program_state.json", "rb") as file:
                StateManager.state = orjson.loads(file.read())
                # Left behind by the removed Additional Notes widget
                StateManager.state.pop("notes", None)
                # Only changed paths are copied to lastSavedState from now on,
                # so it must start out matching the loaded state
                StateManager.lastSavedState = deep_clone(StateManager.state)
                StateManager.signals.state_big_change.emit()
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error(traceback.format_exc())
            StateManager.load_error = f"./out/program_state.json\n\n{e}"
            StateManager.state = {}
            StateManager.signals.state_big_change.emit()
            StateManager.SaveState()

    def Get(key: str, default=None):
        return deep_get(StateManager.state, key, default)

    def Set(key: str, value, replace=False):
        """With replace=True a dict that mostly changed (or with more changes
        than a delta takes, see MAX_DELTA) is sent and exported as one change
        of the whole value instead of being diffed value by value, which is
        much faster (e.g. the teams' stats when they swap). When only a
        little of it changed, it's diffed as usual."""
        with StateManager.lock:
            deep_set(StateManager.state, key, value)
            if replace:
                StateManager.replacedPaths.add(tuple(key.split(".")))
            StateManager._Changed(key)

    def Unset(key: str):
        with StateManager.lock:
            deep_unset(StateManager.state, key)
            StateManager._Changed(key)

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
    def ExportText(oldState, diff):
        changes = [*diff.get("values_changed", {}).items(), *diff.get("type_changes", {}).items()]
        for key, change in changes:
            if StateManager._Excluded(key):
                continue
            if change.get("new_type") == type(None):
                StateManager.RemoveFilesDict(StateManager._FilePath(key), extract(oldState, key))
            else:
                StateManager.CreateFilesDict(StateManager._FilePath(key), change.get("new_value"))

        for key in diff.get("dictionary_item_removed", {}):
            if not StateManager._Excluded(key):
                StateManager.RemoveFilesDict(StateManager._FilePath(key), extract(oldState, key))

        for key in diff.get("dictionary_item_added", {}):
            if StateManager._Excluded(key):
                continue
            try:
                item = extract(StateManager.state, key)
                StateManager.CreateFilesDict(StateManager._FilePath(key), item)
            except Exception:
                logger.error(traceback.format_exc())

    def _Excluded(stateKey: str):
        return stateKey.startswith(StateManager.EXPORT_EXCLUDED_PREFIXES)

    def _FilePath(stateKey: str):
        """root['a']['b/c'] -> a/b_c"""
        return "/".join(stateKey[5:].replace("'", "").replace("]", "").replace("/", "_").split("["))

    def _StateKey(path: str):
        """a/b -> root['a']['b']"""
        return "root" + "".join(f"['{p}']" for p in path.split("/") if p)

    def _RemoveFile(path: str):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except Exception:
            logger.error(traceback.format_exc())

    def CreateFilesDict(path, di):
        if StateManager._Excluded(StateManager._StateKey(path)):
            return

        os.makedirs(os.path.dirname(f"./out/{path}"), exist_ok=True)

        if type(di) == dict:
            for k, i in di.items():
                StateManager.CreateFilesDict(path + "/" + str(k).replace("/", "_"), i)
            return

        isStr = type(di) == str
        isLocal = isStr and di.startswith("./")
        if not isLocal and not (isStr and di.startswith("http") and di.endswith((".png", ".jpg"))):
            with open(f"./out/{path}.txt", "w", encoding="utf-8") as file:
                file.write(str(di))
            return

        # A file or an image to download, exported with its extension
        dest = f"./out/{path}.{di.rsplit('.', 1)[-1]}"
        StateManager._RemoveFile(dest)
        try:
            if isLocal:
                if os.path.exists(di):
                    shutil.copyfile(os.path.abspath(di), dest)
            else:
                # Not waited on: the save runs on the caller's thread
                # (usually the GUI), which must not hang on the network.
                threading.Thread(target=_DownloadImage, args=(di, dest), daemon=True).start()
        except Exception:
            logger.error(traceback.format_exc())

    def ExportReplaced(path, old, new):
        """Export a value set with replace=True: only the files of what
        changed in it are written or removed. None is no file, as with the
        diff, which leaves None out."""
        if type(old) is dict and type(new) is dict:
            for k, value in old.items():
                if k not in new:
                    StateManager.RemoveFilesDict(path + "/" + str(k).replace("/", "_"), value)
            for k, value in new.items():
                childPath = path + "/" + str(k).replace("/", "_")
                if k not in old:
                    if value is not None:
                        StateManager.CreateFilesDict(childPath, value)
                elif not StateManager._SameValue(old[k], value):
                    StateManager.ExportReplaced(childPath, old[k], value)
            return
        StateManager.RemoveFilesDict(path, old)
        if new is not None:
            StateManager.CreateFilesDict(path, new)

    def RemoveFilesDict(path, di):
        if StateManager._Excluded(StateManager._StateKey(path)):
            return

        if type(di) == dict:
            for k, i in di.items():
                StateManager.RemoveFilesDict(path + "/" + str(k).replace("/", "_"), i)
        elif type(di) == str and di.startswith(("./", "http")):
            StateManager._RemoveFile(f"./out/{path}.{di.rsplit('.', 1)[-1]}")
        else:
            StateManager._RemoveFile(f"./out/{path}.txt")

        try:
            if os.path.exists(f"./out/{path}"):
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
