from functools import reduce

from msgpack import packb, unpackb


def deep_get(dictionary, keys, default=None):
    return reduce(
        lambda d, key: d.get(key, default) if isinstance(d, dict) else default,
        keys.split("."),
        dictionary,
    )


def as_dict(value):
    """value if it's a dict, otherwise {}. APIs send null for missing
    objects, which .get(key, {}) returns as is."""
    return value if isinstance(value, dict) else {}


def as_list(value):
    """value's items that aren't None if it's a list, otherwise []"""
    return [item for item in value if item is not None] if isinstance(value, list) else []


def _parent(dictionary, keys):
    """The dict holding the last key of keys (created if missing), and that key"""
    *path, last = keys.split(".")
    for key in path:
        dictionary = dictionary.setdefault(key, {})
    return dictionary, last


def deep_set(dictionary, keys, value):
    d, key = _parent(dictionary, keys)
    d[key] = value


def deep_unset(dictionary, keys):
    d, key = _parent(dictionary, keys)
    d.pop(key, None)


def deep_clone(dictionary):
    return unpackb(packb(dictionary), strict_map_key=False)
