# What the event's completed sets add up to: how long sets take (for the
# stream queue's estimated start times), the characters and stages played,
# the biggest upsets and the players doing better or worse than their seed.
# Also the event's schedule, from its phases and waves.
#
# The sets come from a provider's GetEventStatsSets: {id, started_at,
# completed_at, total_games, round_name, phase_name, phase_id, bracket_type,
# winner (slot 0 or 1), scores, dq, entrants: [{id, name, seed, players:
# [{id, gamertag, sponsor}]}], games: [{winner, stage_id, stage_name,
# selections: [{slot, character_id}]}]}.
#
# Nothing in here depends on Qt, so it can be tested on its own.
import time
from datetime import datetime
from statistics import median

from .Helpers.CompletedSetsHelper import UpsetFactor
from .Helpers.SeedPerformance import DOUBLE_ELIMINATION, SeedPerformanceRating

# Sets shorter or longer than this are left out of the durations: a set
# reported long after it was played, or one started by mistake
MIN_SET_SECS = 60
MAX_SET_SECS = 3 * 60 * 60
# Durations of sets of the same length (best of 3, best of 5...) are only
# used once there are this many
MIN_SAMPLES = 3

TOP_UPSETS = 10
TOP_PERFORMERS = 8


def SetDuration(startedAt, completedAt):
    """Seconds the set took, or None if it can't be told or doesn't look
    like a real set."""
    try:
        seconds = int(completedAt) - int(startedAt)
    except (TypeError, ValueError):
        return None
    if not MIN_SET_SECS <= seconds <= MAX_SET_SECS:
        return None
    return seconds


def Durations(sets):
    """{best of (or None for every set): [seconds]} of completed sets.
    `sets` have startedAt/completedAt/totalGames/dq (GetSetDurations) or
    started_at/completed_at/total_games/dq (GetEventStatsSets)."""
    result = {None: []}
    for s in sets or []:
        if not s or s.get("dq"):
            continue
        seconds = SetDuration(
            s.get("startedAt", s.get("started_at")), s.get("completedAt", s.get("completed_at"))
        )
        if seconds is None:
            continue
        result[None].append(seconds)
        bestOf = s.get("totalGames", s.get("total_games"))
        if bestOf:
            result.setdefault(int(bestOf), []).append(seconds)
    return result


def SetSeconds(durations, bestOf=None):
    """How long a set (of that length, when there's enough data on those)
    takes, or None without data."""
    durations = durations or {}
    try:
        bestOf = int(bestOf) if bestOf else None
    except (TypeError, ValueError):
        bestOf = None
    samples = durations.get(bestOf) or []
    if bestOf is None or len(samples) < MIN_SAMPLES:
        samples = durations.get(None) or []
    if not samples:
        return None
    return int(median(samples))


def EstimateStarts(sets, durations, now=None):
    """When each set of a stream's queue (next set first) should start,
    with each set taking as long as sets usually do. Sets in progress
    count for what's left of them. Returns [(eta, minutes from now)] in
    the same order, (None, None) for sets it can't tell (no data yet, or
    finished)."""
    now = time.time() if now is None else now
    result = []
    t = now
    known = True
    for s in sets or []:
        s = s or {}
        seconds = SetSeconds(durations, s.get("best_of"))
        if s.get("state") == 3:
            result.append((None, None))
            continue
        if seconds is None:
            known = False
        if s.get("state") == 2:
            # Already started: it ends when a set usually would
            started = s.get("started_at")
            if seconds is not None:
                elapsed = max(0, now - started) if started else 0
                t = max(t, now + max(0, seconds - elapsed))
            result.append((int(started) if started else int(now), 0))
            continue
        if not known:
            result.append((None, None))
            continue
        result.append((int(t), max(0, round((t - now) / 60))))
        t += seconds
    return result


def _PlayerName(player):
    sponsor = player.get("sponsor") or ""
    gamertag = player.get("gamertag") or ""
    return f"{sponsor} | {gamertag}" if sponsor else gamertag


def _EntrantInfo(entrant):
    players = entrant.get("players") or []
    return {
        "name": entrant.get("name") or " / ".join(_PlayerName(p) for p in players),
        "seed": entrant.get("seed"),
        "players": {
            str(i + 1): {"gamertag": p.get("gamertag") or "", "sponsor": p.get("sponsor") or ""}
            for i, p in enumerate(players)
        },
    }


