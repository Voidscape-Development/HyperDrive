import copy

from msgpack import packb, unpackb

_MISSING = object()


def deep_get(dictionary, keys, default=None):
    """The value at the dotted path keys, or default when a key on the way is
    missing or its parent isn't a dict."""
    for key in keys.split("."):
        if not isinstance(dictionary, dict):
            return default
        dictionary = dictionary.get(key, _MISSING)
        if dictionary is _MISSING:
            return default
    return dictionary


def as_dict(value):
    """value if it's a dict, otherwise {}. APIs send null for missing
    objects, which .get(key, {}) returns as is."""
    return value if isinstance(value, dict) else {}


def as_list(value):
    """value's items that aren't None if it's a list, otherwise []"""
    return [item for item in value if item is not None] if isinstance(value, list) else []


def deep_set(dictionary, keys, value):
    """Sets the value at the dotted path keys, creating the dicts on the way.
    A value on the way that isn't a dict (None from an API, a text) is
    replaced by one, the way the layouts apply the change."""
    *path, last = keys.split(".")
    for key in path:
        child = dictionary.get(key)
        if not isinstance(child, dict):
            child = dictionary[key] = {}
        dictionary = child
    dictionary[last] = value


def deep_unset(dictionary, keys):
    """Removes the key at the dotted path keys. As it always did, the dicts
    on the way are created when missing; a value on the way that isn't a
    dict is left as it is (there's nothing to remove in it)."""
    *path, last = keys.split(".")
    for key in path:
        child = dictionary.setdefault(key, {})
        if not isinstance(child, dict):
            return
        dictionary = child
    dictionary.pop(last, None)


def deep_clone(dictionary):
    try:
        return unpackb(packb(dictionary), strict_map_key=False)
    except Exception:
        # Values msgpack doesn't take (a set, an int over 64 bits, an object)
        return copy.deepcopy(dictionary)


def deep_clones(dictionary, count):
    """count clones of dictionary, faster than as many deep_clone()"""
    try:
        packed = packb(dictionary)
        return [unpackb(packed, strict_map_key=False) for _ in range(count)]
    except Exception:
        return [copy.deepcopy(dictionary) for _ in range(count)]
