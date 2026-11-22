# Where the bracket focus layouts place a channel's bracket (an
# ExportBracket(), see docs/layout-data.md), in world pixels before zooming:
# each set, round name and pool round's byes, the lines from each set to
# where its winner goes, and the world's size. Exported with each channel
# (bracket.channels.<channel>.placement) for layout/bracket_focus and the
# OBS plugin's native bracket focus source. No Qt here, so it can be tested
# on its own.

PLAYER_H = 40
SET_GAP = 2
SET_W = 380
SET_H = PLAYER_H * 2 + SET_GAP
COLUMN_GAP = 100
ROW_GAP = 24
HEADER_H = 56
SECTION_GAP = 90
MARGIN = 40
STANDINGS_W = 800
POOL_TYPES = ("ROUND_ROBIN", "SWISS")


def _Box(x, y, w, h=None):
    return {"x": x, "y": y, "w": w} if h is None else {"x": x, "y": y, "w": w, "h": h}


def _Columns(bracket, side):
    return [{**c, "side": side} for c in (bracket.get("sides") or {}).get(side) or []]


def Areas(bracket):
    """Columns of the upper part (winners, grand finals) and lower part
    (losers, then the 3rd place match, which goes on top without losers)."""
    upper = _Columns(bracket, "winners") + _Columns(bracket, "grand_final")
    losers = _Columns(bracket, "losers")
    third = _Columns(bracket, "third_place")
    return (upper + third, []) if not losers else (upper, losers + third)


def _Shown(set_):
    # Every set, but a grand final reset only when it's needed
    return bool(set_) and not (set_.get("isReset") and set_.get("resetNeeded") is False)


def _PlaceArea(columns, sets, top, result):
    """Places one part's columns from top, each set level with the sets
    feeding it. Returns the part's bottom."""
    bottom = top
    last_x = MARGIN
    area = {i for c in columns for i in c["sets"]}
    feeders = {}
    for i in area:
        nxt = (sets.get(i) or {}).get("nextWin")
        if nxt:
            feeders.setdefault(nxt["set"], []).append(i)

    shown, third = [], []
    for column in columns:
        if column["side"] == "third_place":
            third.append(column)
            continue
        ids = [i for i in column["sets"] if _Shown(sets.get(i))]
        if ids:
            last_x = MARGIN + len(shown) * (SET_W + COLUMN_GAP)
            shown.append((column, ids, last_x))

    # Play-in rounds (fewer sets than the round after them) are placed last,
    # each set level with the slot its winner goes to
    play_ins = 0
    while (
        play_ins + 1 < len(shown)
        and shown[play_ins][0]["side"] == shown[play_ins + 1][0]["side"]
        and len(shown[play_ins][1]) < len(shown[play_ins + 1][1])
    ):
        play_ins += 1
    order = shown[play_ins:] + shown[:play_ins][::-1]

    last_grand_final = None
    for n, (column, ids, x) in enumerate(order):
        play_in = n >= len(shown) - play_ins
        cursor = top + HEADER_H
        first_y = None
        for i in ids:
            fed = [f for f in feeders.get(i, []) if f in result["sets"]]
            nxt = sets[i].get("nextWin")
            target = result["sets"].get(nxt["set"]) if play_in and nxt else None
            y = cursor
            if target:
                # Centered on the slot's row, the top or bottom half of the set
                y = max(cursor, target["y"] + ((nxt.get("slot") or 0) * 2 - 1) * SET_H / 4)
            elif fed:
                y = max(cursor, sum(result["sets"][f]["y"] for f in fed) / len(fed))
            elif column["side"] == "grand_final" and last_grand_final is not None:
                # The reset, level with the grand final
                y = max(cursor, last_grand_final)
            if column["side"] == "grand_final":
                last_grand_final = y
            if first_y is None:
                first_y = y
            result["sets"][i] = _Box(x, y, SET_W, SET_H)
            cursor = y + SET_H + ROW_GAP
            bottom = max(bottom, cursor)
        # Grand finals have their name just above them
        header_y = first_y - HEADER_H if column["side"] == "grand_final" else top
        result["headers"][column["key"]] = _Box(x, header_y, SET_W, HEADER_H - 12)

    # The 3rd place match under the last column
    for column in third:
        ids = [i for i in column["sets"] if _Shown(sets.get(i))]
        if not ids:
            continue
        y = bottom + ROW_GAP
        result["headers"][column["key"]] = _Box(last_x, y, SET_W, HEADER_H - 12)
        y += HEADER_H
        for i in ids:
            result["sets"][i] = _Box(last_x, y, SET_W, SET_H)
            y += SET_H + ROW_GAP
        bottom = y
    return bottom


