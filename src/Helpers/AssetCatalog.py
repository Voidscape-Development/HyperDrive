"""The asset pack catalog (StreamHelperAssets' assets.json) and installing
packs from it. No Qt here: the downloader window and its queue use these, and
the tests run them on their own.

A catalog is {game: {"name", "assets": {pack: {"name", "version", "files",
"description", "credits", "has_stage_data", "has_eyesight_data"}}}}. Each pack
unpacks into user_data/games/<game>/<pack>/; base_files holds the game's own
config and is needed by every other pack."""

import datetime
import os
import shutil
import time

import py7zr
import requests

GAMES_DIR = "./user_data/games"
CATALOG_URL = "https://raw.githubusercontent.com/joaorb64/StreamHelperAssets/main/assets.json"
RELEASE_URL = "https://github.com/joaorb64/StreamHelperAssets/releases/latest/download/"
LOGO_URLS = [
    "https://raw.githubusercontent.com/joaorb64/StreamHelperAssets/main/games/{game}/base_files/logo_small.png",
    "https://raw.githubusercontent.com/joaorb64/StreamHelperAssets/main/games/{game}/base_files/logo.png",
]
LOGO_CACHE_DIR = "./user_data/asset_logo_cache"
# A cached logo older than this is fetched again, in case the game's logo changed
LOGO_CACHE_MAX_AGE = 30 * 24 * 60 * 60
BASE_FILES = "base_files"
# Partial downloads go here, so a cancelled or failed one never reaches a game folder
DOWNLOADS_DIR = ".downloads"
CHUNK_SIZE = 1024 * 1024
TIMEOUT = 30

STATE_INSTALLED = "installed"
STATE_UPDATE = "update"
STATE_NEW = "new"