def Upsets(sets, top=TOP_UPSETS):
    """The biggest upsets: sets won by the worse seed, the furthest apart
    in expected placement first."""
    upsets = []
    for s in sets or []:
        if s.get("dq") or s.get("winner") not in (0, 1) or len(s.get("entrants") or []) < 2:
            continue
        winner = s["entrants"][s["winner"]]
        loser = s["entrants"][1 - s["winner"]]
        factor = UpsetFactor(s.get("bracket_type"), winner.get("seed"), loser.get("seed"))
        if factor <= 0:
            continue
        scores = s.get("scores") or [None, None]
        upsets.append(
            {
                "upset_factor": factor,
                "winner": _EntrantInfo(winner),
                "loser": _EntrantInfo(loser),
                "winner_score": scores[s["winner"]],
                "loser_score": scores[1 - s["winner"]],
                "round_name": s.get("round_name") or "",
                "phase_name": s.get("phase_name") or "",
                "phase_id": s.get("phase_id") or "",
                "completed_at": s.get("completed_at"),
            }
        )
    upsets.sort(
        key=lambda u: (
            -u["upset_factor"],
            -(int(u["winner"]["seed"] or 0) - int(u["loser"]["seed"] or 0)),
            -(u.get("completed_at") or 0),
        )
    )
    return upsets[:top]


def Performers(standings, bracketType=DOUBLE_ELIMINATION, top=TOP_PERFORMERS):
    """Players who placed better (over) or worse (under) than their seed,
    by Seed Performance Rating. Only placements that are final count.
    Returns (over, under)."""
    rated = []
    for s in standings or []:
        if not s.get("final"):
            continue
        spr = SeedPerformanceRating(bracketType, s.get("seed"), s.get("placement"))
        if spr is None or spr == 0:
            continue
        info = _EntrantInfo(s)
        info.update({"placement": s.get("placement"), "spr": spr})
        rated.append(info)
    over = sorted([r for r in rated if r["spr"] > 0], key=lambda r: (-r["spr"], r["placement"]))
    under = sorted([r for r in rated if r["spr"] < 0], key=lambda r: (r["spr"], r["placement"]))
    return over[:top], under[:top]


def Usage(sets, character=lambda id: None, stage=lambda id, name: None):
    """Games played and won by each character, and games played on each
    stage. character(start.gg id) gives {"key", ...the character's data for
    layouts} or None; stage(start.gg id, name) gives {"key", ...} or None.
    Returns (characters, stages), most played first."""
    characters = {}
    stages = {}
    for s in sets or []:
        if s.get("dq"):
            continue
        for game in s.get("games") or []:
            for selection in game.get("selections") or []:
                data = character(selection.get("character_id"))
                if not data:
                    continue
                entry = characters.setdefault(
                    data["key"], dict(data, games=0, wins=0, sets=set(), players=set())
                )
                # A character played by both players is counted for each
                entry["games"] += 1
                if game.get("winner") is not None and selection.get("slot") == game.get("winner"):
                    entry["wins"] += 1
                entry["sets"].add(s.get("id"))
                slot = selection.get("slot")
                if slot is not None and slot < len(s.get("entrants") or []):
                    for p in s["entrants"][slot].get("players") or []:
                        entry["players"].add(p.get("id") or p.get("gamertag"))
            if game.get("stage_id") is not None or game.get("stage_name"):
                data = stage(game.get("stage_id"), game.get("stage_name")) or {
                    "key": str(game.get("stage_id") or game.get("stage_name")),
                    "name": game.get("stage_name") or "",
                }
                entry = stages.setdefault(data["key"], dict(data, games=0))
                entry["games"] += 1

    def Finish(entry):
        entry = dict(entry)
        entry["sets"] = len(entry["sets"])
        entry["players"] = len(entry["players"])
        entry["win_rate"] = round(100 * entry["wins"] / entry["games"]) if entry["games"] else 0
        entry.pop("key", None)
        return entry

    characters = sorted(characters.values(), key=lambda c: (-c["games"], -c["wins"]))
    totalGames = sum(c["games"] for c in characters)
    characterList = []
    for c in characters:
        c = Finish(c)
        c["play_rate"] = round(100 * c["games"] / totalGames) if totalGames else 0
        characterList.append(c)

    stageList = sorted(stages.values(), key=lambda s: -s["games"])
    totalStages = sum(s["games"] for s in stageList)
    for s in stageList:
        s.pop("key", None)
        s["play_rate"] = round(100 * s["games"] / totalStages) if totalStages else 0
    return characterList, stageList


def Numbered(items):
    """{"1": first, "2": second...}, the way layouts get lists."""
    return {str(i + 1): item for i, item in enumerate(items or [])}


