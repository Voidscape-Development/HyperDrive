# Checks that SettingsManager can't lose the user's settings (their API keys
# among them): settings.json is replaced, never written in place, so a write
# that fails leaves the previous one; a file that can't be loaded is kept
# aside before anything is saved over it; and Set() can be called from
# several threads.
# Run from the repository root: python test/test_settings_manager.py
import json
import os
import sys
import tempfile
import threading
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

# SettingsManager reads and writes ./user_data
os.chdir(tempfile.mkdtemp())
os.makedirs("user_data")

from loguru import logger

from src.SettingsManager import SettingsManager

# The errors these tests cause are logged
logger.remove()

PATH = "user_data/settings.json"
KEYS = {"startgg_user": {"api_key": "secret"}, "general": {"language": "pt-BR"}}


def Read(path=PATH):
    with open(path, "rb") as file:
        return file.read()


def Write(content, path=PATH):
    with open(path, "wb") as file:
        file.write(content if isinstance(content, bytes) else json.dumps(content).encode())


def Folder():
    return sorted(os.listdir("user_data"))


def Reset(content=None):
    for name in os.listdir("user_data"):
        os.remove(f"user_data/{name}")
    if content is not None:
        Write(content)
    SettingsManager.LoadSettings()


def TestFirstLaunch():
    # Imported with no settings.json: one is made
    assert SettingsManager.first_launch
    assert SettingsManager.load_error is None
    assert json.loads(Read()) == {} == SettingsManager.settings
    assert Folder() == ["settings.json"]


def TestSetGet():
    Reset()
    assert not os.path.exists(PATH) and SettingsManager.settings == {}
    SettingsManager.Set("general.language", "en")
    SettingsManager.Set("startgg_user.api_key", "secret")
    SettingsManager.Set("a.b.c", [1, {"d": None}])
    assert SettingsManager.Get("general.language") == "en"
    assert SettingsManager.Get("general.missing") is None
    assert SettingsManager.Get("general.missing", 5) == 5
    assert SettingsManager.Get("general.language.deeper", "default") == "default"
    expected = {
        "general": {"language": "en"},
        "startgg_user": {"api_key": "secret"},
        "a": {"b": {"c": [1, {"d": None}]}},
    }
    assert json.loads(Read()) == expected == SettingsManager.settings
    SettingsManager.Unset("a.b")
    SettingsManager.Unset("general.language.deeper")
    expected["a"] = {}
    assert json.loads(Read()) == expected == SettingsManager.settings
    # Nothing but the file is left, and it's loaded back the same
    assert Folder() == ["settings.json"]
    SettingsManager.settings = {}
    SettingsManager.LoadSettings()
    assert SettingsManager.settings == expected and SettingsManager.load_error is None


def TestRemovedKeys():
    Reset({**KEYS, "bsky_account": {"app_password": "x"}, "hotkeys": {"a": 1}})
    assert SettingsManager.settings == KEYS
    assert json.loads(Read()) == KEYS


