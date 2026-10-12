# How long the event's sets take, and when the sets of a stream queue should
# start from that.
#
# The sets come from a provider's GetSetDurations: {startedAt, completedAt,
# totalGames, dq}.
#
# Nothing in here depends on Qt, so it can be tested on its own.
import time
from statistics import median

# Sets shorter or longer than this are left out of the durations: a set
# reported long after it was played, or one started by mistake
MIN_SET_SECS = 60
MAX_SET_SECS = 3 * 60 * 60
# Durations of sets of the same length (best of 3, best of 5...) are only
# used once there are this many
MIN_SAMPLES = 3


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
    `sets` have startedAt/completedAt/totalGames/dq (GetSetDurations)."""
    result = {None: []}
    for s in sets or []:
        if not s or s.get("dq"):
            continue
        seconds = SetDuration(s.get("startedAt"), s.get("completedAt"))
        if seconds is None:
            continue
        result[None].append(seconds)
        bestOf = s.get("totalGames")
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