def BuildEventStats(
    sets, standings=None, character=lambda id: None, stage=lambda id, name: None, now=None
):
    """Everything for the event_stats layouts. `standings` is a provider's
    GetEventStandings."""
    sets = [s for s in sets or [] if s]
    characters, stages = Usage(sets, character, stage)
    over, under = Performers(
        (standings or {}).get("standings"), (standings or {}).get("bracket_type")
    )
    played = [s for s in sets if not s.get("dq")]
    setSeconds = SetSeconds(Durations(sets))
    return {
        "updated": int(time.time() if now is None else now),
        "sets": len(played),
        "games": sum(len(s.get("games") or []) for s in played),
        "dqs": len(sets) - len(played),
        "average_set_minutes": round(setSeconds / 60) if setSeconds else None,
        "characters": Numbered(characters),
        "stages": Numbered(stages),
        "upsets": Numbered(Upsets(sets)),
        "overperformers": Numbered(over),
        "underperformers": Numbered(under),
        "event_completed": bool((standings or {}).get("completed")),
    }


# Schedule

STATE_UPCOMING = "upcoming"
STATE_ACTIVE = "active"
STATE_COMPLETED = "completed"


def _State(state):
    """start.gg gives phases "CREATED"/"ACTIVE"/"COMPLETED" and phase
    groups 1/2/3."""
    if state in ("ACTIVE", 2, "2"):
        return STATE_ACTIVE
    if state in ("COMPLETED", 3, "3"):
        return STATE_COMPLETED
    return STATE_UPCOMING


def _Overall(states):
    states = list(states)
    if states and all(s == STATE_COMPLETED for s in states):
        return STATE_COMPLETED
    if any(s in (STATE_ACTIVE, STATE_COMPLETED) for s in states):
        return STATE_ACTIVE
    return STATE_UPCOMING


def _Time(timestamp, fmt):
    if not timestamp:
        return ""
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime(fmt)
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def _When(timestamp):
    return {
        "start_at": int(timestamp) if timestamp else None,
        # In the computer's time zone
        "time": _Time(timestamp, "%H:%M"),
        "date": _Time(timestamp, "%Y-%m-%d"),
        "weekday": _Time(timestamp, "%A"),
    }


def BuildSchedule(schedule, now=None):
    """The event's phases and waves in order, for the schedule layout.
    `schedule` is a provider's GetSchedule."""
    now = time.time() if now is None else now
    schedule = schedule or {}
    groups = schedule.get("groups") or []
    phases = []
    for phase in sorted(schedule.get("phases") or [], key=lambda p: p.get("order") or 0):
        phaseGroups = [g for g in groups if str(g.get("phaseId")) == str(phase.get("id"))]
        starts = [g.get("startAt") or g.get("waveStartAt") for g in phaseGroups]
        starts = [s for s in starts if s]
        groupStates = [_State(g.get("state")) for g in phaseGroups]
        state = _State(phase.get("state"))
        if groupStates and state != STATE_COMPLETED:
            state = _Overall(groupStates) if state == STATE_UPCOMING else state
        waves = []
        for g in sorted(phaseGroups, key=lambda g: g.get("startAt") or g.get("waveStartAt") or 0):
            if g.get("wave") and g["wave"] not in waves:
                waves.append(g["wave"])
        entry = {
            "name": phase.get("name") or "",
            "state": state,
            "groups": phase.get("groupCount") or len(phaseGroups),
            "bracket_type": phase.get("bracketType"),
            "waves": waves,
        }
        entry.update(_When(min(starts) if starts else None))
        phases.append(entry)

    phaseNames = {str(p.get("id")): p.get("name") or "" for p in schedule.get("phases") or []}
    waves = {}
    for g in groups:
        if not g.get("wave"):
            continue
        wave = waves.setdefault(
            g["wave"],
            {
                "identifier": g["wave"],
                "start": g.get("waveStartAt") or g.get("startAt"),
                "phases": [],
                "pools": [],
                "states": [],
            },
        )
        name = phaseNames.get(str(g.get("phaseId")), "")
        if name and name not in wave["phases"]:
            wave["phases"].append(name)
        if g.get("identifier"):
            wave["pools"].append(g["identifier"])
        wave["states"].append(_State(g.get("state")))
    waveList = []
    for wave in sorted(waves.values(), key=lambda w: (w["start"] or 0, w["identifier"])):
        entry = {
            "identifier": wave["identifier"],
            "phases": wave["phases"],
            "pools": sorted(wave["pools"]),
            "state": _Overall(wave["states"]),
        }
        entry.update(_When(wave["start"]))
        waveList.append(entry)

    # What's next: the first wave (or phase, without waves) that hasn't started
    upcoming = [w for w in waveList if w["state"] == STATE_UPCOMING] or [
        p for p in phases if p["state"] == STATE_UPCOMING
    ]
    nextItem = upcoming[0] if upcoming else None
    if nextItem and nextItem.get("start_at"):
        nextItem = dict(nextItem, minutes=max(0, round((nextItem["start_at"] - now) / 60)))
    return {
        "event_start": _When(schedule.get("startAt")),
        "phases": Numbered(phases),
        "waves": Numbered(waveList),
        "next": nextItem,
    }
