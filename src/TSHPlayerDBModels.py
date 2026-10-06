"""SQLite storage of the local player database, as SQLModel tables.

TSHPlayerDB keeps the players in memory and saves them here. The admin page
(/admin, see TSHWebServer) edits these tables directly.
"""

import os
import threading

from sqlalchemy import JSON, Column, event
from sqlalchemy.engine import Engine
from sqlmodel import Field, SQLModel, create_engine

DB_PATH = "./user_data/players.db"


def MakeTag(prefix, gamerTag):
    """The key a player is saved under: prefix + gamerTag, or just gamerTag."""
    prefix = (prefix or "").strip()
    gamerTag = (gamerTag or "").strip()
    return prefix + " " + gamerTag if prefix else gamerTag


class Player(SQLModel, table=True):
    __tablename__ = "players"

    id: int | None = Field(default=None, primary_key=True)
    # prefix + gamerTag, kept up to date by the events below
    tag: str = Field(default="", index=True, unique=True)
    prefix: str | None = None
    gamerTag: str = ""
    name: str | None = None
    twitter: str | None = None
    country_code: str | None = None
    state_code: str | None = None
    # {game codename: [[character, skin, variant], ...]}
    mains: dict | None = Field(default=None, sa_column=Column(JSON))
    pronoun: str | None = None
    custom_textbox: str | None = None

    def __str__(self):
        return self.tag


# Columns saved from the players' dicts (everything but id and tag)
PLAYER_FIELDS = [name for name in Player.model_fields if name not in ("id", "tag")]


@event.listens_for(Player, "before_insert")
@event.listens_for(Player, "before_update")
def _UpdateTag(mapper, connection, player):
    player.prefix = (player.prefix or "").strip()
    player.gamerTag = (player.gamerTag or "").strip()
    player.tag = MakeTag(player.prefix, player.gamerTag)


_engine: Engine | None = None
_engineLock = threading.Lock()


def GetEngine() -> Engine:
    """The engine of DB_PATH, created with its tables on first use."""
    global _engine
    with _engineLock:
        if _engine is None:
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            # Used from the GUI thread, workers and the web server
            _engine = create_engine(
                f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False}
            )
            SQLModel.metadata.create_all(_engine)
        return _engine


def ResetEngine():
    """Closes the engine, so the next GetEngine opens DB_PATH again."""
    global _engine
    with _engineLock:
        if _engine is not None:
            _engine.dispose()
            _engine = None
