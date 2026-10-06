import csv
import json
import os
import threading
import time
import traceback

import orjson
from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from sqlmodel import Session, select

from .Helpers.TSHDictHelper import deep_clone
from .Helpers.TSHQtHelper import gui_thread_sync
from .SettingsManager import SettingsManager
from .TSHGameAssetManager import TSHGameAssetManager
from .TSHPlayerDBModels import PLAYER_FIELDS, GetEngine, MakeTag, Player

# Where the players were saved before the SQLite database
LEGACY_JSON_PATH = "./user_data/local_players.json"
LEGACY_CSV_PATH = "./user_data/local_players.csv"


class TSHPlayerDBSignals(QObject):
    db_updated = Signal()


class TSHPlayerDB:
    signals = TSHPlayerDBSignals()
    database = {}
    model: QStandardItemModel = None
    webServer = None
    modelLock = threading.Lock()
    # Character icons used by the model, built on demand. Reset when a game
    # is loaded, which replaces TSHGameAssetManager's stockIcons.
    iconCache = {}
    iconCacheSource = None
    # The fields saved to the database, the others (id, avatar, seed...) are
    # only kept while the program runs
    fieldnames = PLAYER_FIELDS
    saveLock = threading.Lock()

    @staticmethod
    def LoadDB():
        try:
            players = TSHPlayerDB.ReadDB()

            if not players:
                players = TSHPlayerDB.MigrateLegacyFiles()

            for tag, player in players.items():
                if tag not in TSHPlayerDB.database:
                    TSHPlayerDB.database[tag] = player

            TSHPlayerDB.SaveDB()
            TSHPlayerDB.SetupModel()

        except Exception:
            logger.error(traceback.format_exc())

    @staticmethod
    def ReadDB():
        """The players saved in the database, as {tag: player dict}."""
        with Session(GetEngine()) as session:
            rows = session.exec(select(Player)).all()
        return {row.tag: TSHPlayerDB.RowToDict(row) for row in rows}

    @staticmethod
    def RowToDict(row):
        # Unset fields are left out, like they were in the JSON file, so
        # player.get("mains", {}) still gets the default
        return {
            field: getattr(row, field)
            for field in TSHPlayerDB.fieldnames
            if getattr(row, field) is not None
        }

    @staticmethod
    def MigrateLegacyFiles():
        """Imports local_players.json (or the older local_players.csv) into an
        empty database. The file is kept, renamed to .bak."""
        players = {}
        path = None

        if os.path.exists(LEGACY_JSON_PATH):
            path = LEGACY_JSON_PATH
            logger.info("Importing the player database from local_players.json")
            players = TSHPlayerDB.ReadJSON(path)
        elif os.path.exists(LEGACY_CSV_PATH):
            path = LEGACY_CSV_PATH
            logger.info("Importing from the previous version of the player database")
            with open(path, encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile, quotechar="'")
                for player in reader:
                    tag = MakeTag(player.get("prefix"), player.get("gamerTag"))
                    if tag not in players:
                        players[tag] = player
                        logger.info(f"Import player {tag} from old database")
                        try:
                            player["mains"] = json.loads(player.get("mains", "{}"))
                        except:
                            player["mains"] = {}
                            logger.error(f"No mains found for: {tag}")

        if path is None:
            return players

        TSHPlayerDB.WriteDB(players)

        backup = path + ".bak"
        if os.path.exists(backup):
            backup = f"{path}.{int(time.time())}.bak"
        try:
            os.replace(path, backup)
            logger.info(f"Imported {len(players)} players, the old file is now {backup}")
        except Exception:
            logger.error(traceback.format_exc())

        return players

    @staticmethod
    def ReadJSON(path):
        """Players from a JSON file in the format of local_players.json."""
        with open(path, "rb") as jsonfile:
            player_list = orjson.loads(jsonfile.read())

        players = {}
        for player in player_list:
            if not isinstance(player, dict):
                continue
            tag = MakeTag(player.get("prefix"), player.get("gamerTag"))
            if tag and tag not in players:
                if isinstance(player.get("mains"), str):
                    try:
                        player["mains"] = json.loads(player["mains"])
                    except:
                        player["mains"] = {}
                        logger.error(f"No mains found for: {tag}")
                players[tag] = player
        return players

    @staticmethod
    def ImportJSON(path):
        """Adds the players of a local_players.json file. Returns how many."""
        players = list(TSHPlayerDB.ReadJSON(path).values())
        TSHPlayerDB.AddPlayers(players)
        return len(players)

    @staticmethod
    def ExportJSON(path):
        """Saves the players to a file in the format of local_players.json."""
        players = deep_clone(list(TSHPlayerDB.database.values()))
        player_list = [
            {k: v for k, v in player.items() if k in TSHPlayerDB.fieldnames}
            for player in players
            if player is not None
        ]
        with open(path, "wb") as outfile:
            outfile.write(
                orjson.dumps(player_list, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS)
            )

    @staticmethod
    @gui_thread_sync
    def ReloadDB():
        """Loads the players again after the database was edited elsewhere
        (the admin page). Fields that aren't saved are kept."""
        try:
            saved = TSHPlayerDB.ReadDB()
            for tag in list(TSHPlayerDB.database.keys()):
                if tag not in saved:
                    del TSHPlayerDB.database[tag]
            for tag, player in saved.items():
                entry = TSHPlayerDB.database.get(tag)
                if entry is None:
                    TSHPlayerDB.database[tag] = player
                else:
                    for field in TSHPlayerDB.fieldnames:
                        entry.pop(field, None)
                    entry.update(player)
            TSHPlayerDB.SetupModel()
        except Exception:
            logger.error(traceback.format_exc())

    @staticmethod
    def AddPlayers(players, overwrite=False):
        logger.info(f"Adding players to DB: {len(players)}")
        for player in players:
            if player is not None:
                tag = (
                    player.get("prefix") + " " + player.get("gamerTag")
                    if player.get("prefix")
                    else player.get("gamerTag")
                )

                if not overwrite:
                    if tag not in TSHPlayerDB.database:
                        incomingMains = player.get("mains", {})
                        for game in incomingMains:
                            for main in incomingMains[game]:
                                if len(main) == 1:
                                    main.append(0)
                        TSHPlayerDB.database[tag] = player
                    else:
                        dbMains = deep_clone(TSHPlayerDB.database[tag].get("mains", {}))
                        if isinstance(dbMains, str):
                            dbMains = json.loads(dbMains)
                        incomingMains = player.get("mains", {})

                        newMains = []
                        for game in incomingMains:
                            for main in incomingMains[game]:
                                if len(main) == 1:
                                    found = next(
                                        (m for m in dbMains.get(game, []) if m[0] == main[0]), None
                                    )
                                    if found:
                                        main.append(found[1])
                                    else:
                                        main.append(0)
                                newMains.append(main)
                            dbMains[game] = newMains

                        if SettingsManager.Get("general.disable_overwrite", False):
                            TSHPlayerDB.database[tag] = player | TSHPlayerDB.database[tag]
                        else:
                            TSHPlayerDB.database[tag].update(player)
                        TSHPlayerDB.database[tag]["mains"] = dbMains
                else:
                    if (
                        TSHPlayerDB.database.get(tag) is not None
                        and player.get("mains") is not None
                    ):
                        try:
                            mains = TSHPlayerDB.database[tag].get("mains", {})
                            mains.update(player.get("mains", {}))
                            player["mains"] = mains
                        except:
                            logger.error(traceback.format_exc())
                    TSHPlayerDB.database[tag] = player

        TSHPlayerDB.SaveDB()
        TSHPlayerDB.SetupModel()

    @staticmethod
    def DeletePlayer(tag):
        if tag in TSHPlayerDB.database:
            del TSHPlayerDB.database[tag]

        TSHPlayerDB.SaveDB()
        TSHPlayerDB.SetupModel()

    @staticmethod
    def GetTag(player):
        """The key a player is saved under: prefix + gamerTag, or just gamerTag."""
        return MakeTag(player.get("prefix"), player.get("gamerTag"))

    @staticmethod
    def UpdatePlayer(oldTag, player):
        """Saves an edited player, which may have been renamed.

        oldTag is the tag the player was saved under, or None for a new
        player. Fields the editor doesn't know about (id, avatar, seed...)
        are kept. Returns the player's new tag, or None if the new tag is
        empty or already used by another player.
        """
        newTag = TSHPlayerDB.GetTag(player)
        if not newTag:
            return None
        if newTag != oldTag and newTag in TSHPlayerDB.database:
            return None

        entry = deep_clone(TSHPlayerDB.database.get(oldTag) or {}) if oldTag else {}
        entry.update(player)
        entry["prefix"] = (entry.get("prefix") or "").strip()
        entry["gamerTag"] = (entry.get("gamerTag") or "").strip()

        if oldTag is not None and oldTag != newTag:
            TSHPlayerDB.database.pop(oldTag, None)
        TSHPlayerDB.database[newTag] = entry

        TSHPlayerDB.SaveDB()
        TSHPlayerDB.SetupModel()
        return newTag

    @staticmethod
    def DeletePlayers(tags):
        for tag in tags:
            TSHPlayerDB.database.pop(tag, None)

        TSHPlayerDB.SaveDB()
        TSHPlayerDB.SetupModel()

    @staticmethod
    def GetPlayer(tag):
        """Returns a copy of the player saved under tag (prefix + gamerTag), or None."""
        player = TSHPlayerDB.database.get(tag)
        return deep_clone(player) if player is not None else None

    @staticmethod
    def GetPlayerFromTag(tag):
        for player_db in TSHPlayerDB.database.values():
            if tag.lower() == player_db.get("gamerTag").lower():
                return player_db
        return None

    @staticmethod
    @gui_thread_sync
    def SetupModel():
        with TSHPlayerDB.modelLock:
            TSHPlayerDB.model = QStandardItemModel()

            cancelIcon = QIcon(
                QPixmap.fromImage(
                    QImage("./assets/icons/cancel.svg").scaledToWidth(
                        32, Qt.TransformationMode.SmoothTransformation
                    )
                )
            )

            stockIcons = TSHGameAssetManager.instance.stockIcons
            if TSHPlayerDB.iconCacheSource is not stockIcons:
                TSHPlayerDB.iconCache = {}
                TSHPlayerDB.iconCacheSource = stockIcons

            def GetCharIcon(char, skin):
                # Only the icons players actually use get decoded and scaled
                key = (char, skin)
                icon = TSHPlayerDB.iconCache.get(key)
                if icon is None:
                    # Misses aren't cached: stockIcons is filled in after
                    # being assigned, so a missing entry may appear later
                    path = stockIcons.get(char, {}).get(skin)
                    if path:
                        icon = QIcon(
                            QPixmap.fromImage(
                                QImage(path).scaledToWidth(
                                    32, Qt.TransformationMode.SmoothTransformation
                                )
                            )
                        )
                        TSHPlayerDB.iconCache[key] = icon
                return icon

            for player in TSHPlayerDB.database.values():
                if player is not None:
                    try:
                        tag = (
                            player.get("prefix") + " " + player.get("gamerTag")
                            if player.get("prefix")
                            else player.get("gamerTag")
                        )

                        item = QStandardItem(tag)
                        item.setIcon(cancelIcon)

                        if player.get("mains") and type(player.get("mains")) == dict:
                            if (
                                TSHGameAssetManager.instance.selectedGame.get("codename")
                                in player.get("mains", {}).keys()
                            ):
                                playerMains = player.get("mains")[
                                    TSHGameAssetManager.instance.selectedGame.get("codename")
                                ]

                                if playerMains is not None and len(playerMains) > 0:
                                    # Must be a list of size 2 [character, skin]
                                    playerMains = [
                                        main
                                        for main in playerMains
                                        if isinstance(main, list)
                                        and (len(main) == 2)
                                        or (len(main) == 3)
                                    ]

                                    # If the skin is invalid, default to 0
                                    for main in playerMains:
                                        while len(main) < 3:
                                            main.append("")
                                        skin = 0
                                        try:
                                            skin = int(main[1])
                                        except:
                                            logger.error(
                                                f"Local DB error: Player {player.get('gamerTag')} has an invalid skin for character {main[0]}"
                                            )
                                            logger.error(traceback.format_exc())
                                        main[1] = skin

                                        # If no variant, set to none
                                        if len(main) >= 3:
                                            variant = main[2]
                                        else:
                                            variant = ""
                                        main[2] = variant

                                    if (
                                        playerMains[0][0]
                                        in TSHGameAssetManager.instance.characters.keys()
                                    ):
                                        character = playerMains[0]

                                        icon = GetCharIcon(character[0], int(character[1]))
                                        if icon is not None:
                                            item.setIcon(icon)

                        item.setData(player, Qt.ItemDataRole.UserRole)

                        TSHPlayerDB.model.appendRow(item)
                    except:
                        logger.error(
                            f"Error loading player from local DB: {player.get('gamerTag')}"
                        )
                        logger.error(traceback.format_exc())

            TSHPlayerDB.signals.db_updated.emit()

    @staticmethod
    def SaveDB():
        try:
            # One copy of the whole DB, taken in a single call so another
            # thread changing it can't break the loop below
            players = deep_clone(list(TSHPlayerDB.database.values()))
            TSHPlayerDB.WriteDB(
                {MakeTag(p.get("prefix"), p.get("gamerTag")): p for p in players if p is not None}
            )
        except Exception:
            logger.error(traceback.format_exc())

    @staticmethod
    def WriteDB(players):
        """Makes the database hold exactly players ({tag: player dict}), in a
        single transaction. Only rows that changed are written."""
        with TSHPlayerDB.saveLock, Session(GetEngine()) as session:
            rows = {row.tag: row for row in session.exec(select(Player))}
            for tag, player in players.items():
                if not tag:
                    logger.warning(f"Not saving a player without a tag: {player}")
                    continue
                row = rows.pop(tag, None) or Player()
                for field in TSHPlayerDB.fieldnames:
                    value = player.get(field)
                    if field == "mains" and isinstance(value, str):
                        try:
                            value = json.loads(value)
                        except:
                            value = {}
                    elif field != "mains" and value is not None:
                        value = str(value)
                    if getattr(row, field) != value:
                        setattr(row, field, value)
                if row.gamerTag is None:
                    row.gamerTag = ""
                session.add(row)
            # Players no longer in the DB, renamed players' old tags included
            for row in rows.values():
                session.delete(row)
            session.commit()


TSHGameAssetManager.instance.signals.onLoad.connect(TSHPlayerDB.SetupModel)