# =====================================================
# CATALOG
# =====================================================
def FetchCatalog():
    response = requests.get(CATALOG_URL, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def FetchLogo(game):
    """The game's logo as PNG bytes, or None."""
    for url in LOGO_URLS:
        try:
            response = requests.get(url.format(game=game), timeout=TIMEOUT)
            response.raise_for_status()
            return response.content
        except requests.RequestException:
            continue
    return None


def LogoCachePath(game, cacheDir=LOGO_CACHE_DIR):
    """Where the game's logo is cached, or None for a game code that isn't a
    safe file name."""
    if not game or not all(c.isalnum() or c in "_-." for c in game) or game.startswith("."):
        return None
    return os.path.join(cacheDir, f"{game}.png")


def CachedLogo(game, cacheDir=LOGO_CACHE_DIR, maxAge=LOGO_CACHE_MAX_AGE):
    """The cached logo as (PNG bytes or None, whether it's recent enough)."""
    path = LogoCachePath(game, cacheDir)
    try:
        with open(path, "rb") as f:
            data = f.read()
        return data, time.time() - os.path.getmtime(path) < maxAge
    except (OSError, TypeError):
        return None, False


def SaveLogo(game, data, cacheDir=LOGO_CACHE_DIR):
    path = LogoCachePath(game, cacheDir)
    if path is None:
        return
    try:
        os.makedirs(cacheDir, exist_ok=True)
        # Written aside then swapped in, so a crash never leaves half a file
        temp = path + ".part"
        with open(temp, "wb") as f:
            f.write(data)
        os.replace(temp, path)
    except OSError:
        pass


def LoadLogo(game, cacheDir=LOGO_CACHE_DIR, maxAge=LOGO_CACHE_MAX_AGE):
    """The game's logo from the cache, fetched (and cached) when it isn't
    there or is old. An old cached logo is still used if the fetch fails."""
    cached, fresh = CachedLogo(game, cacheDir, maxAge)
    if cached is not None and fresh:
        return cached
    data = FetchLogo(game)
    if data is None:
        return cached
    SaveLogo(game, data, cacheDir)
    return data


def Packs(catalog, game):
    """The game's packs, base files first, then by name."""
    packs = catalog.get(game, {}).get("assets", {})
    return sorted(packs, key=lambda p: (p != BASE_FILES, str(packs[p].get("name", p)).casefold()))


def PackSize(catalog, game, pack):
    files = catalog[game]["assets"][pack].get("files", {})
    return sum(f.get("size", 0) for f in files.values())


def InstalledVersion(installedGames, game, pack):
    """The installed version of the pack, "" if it isn't installed.
    installedGames is GameAssetManager.games."""
    version = installedGames.get(game, {}).get("assets", {}).get(pack, {}).get("version", "")
    return str(version) if version is not None else ""


def HasBaseFiles(installedGames, game):
    return BASE_FILES in installedGames.get(game, {}).get("assets", {})


def PackState(catalog, installedGames, game, pack):
    installed = InstalledVersion(installedGames, game, pack)
    if installed == "":
        return STATE_NEW
    if installed == str(catalog[game]["assets"][pack].get("version")):
        return STATE_INSTALLED
    return STATE_UPDATE


def Updates(catalog, installedGames):
    """[(game, pack)] of installed packs that have a newer version."""
    return [
        (game, pack)
        for game in catalog
        for pack in Packs(catalog, game)
        if PackState(catalog, installedGames, game, pack) == STATE_UPDATE
    ]


def InstalledPacks(catalog, installedGames, game):
    return [
        p for p in Packs(catalog, game) if PackState(catalog, installedGames, game, p) != STATE_NEW
    ]


# =====================================================
# SEARCH
# =====================================================
def _Matches(words, *texts):
    """Every word is somewhere in the texts ("smash ultimate" matches
    Super Smash Bros. Ultimate)."""
    text = " ".join(str(t or "") for t in texts).casefold()
    return all(word in text for word in words)


def MatchingPacks(catalog, game, query):
    """The game's packs a search matches: all of them when the query is
    empty or matches the game itself, else the packs whose name or
    description matches (possibly none)."""
    words = query.casefold().split()
    info = catalog.get(game, {})
    packs = Packs(catalog, game)
    if not words or _Matches(words, info.get("name"), game):
        return packs
    return [
        p
        for p in packs
        if _Matches(words, info["assets"][p].get("name"), info["assets"][p].get("description"))
    ]


# =====================================================
# DISPLAY
# =====================================================
def FormatSize(size):
    """Bytes as e.g. 512 KB, 22.6 MB or 2.2 GB."""
    if size < 1024 * 1024:
        return f"{max(1, round(size / 1024)) if size else 0} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB"
    return f"{size / 1024 / 1024 / 1024:.1f} GB"


def VersionDate(version):
    """Versions are year.month.day.build (26.10.02.40910). The date, or None
    for a version that isn't one."""
    parts = str(version or "").split(".")
    if len(parts) < 3:
        return None
    try:
        return datetime.date(2000 + int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


# =====================================================
# INSTALLING
# =====================================================
def PackPath(game, pack, gamesDir=GAMES_DIR):
    return os.path.join(gamesDir, game, pack)


def PackFiles(catalog, game, pack):
    """The files to download for a pack, in order: [{"name", "size", "url"}]."""
    files = catalog[game]["assets"][pack].get("files", {})
    return [
        {"name": f["name"], "size": f.get("size", 0), "url": RELEASE_URL + f["name"]}
        for f in sorted(files.values(), key=lambda f: f["name"])
    ]


def FreeSpace(gamesDir=GAMES_DIR):
    """Free bytes on the drive the games are on."""
    path = os.path.abspath(gamesDir)
    while not os.path.exists(path):
        path = os.path.dirname(path)
    return shutil.disk_usage(path).free


def InstallPack(game, pack, files, progress, cancelled, onUnpack=None, gamesDir=GAMES_DIR):
    """Downloads a pack's files and unpacks them into the game's folder.

    progress(done, total) is called with the bytes downloaded so far,
    cancelled() is checked between chunks, and onUnpack() is called once the
    download is done and unpacking starts. Returns False if it was cancelled.
    Nothing is left in the downloads folder either way."""
    workDir = os.path.join(gamesDir, DOWNLOADS_DIR, f"{game}.{pack}")
    shutil.rmtree(workDir, ignore_errors=True)
    os.makedirs(workDir)

    try:
        total = sum(f["size"] for f in files)
        done = 0
        paths = []
        for f in files:
            path = os.path.join(workDir, os.path.basename(f["name"]))
            paths.append(path)
            with requests.get(f["url"], stream=True, timeout=TIMEOUT) as response:
                response.raise_for_status()
                with open(path, "wb") as out:
                    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                        if cancelled():
                            return False
                        out.write(chunk)
                        done += len(chunk)
                        progress(done, max(total, done))

        if cancelled():
            return False
        if onUnpack:
            onUnpack()

        gameDir = os.path.join(gamesDir, game)
        os.makedirs(gameDir, exist_ok=True)

        if any(".7z" in f["name"] for f in files):
            # A pack too big for one file comes split in parts (.7z.001, .7z.002...)
            archive = os.path.join(workDir, "pack.7z")
            with open(archive, "wb") as out:
                for path in paths:
                    with open(path, "rb") as part:
                        shutil.copyfileobj(part, out)
            with py7zr.SevenZipFile(archive, "r") as zipFile:
                zipFile.extractall(gameDir)
        else:
            for path in paths:
                shutil.move(path, os.path.join(gameDir, os.path.basename(path)))

        progress(total, total)
        return True
    finally:
        shutil.rmtree(workDir, ignore_errors=True)
        # Gone once nothing else is downloading, so it's never taken for a game
        try:
            os.rmdir(os.path.dirname(workDir))
        except OSError:
            pass


def RemovePack(game, pack, gamesDir=GAMES_DIR):
    """Deletes an installed pack. Base files can't be removed this way: every
    other pack of the game needs them."""
    if pack == BASE_FILES:
        raise ValueError("Base files can't be removed on their own")
    gameDir = os.path.realpath(os.path.join(gamesDir, game))
    path = os.path.realpath(PackPath(game, pack, gamesDir))
    # Only ever a pack folder directly inside the game's folder
    if os.path.dirname(path) != gameDir or not os.path.isdir(path):
        raise ValueError(f"{path} isn't an installed pack of {game}")
    shutil.rmtree(path)
