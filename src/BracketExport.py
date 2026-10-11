# A bracket as the layouts get it (bracket.channels.<channel>.bracket, and
# bracket.bracket for the main channel, see docs/layout-data.md).
from .BracketModel import *
from .BracketView import SourceText
from .StateManager import StateManager


def RosterPath(key="local"):
    """Where a player list is in the state: "local" for the phases built in
    the bracket widget, a start.gg phase group's id for its entrants."""
    return f"bracket.rosters.{key}"


def TeamName(playerId, players=None):
    """A player slot's name, from the player list kept at players (the
    phases built in the bracket widget's by default)."""
    players = players or RosterPath()
    if playerId is None or playerId <= 0:
        return ""
    team = StateManager.Get(f"{players}.slot.{playerId}", {}) or {}
    if team.get("name"):
        return team.get("name")
    return " / ".join(
        [p.get("name", "") for p in (team.get("player") or {}).values() if p.get("name")]
    )


def PlayerExport(bracket, m, slot, teamName):
    player = m.players[slot]
    return {
        "id": player if player > 0 else None,
        "seed": bracket.SeedOf(player) if player > 0 and bracket.SeedOf(player) != 9999 else None,
        "name": teamName(player) if player > 0 else "",
        "bye": player == BYE,
        "pending": player == PENDING,
        # What the slot waits for, e.g. "Winner of C"
        "source": SourceText(bracket, m.sources[slot]) if player == PENDING else "",
        "manual": m.override[slot] is not None,
    }


def ExportBracket(bracket, name, limit=None, players=None):
    """The bracket's export. limit: only its top N (elimination); players:
    where its player list is in the state."""

    players = players or RosterPath()

    def teamName(p):
        return TeamName(p, players)

    limit = limit if not bracket.IsPool() else None
    included = {
        m.id
        for m in bracket.matches.values()
        if not m.isBye and (limit is None or bracket.InTopN(m, limit))
    }

    sets = {}
    for m in bracket.matches.values():
        if m.id not in included:
            continue
        winner = None
        if m.winnerSlot is not None and m.finished:
            winner = m.winnerSlot
        elif m.IsDraw():
            winner = "draw"

        def Next(link):
            if link is None or link[0] not in included:
                return None
            return {"set": link[0], "slot": link[1]}

        sets[m.id] = {
            "id": m.id,
            "identifier": m.identifier,
            "side": m.side,
            "column": m.column,
            "row": m.row,
            "roundName": bracket.RoundName(m.side, m.column),
            "players": [PlayerExport(bracket, m, slot, teamName) for slot in range(2)],
            "score": list(m.score),
            "completed": bool(m.finished),
            # 0 or 1 for the slot that won, "draw" or None
            "winner": winner,
            "nextWin": Next(m.nextWin),
            "nextLose": Next(m.nextLose),
            "loserPlacement": bracket.LoserPlacementOf(m) if not bracket.IsPool() else None,
            "isGrandFinal": m.isGrandFinal,
            "isReset": m.isReset,
            "resetNeeded": not m.notNeeded,
            "startggId": m.providerId,
        }

    sides = {}
    for side in SIDES:
        columns = []
        for column in bracket.Columns(side, includeHidden=side == SIDE_GRAND_FINAL):
            ids = [m.id for m in column if m.id in included]
            if not ids:
                continue
            columns.append(
                {
                    "key": Bracket.RoundKey(side, column[0].column),
                    "name": bracket.RoundName(side, column[0].column),
                    "sets": ids,
                }
            )
        if columns:
            sides[side] = columns

    data = {
        "type": bracket.type,
        "name": name,
        "fromStartgg": bracket.fromProvider,
        "progressionsOut": bracket.progressionsOut,
        "limitExportNumber": limit,
        "sides": sides,
        "sets": sets,
    }

    if bracket.IsPool():
        standings = bracket.GetStandings()
        data["standings"] = [dict(row, name=teamName(row["playerId"])) for row in standings]
        data["totalRounds"] = bracket.totalRounds
        data["byes"] = {
            Bracket.RoundKey(SIDE_POOL, int(r)): [{"id": p, "name": teamName(p)} for p in out]
            for r, out in bracket.byes.items()
        }
    else:
        results = []
        for i, player in enumerate(bracket.Results()):
            if player > 0:
                results.append({"order": i + 1, "id": player, "name": teamName(player)})
        data["results"] = results

    return data
