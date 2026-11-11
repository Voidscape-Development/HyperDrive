# The clients' side of the state protocol, in Python, for the tests that
# check what StateManager sends: a port of layout/include/state_client.js
# (the one implementation the layouts, the web app and the Stream Deck
# plugin run). test/test_state_protocol.py holds it to the same fixture as
# the JavaScript, test/fixtures/state_protocol.json.
import re

SET_ACTIONS = ("values_changed", "type_changes", "dictionary_item_added")
REMOVE_ACTIONS = ("dictionary_item_removed",)
ACTIONS = SET_ACTIONS + REMOVE_ACTIONS

# What older servers sent for a change they had no value of
UNKNOWN_VALUE = "unknown___"

_MISSING = object()


class DeltaError(ValueError):
    """A delta the protocol doesn't know."""


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_index(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _list_index(items, key):
    """A list's index from a path key: 0 to the list's length, or -1."""
    if isinstance(key, str):
        index = int(key) if re.fullmatch(r"[0-9]+", key) else -1
    elif _is_index(key) or (isinstance(key, float) and key.is_integer()):
        index = int(key)
    else:
        index = -1
    return index if 0 <= index <= len(items) else -1


def _object_key(node, key):
    """Keys of JSON objects are text. States that never went through JSON
    (StateManager's, in the tests) may hold the number itself."""
    if isinstance(key, str) or key in node:
        return key
    if isinstance(key, float) and key.is_integer():
        key = int(key)
    return str(key)


def apply_deltas(state, deltas):
    """The state with the deltas applied, leaving the state as it was: only
    the dicts and lists on the changed paths are copied. Raises DeltaError
    on a delta the protocol doesn't know."""
    if not isinstance(deltas, list):
        raise DeltaError(f"Not a list of deltas: {deltas!r}")
    root = dict(state)
    copied = {id(root)}

    for delta in deltas:
        path = delta.get("path") if isinstance(delta, dict) else None
        if not isinstance(path, list) or not path:
            raise DeltaError(f"Delta without a path: {delta!r}")
        action = delta.get("action")
        remove = action in REMOVE_ACTIONS
        value = delta.get("value", _MISSING)
        if not remove:
            if action not in SET_ACTIONS:
                raise DeltaError(f"Unsupported delta action: {delta!r}")
            if value is _MISSING or (isinstance(value, str) and value == UNKNOWN_VALUE):
                raise DeltaError(f"Delta without a value: {delta!r}")

        node = root
        for i, key in enumerate(path):
            last = i == len(path) - 1
            if not (isinstance(key, str) or _is_number(key)) or key == "__proto__":
                raise DeltaError(f"Invalid key in a delta's path: {delta!r}")
            if isinstance(node, list):
                key = _list_index(node, key)
                # Items are never removed from lists: the whole list is sent
                if key < 0 or (remove and last):
                    raise DeltaError(f"Invalid list change: {delta!r}")
                exists = key < len(node)
            else:
                key = _object_key(node, key)
                exists = key in node

            if last:
                if remove:
                    node.pop(key, None)
                elif exists or isinstance(node, dict):
                    node[key] = value
                else:
                    node.append(value)
                break

            # On the way: a copy of what is there, or a new dict where there
            # is none (or a value that isn't one)
            following = node[key] if exists else None
            if not isinstance(following, (dict, list)):
                following = {}
            elif id(following) not in copied:
                following = following.copy()
            copied.add(id(following))
            if exists or isinstance(node, dict):
                node[key] = following
            else:
                node.append(following)
            node = following
    return root


class Sync:
    """createSync() of state_client.js: follows the numbering of the
    messages and applies the deltas that are next in line."""

    def __init__(self, request_full_state):
        self.request_full_state = request_full_state
        self.index = None
        self.resyncing = False

    def full(self, message):
        index = message.get("delta_index") if isinstance(message, dict) else None
        self.index = index if _is_index(index) else None
        self.resyncing = False
        state = message.get("state") if isinstance(message, dict) else None
        return state if isinstance(state, dict) else {}

    def delta(self, message, state):
        """(status, state): the state as given unless status is "applied"."""
        if self.resyncing:
            return "waiting", state
        index = message.get("delta_index") if isinstance(message, dict) else None
        if not _is_index(index) or not isinstance(message.get("delta"), list):
            status = "invalid"
        elif self.index is None or index > self.index + 1:
            status = "gap"
        elif index == self.index:
            status = "duplicate"
        elif index < self.index:
            status = "stale"
        elif not message["delta"]:
            status = "empty"
        else:
            try:
                state = apply_deltas(state, message["delta"])
                status = "applied"
            except DeltaError:
                status = "invalid"

        if status in ("applied", "empty"):
            self.index = index
        elif status != "duplicate":
            self.resyncing = True
            self.request_full_state(status, index)
        return status, state

    def reset(self):
        self.index = None
        self.resyncing = False
