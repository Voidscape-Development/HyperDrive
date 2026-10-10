# What the bracket focus layouts (layout/bracket_focus) zoom to: sets of the
# bracket widget's export (bracket.bracket, see docs/layout-data.md) picked
# by hand, whole rounds, a player's run, the set on a scoreboard or a tour of
# every round. No Qt here, so it can be tested on its own.

MODE_ALL = "all"
MODE_SETS = "sets"
MODE_ROUNDS = "rounds"
MODE_PLAYER = "player"
MODE_FOLLOW = "follow"
MODE_TOUR = "tour"
MODES = (MODE_ALL, MODE_SETS, MODE_ROUNDS, MODE_PLAYER, MODE_FOLLOW, MODE_TOUR)

# Order the tour goes through the sides
TOUR_SIDES = ("pool", "winners", "losers", "third_place", "grand_final")

# Every layout without ?channel= shows this one
MAIN_CHANNEL = "main"
MAX_CHANNEL_NAME = 40

DEFAULT_INTERVAL = 8
MIN_INTERVAL = 2
MAX_INTERVAL = 300


def NormalizeChannelName(name):
    """A channel's name as it's kept: its key in bracket.focus and the
    layouts' ?channel=, so without dots (they separate state keys) or extra
    spaces. Empty if there's nothing left."""
    name = " ".join(str(name or "").replace(".", " ").split())
    return name[:MAX_CHANNEL_NAME].strip()


def NormalizeRequest(request):
    """A focus request from the app, a hotkey or the web page, with only the
    keys its mode uses and sane values."""
    request = request if isinstance(request, dict) else {}
    mode = request.get("mode")
    if mode not in MODES:
        mode = MODE_ALL
    result = {"mode": mode}
    if mode in (MODE_SETS, MODE_ROUNDS):
        # Picked by hand: sets, rounds or both
        result["sets"] = [str(s) for s in request.get("sets") or [] if s not in (None, "")]
        result["rounds"] = [str(r) for r in request.get("rounds") or [] if r not in (None, "")]
    elif mode == MODE_PLAYER:
        try:
            result["player"] = int(request.get("player"))
        except (TypeError, ValueError):
            result["player"] = None
    elif mode == MODE_FOLLOW:
        try:
            result["scoreboard"] = max(1, int(request.get("scoreboard") or 1))
        except (TypeError, ValueError):
            result["scoreboard"] = 1
    elif mode == MODE_TOUR:
        try:
            interval = int(request.get("interval") or DEFAULT_INTERVAL)
        except (TypeError, ValueError):
            interval = DEFAULT_INTERVAL
        result["interval"] = max(MIN_INTERVAL, min(MAX_INTERVAL, interval))
    return result


def WithoutPicks(request, sets=(), rounds=()):
    """A request picked by hand with these sets and rounds taken out of it
    (deselected in the bracket widget), the whole bracket once nothing is
    left, or None if they weren't in it or it wasn't picked by hand."""
    request = NormalizeRequest(request)
    if request["mode"] not in (MODE_SETS, MODE_ROUNDS):
        return None
    sets, rounds = {str(s) for s in sets or []}, {str(r) for r in rounds or []}
    keptSets = [s for s in request["sets"] if s not in sets]
    keptRounds = [r for r in request["rounds"] if r not in rounds]
    if keptSets == request["sets"] and keptRounds == request["rounds"]:
        return None
    if not keptSets and not keptRounds:
        return {"mode": MODE_ALL}
    mode = MODE_SETS if keptSets else MODE_ROUNDS
    return {"mode": mode, "sets": keptSets, "rounds": keptRounds}


def Columns(bracket):
    """Every column of the bracket, in tour order."""
    sides = (bracket or {}).get("sides") or {}
    columns = []
    for side in TOUR_SIDES:
        for column in sides.get(side) or []:
            columns.append(column)
    return columns


def RoundSets(bracket, keys):
    """The sets of the rounds with these keys, and the keys that exist."""
    keys = set(keys or [])
    sets, found = [], []
    for column in Columns(bracket):
        if column.get("key") in keys:
            found.append(column.get("key"))
            sets.extend(column.get("sets") or [])
    return sets, found


def PlayerSets(bracket, player):
    """The sets a player (slot in bracket.players.slot) plays in, in the
    order they're played: by side then column."""
    if not player:
        return []
    sets = []
    for column in Columns(bracket):
        for id in column.get("sets") or []:
            s = ((bracket or {}).get("sets") or {}).get(id) or {}
            if any((p or {}).get("id") == player for p in s.get("players") or []):
                sets.append(id)
    return sets


def PlayerName(bracket, player):
    for s in ((bracket or {}).get("sets") or {}).values():
        for p in s.get("players") or []:
            if (p or {}).get("id") == player and p.get("name"):
                return p.get("name")
    return ""


def _Normalize(name):
    return " ".join(str(name or "").split()).casefold()