def TestFailedWrite():
    # The write is interrupted (a crash, a full disk): the previous file stays
    Reset(KEYS)
    before = Read()
    realOpen = open

    class Truncating:
        def __init__(self, file):
            self.file = file

        def write(self, data):
            self.file.write(data[: len(data) // 2])
            self.file.flush()
            raise OSError("No space left on device")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.file.close()

        def __getattr__(self, name):
            return getattr(self.file, name)

    import builtins

    builtins.open = lambda path, mode="r", *a, **k: (
        Truncating(realOpen(path, mode, *a, **k)) if "w" in mode else realOpen(path, mode, *a, **k)
    )
    try:
        # The widget that changed the setting doesn't fail over it
        SettingsManager.Set("general.language", "ja")
    finally:
        builtins.open = realOpen
    assert Read() == before
    assert SettingsManager.Get("general.language") == "ja"
    # Saved with the next change
    SettingsManager.Set("general.other", 1)
    assert json.loads(Read())["general"] == {"language": "ja", "other": 1}
    assert Folder() == ["settings.json"]

    # The replace fails
    before = Read()
    replace = os.replace
    os.replace = lambda *args: (_ for _ in ()).throw(OSError("failed"))
    try:
        SettingsManager.Set("general.other", 2)
    finally:
        os.replace = replace
    assert Read() == before
    SettingsManager.Set("general.other", 3)
    assert json.loads(Read())["general"]["other"] == 3
    assert Folder() == ["settings.json"]


def TestFileInUse():
    # Windows refuses to replace a file another program has open: it's
    # retried, then written in place
    Reset(KEYS)
    replace = os.replace
    calls = []

    def Refuse(source, dest, count):
        calls.append(dest)
        if len(calls) <= count:
            raise PermissionError("in use")
        replace(source, dest)

    for count in (1, 100):
        calls.clear()
        os.replace = lambda source, dest: Refuse(source, dest, count)
        try:
            SettingsManager.Set("general.count", count)
        finally:
            os.replace = replace
        assert json.loads(Read())["general"]["count"] == count
        assert json.loads(Read())["startgg_user"] == KEYS["startgg_user"]
        assert Folder() == ["settings.json"]


def TestBrokenFile():
    for broken in [b'{"startgg_user": {"api_key": "sec', b"", b"[1, 2]", b'"text"', b"\xff\xfe"]:
        Reset(broken)
        # Nothing was loaded, and the file is kept under another name
        assert SettingsManager.settings == {}
        assert Folder() == ["settings.json.broken"], Folder()
        assert Read("user_data/settings.json.broken") == broken
        error = SettingsManager.load_error
        assert error.startswith("./user_data/settings.json\n\n"), error
        assert "./user_data/settings.json.broken" in error
        assert not SettingsManager.save_disabled

        # The settings changed from there are saved, without touching it
        SettingsManager.Set("general.language", "en")
        assert json.loads(Read()) == {"general": {"language": "en"}}
        assert Read("user_data/settings.json.broken") == broken

        # Broken again: the first one, which may be the one with the
        # user's settings, isn't replaced
        Write(b"{again")
        SettingsManager.LoadSettings()
        assert Folder() == ["settings.json.broken", "settings.json.broken.2"]
        assert Read("user_data/settings.json.broken") == broken
        assert Read("user_data/settings.json.broken.2") == b"{again"
        assert "settings.json.broken.2" in SettingsManager.load_error

        # A good file clears the error
        Write(KEYS)
        SettingsManager.LoadSettings()
        assert SettingsManager.load_error is None and SettingsManager.settings == KEYS

    # Every file kept has a name the web server refuses to serve (see the
    # file route of src/WebServer.py), as they hold the API keys too
    for path in (SettingsManager.PATH, SettingsManager.TEMP_PATH, SettingsManager.BROKEN_PATH):
        assert os.path.basename(path).startswith("settings.json")
        assert os.path.dirname(path) == "./user_data"


def TestBrokenFileThatCantBeKept():
    # It can't be moved aside: it's never written over
    broken = b'{"startgg_user": {"api_key": "sec'
    Reset()
    Write(broken)
    replace = os.replace
    os.replace = lambda *args: (_ for _ in ()).throw(PermissionError("in use"))
    try:
        SettingsManager.LoadSettings()
    finally:
        os.replace = replace
    assert SettingsManager.save_disabled
    assert "won't be saved" in SettingsManager.load_error
    SettingsManager.Set("general.language", "en")
    SettingsManager.Unset("general.other")
    assert SettingsManager.Get("general.language") == "en"
    assert Read() == broken and Folder() == ["settings.json"]

    # Nor is a file that can't be read (it isn't broken, and isn't moved)
    Reset(KEYS)
    realOpen = open
    import builtins

    def Refuse(path, mode="r", *args, **kwargs):
        if "r" in mode and str(path).endswith("settings.json"):
            raise PermissionError("denied")
        return realOpen(path, mode, *args, **kwargs)

    builtins.open = Refuse
    try:
        SettingsManager.LoadSettings()
    finally:
        builtins.open = realOpen
    assert SettingsManager.save_disabled and SettingsManager.settings == {}
    assert SettingsManager.load_error.startswith("./user_data/settings.json\n\n")
    SettingsManager.Set("general.language", "en")
    assert json.loads(Read()) == KEYS and Folder() == ["settings.json"]

    # Loaded fine the next time: saved again
    SettingsManager.LoadSettings()
    assert not SettingsManager.save_disabled and SettingsManager.load_error is None
    SettingsManager.Set("general.language", "en")
    assert json.loads(Read())["general"]["language"] == "en"


def TestThreads():
    # The GUI and the web server's threads set settings at the same time,
    # while the file is read: it's always whole
    Reset(KEYS)
    errors = []
    done = threading.Event()

    def Work(number):
        try:
            for i in range(60):
                SettingsManager.Set(f"thread_{number}.value_{i}", "x" * 200)
                SettingsManager.Set("shared.last", [number, i])
                if i % 7 == 0:
                    SettingsManager.Unset(f"thread_{number}.value_{i}")
                assert SettingsManager.Get(f"thread_{number}.value_{i - 1 if i else 1}", "x")
        except Exception as e:
            errors.append(e)

    def Watch():
        try:
            while not done.is_set():
                assert json.loads(Read())["startgg_user"] == KEYS["startgg_user"]
        except Exception as e:
            errors.append(e)

    watcher = threading.Thread(target=Watch)
    watcher.start()
    threads = [threading.Thread(target=Work, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    done.set()
    watcher.join()
    assert errors == [], errors
    # The last write has every thread's settings
    assert json.loads(Read()) == SettingsManager.settings
    for number in range(8):
        values = SettingsManager.Get(f"thread_{number}")
        assert len(values) == 60 - len(range(0, 60, 7)), len(values)
    assert Folder() == ["settings.json"]


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("Test")]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