def _PlacePool(bracket, result):
    """Round robin and swiss: a column per round, the standings after them."""
    sets = bracket.get("sets") or {}
    bottom = x = MARGIN
    for column in _Columns(bracket, "pool"):
        result["headers"][column["key"]] = _Box(x, MARGIN, SET_W, HEADER_H - 12)
        y = MARGIN + HEADER_H
        for i in column["sets"]:
            if i in sets:
                result["sets"][i] = _Box(x, y, SET_W, SET_H)
                y += SET_H + ROW_GAP
        result["byes"][column["key"]] = _Box(x, y, SET_W)
        bottom = max(bottom, y + 40)
        x += SET_W + COLUMN_GAP
    result["standings"] = _Box(x, MARGIN, STANDINGS_W)
    return bottom


def _Lines(bracket, areas, placed):
    """Each set's line to where its winner goes, in its part of the
    bracket, and arrows out of it for players going on to another phase:
    [{from, to (None for an arrow), points}]."""
    sets = bracket.get("sets") or {}
    lines = []
    for columns in areas:
        area = dict.fromkeys(i for c in columns for i in c["sets"])
        for i in area:
            set_, a = sets.get(i), placed.get(i)
            if not set_ or not a:
                continue
            start = [a["x"] + a["w"], a["y"] + a["h"] / 2]
            nxt = set_.get("nextWin")
            b = placed.get(nxt["set"]) if nxt and nxt["set"] in area else None
            if b:
                if b["x"] > a["x"]:
                    # To the middle of the set, so the two feeding it share one line in
                    end = [b["x"], b["y"] + b["h"] / 2]
                    mid = start[0] + (end[0] - start[0]) / 2
                    points = [start, [mid, start[1]], [mid, end[1]], end]
                    lines.append({"from": i, "to": nxt["set"], "points": points})
            elif (
                not nxt
                and (bracket.get("progressionsOut") or 0) > 0
                and set_.get("side") in ("winners", "losers")
            ):
                points = [start, [start[0] + 45, start[1]]]
                lines.append({"from": i, "to": None, "points": points, "arrow": True})
    return lines


def Place(bracket):
    """The bracket's placement: {sets, headers, byes: {key: {x, y, w(, h)}},
    standings ({x, y, w}, pools), lines, width, height}. None without one."""
    if not bracket or not bracket.get("sides"):
        return None
    result = {"sets": {}, "headers": {}, "byes": {}, "standings": None}
    sets = bracket.get("sets") or {}
    if bracket.get("type") in POOL_TYPES:
        bottom = _PlacePool(bracket, result)
        areas = []
    else:
        areas = Areas(bracket)
        bottom = _PlaceArea(areas[0], sets, MARGIN, result)
        if areas[1]:
            bottom = _PlaceArea(areas[1], sets, bottom + SECTION_GAP, result)
    boxes = list(result["sets"].values()) + list(result["headers"].values())
    result["lines"] = _Lines(bracket, areas, result["sets"])
    result["width"] = max([0] + [b["x"] + b["w"] for b in boxes]) + MARGIN
    result["height"] = max([bottom] + [b["y"] + b["h"] for b in boxes]) + MARGIN
    return result