def TeamNames(team):
    """Names a scoreboard team (score.N.team.T) can go by in the bracket:
    its team name, its players' names (with and without sponsor), and its
    players' names together."""
    team = team or {}
    names = set()
    for key in ("teamName", "mergedTeamName"):
        if team.get(key):
            names.add(_Normalize(team.get(key)))
    players = [p for p in (team.get("player") or {}).values() if isinstance(p, dict)]
    for p in players:
        for key in ("name", "mergedName"):
            if p.get(key):
                names.add(_Normalize(p.get(key)))
    together = [p.get("name") for p in players if p.get("name")]
    if together:
        names.add(_Normalize(" / ".join(together)))
    names.discard("")
    return names


def FollowSet(bracket, score):
    """The set of the bracket a scoreboard (score.N) shows: the one with its
    start.gg set id, else the one between its two teams (an unfinished one
    first). None if there's none."""
    score = score or {}
    sets = (bracket or {}).get("sets") or {}

    setId = score.get("set_id")
    if setId not in (None, ""):
        for id, s in sets.items():
            if s.get("startggId") not in (None, "") and str(s.get("startggId")) == str(setId):
                return id

    teams = score.get("team") or {}
    names1 = TeamNames(teams.get("1"))
    names2 = TeamNames(teams.get("2"))
    if not names1 or not names2:
        return None

    found = []
    for column in Columns(bracket):
        for id in column.get("sets") or []:
            s = sets.get(id) or {}
            players = s.get("players") or []
            if len(players) < 2 or not all((p or {}).get("id") for p in players):
                continue
            a, b = (_Normalize(p.get("name")) for p in players[:2])
            if (a in names1 and b in names2) or (a in names2 and b in names1):
                found.append((bool(s.get("completed")), id))
    if not found:
        return None
    # An unfinished set first; of finished ones (e.g. a grand final and its
    # reset), the last
    unfinished = [id for completed, id in found if not completed]
    return unfinished[0] if unfinished else found[-1][1]


def TourSteps(bracket):
    """The tour's steps: the whole bracket, then each round."""
    steps = [{"label": "", "rounds": [], "sets": []}]
    for column in Columns(bracket):
        if column.get("sets"):
            steps.append(
                {
                    "label": column.get("name") or "",
                    "rounds": [column.get("key")],
                    "sets": list(column.get("sets")),
                }
            )
    return steps


def Resolve(bracket, request, score=None, step=0):
    """What the layouts show for a request: bracket.focus. `sets` are the
    sets to zoom to and highlight (none: the whole bracket), `rounds` the
    rounds to highlight, `label` says what it is."""
    request = NormalizeRequest(request)
    mode = request["mode"]
    bracket = bracket or {}
    allSets = bracket.get("sets") or {}

    focus = dict(request)
    focus.update({"sets": [], "rounds": [], "label": ""})

    if mode in (MODE_SETS, MODE_ROUNDS):
        roundSets, found = RoundSets(bracket, request["rounds"])
        picked = set(roundSets) | set(request["sets"])
        # In the bracket's order
        focus["sets"] = [
            id
            for c in Columns(bracket)
            for id in c.get("sets") or []
            if id in picked and id in allSets
        ]
        focus["rounds"] = found
        if found and set(focus["sets"]) <= set(roundSets):
            focus["label"] = ", ".join(
                c.get("name") or "" for c in Columns(bracket) if c.get("key") in found
            )
        elif focus["sets"] and len({allSets[id].get("roundName") for id in focus["sets"]}) == 1:
            focus["label"] = allSets[focus["sets"][0]].get("roundName") or ""
    elif mode == MODE_PLAYER:
        focus["sets"] = [id for id in PlayerSets(bracket, request["player"]) if id in allSets]
        focus["label"] = PlayerName(bracket, request["player"]) if focus["sets"] else ""
    elif mode == MODE_FOLLOW:
        id = FollowSet(bracket, score)
        if id is not None:
            focus["sets"] = [id]
            focus["label"] = allSets[id].get("roundName") or ""
    elif mode == MODE_TOUR:
        steps = TourSteps(bracket)
        step = step % len(steps)
        focus["step"] = step
        focus["steps"] = len(steps)
        focus["sets"] = [id for id in steps[step]["sets"] if id in allSets]
        focus["rounds"] = steps[step]["rounds"]
        focus["label"] = steps[step]["label"]

    return focus


def NextRound(bracket, focus, offset=1):
    """The round after (or before, with a negative offset) the one in
    focus, as a rounds request. From the whole bracket, the first round
    (or the last one going back)."""
    keys = [c.get("key") for c in Columns(bracket) if c.get("sets")]
    if not keys:
        return {"mode": MODE_ALL}
    focus = focus or {}
    current = None
    if focus.get("rounds"):
        current = keys.index(focus["rounds"][0]) if focus["rounds"][0] in keys else None
    elif focus.get("sets"):
        # The round of the first set in focus
        for i, column in enumerate(c for c in Columns(bracket) if c.get("sets")):
            if focus["sets"][0] in column.get("sets"):
                current = i
                break
    if current is None:
        index = 0 if offset > 0 else len(keys) - 1
    else:
        index = (current + offset) % len(keys)
    return {"mode": MODE_ROUNDS, "rounds": [keys[index]]}
