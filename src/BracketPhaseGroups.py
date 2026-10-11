# start.gg phase groups focus channels are pinned to, loaded on their own
# (the bracket widget's phases stay as they are). Each is sent to the layouts
# as bracket.groups.<id>: its bracket, its players and its names, like
# bracket.bracket, bracket.players, bracket.phase and bracket.phaseGroup.
import traceback

from loguru import logger
from qtpy.QtCore import *

from .BracketExport import ExportBracket
from .BracketModel import *
from .PlayerList import PlayerList
from .StateManager import StateManager
from .TournamentDataManager import TournamentDataManager


def GroupPath(id):
    return f"bracket.groups.{id}"


class PhaseGroup:
    def __init__(self, id, info):
        self.id = id
        # {"phase", "group", "bracketType"}
        self.info = info
        self.bracket = None
        self.players: PlayerList = None
        self.loading = False

    def Name(self):
        phase, group = self.info.get("phase") or "", self.info.get("group") or ""
        return f"{phase} - {group}" if phase and group else phase or group


class PhaseGroupBracketsSignals(QObject):
    # A group's bracket was loaded or updated (its id)
    changed = Signal(str)


class PhaseGroupBrackets(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = PhaseGroupBracketsSignals()
        self.groups: dict[str, PhaseGroup] = {}

    def Bracket(self, id):
        return StateManager.Get(f"{GroupPath(id)}.bracket", {}) or {}

    def Keep(self, wanted):
        """Loads the groups in wanted ({id: info}) not loaded yet, and drops
        the others."""
        wanted = {str(id): info for id, info in (wanted or {}).items()}
        for id in [id for id in self.groups if id not in wanted]:
            group = self.groups.pop(id)
            if group.players is not None:
                group.players.deleteLater()
            StateManager.Unset(GroupPath(id))
        for id, info in wanted.items():
            if id not in self.groups:
                self.groups[id] = PhaseGroup(id, dict(info or {}))
                StateManager.Set(
                    GroupPath(id),
                    {"phase": info.get("phase") or "", "phaseGroup": info.get("group") or ""},
                )
            else:
                self.groups[id].info.update(info or {})
        self.LoadMissing()

    def LoadMissing(self):
        """Loads the groups that aren't, e.g. once connected to start.gg."""
        for id, group in self.groups.items():
            if group.bracket is None and not group.loading:
                self.Load(id)

    def Load(self, id):
        group = self.groups.get(id)
        manager = TournamentDataManager.instance
        if group is None or manager is None or manager.provider is None:
            return
        if not getattr(manager.provider, "SUPPORTS_BRACKETS", False):
            return
        group.loading = True
        manager.GetTournamentPhaseGroup(id, callback=lambda data, id=id: self.Loaded(id, data))

    def Loaded(self, id, data):
        group = self.groups.get(id)
        if group is None:
            return
        group.loading = False
        entrants = (data or {}).get("entrants") or []
        sets = (data or {}).get("sets")
        if not entrants or not sets:
            logger.warning(f"Phase group {id} came back without entrants or sets")
            return
        try:
            bracket = FromProviderSets(
                group.info.get("bracketType") or TYPE_DOUBLE_ELIMINATION,
                sets,
                len(entrants),
                data.get("entrantIds"),
                progressionsOut=data.get("progressionsOut") or 0,
            )
        except Exception:
            logger.error(traceback.format_exc())
            logger.error(f"Couldn't build phase group {id}'s bracket")
            return
        if group.bracket is not None:
            bracket.roundNames = group.bracket.roundNames
        group.bracket = bracket

        with StateManager.SaveBlock():
            if group.players is None:
                group.players = PlayerList(base=f"{GroupPath(id)}.players")
            group.players.LoadFromStandings(entrants, enrichBlocking=False)
        self.Export(id)

    def Export(self, id):
        group = self.groups.get(id)
        if group is None or group.bracket is None:
            return
        path = GroupPath(id)
        StateManager.Set(f"{path}.phase", group.info.get("phase") or "")
        StateManager.Set(f"{path}.phaseGroup", group.info.get("group") or "")
        StateManager.Set(
            f"{path}.bracket",
            ExportBracket(group.bracket, group.Name(), players=f"{path}.players"),
        )
        self.signals.changed.emit(id)

    def Refresh(self, done=None):
        """Fetches the results of every loaded group again; done is called
        once they're all in."""
        manager = TournamentDataManager.instance
        loaded = [id for id, g in self.groups.items() if g.bracket is not None]
        if manager is None or manager.provider is None or not loaded:
            self.LoadMissing()
            if done:
                done()
            return
        remaining = {"count": len(loaded)}

        def finished():
            remaining["count"] -= 1
            if remaining["count"] == 0 and done:
                done()

        for id in loaded:
            manager.GetTournamentPhaseGroupSets(
                id, onFinished=finished, callback=lambda update: self.SetsUpdated(update)
            )
        self.LoadMissing()

    def SetsUpdated(self, update):
        id = str(update.get("phaseGroupId"))
        group = self.groups.get(id)
        sets = (update.get("data") or {}).get("sets") or []
        if group is None or group.bracket is None or not sets:
            return
        try:
            if not ApplyProviderUpdate(group.bracket, sets):
                # Its sets changed since it was loaded
                self.Load(id)
                return
        except Exception:
            logger.error(traceback.format_exc())
            return
        self.Export(id)
