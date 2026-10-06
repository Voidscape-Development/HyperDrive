# The stream queue: the sets each stream will show next. start.gg's stream
# queue is the base, and every stream's queue can be edited here on top of
# it: sets moved, hidden, or added (any start.gg set, or a set typed in by
# hand). Streams can also be added by hand, e.g. for a stream start.gg
# doesn't know about.
#
# Nothing in here depends on Qt, so it can be tested on its own.
import time
import uuid

# What to do when the set on a stream's scoreboard is over
AFTER_SET_NOTHING = "nothing"
AFTER_SET_LOAD_NEXT = "load_next"
AFTER_SET_ASK = "ask"

SOURCE_STARTGG = "startgg"
# A start.gg set added by hand
SOURCE_ADDED = "added"
# A set typed in by hand
SOURCE_CUSTOM = "custom"

# start.gg set states
STATE_COMPLETED = 3


def SetKey(setId):
    return f"set:{setId}"


class StreamConfig:
    def __init__(self, name, manual=False):
        self.name = name
        # Added by hand rather than coming from start.gg
        self.manual = manual
        # Keys in the order they were put in by hand. Empty: start.gg's order.
        self.order = []
        # start.gg sets taken out of this queue
        self.hidden = []
        # Sets added by hand: {"key", "source", "setId", "set"}
        self.added = []
        # Scoreboard showing this stream's sets
        self.scoreboard = None

    def ToDict(self):
        return {
            "name": self.name,
            "manual": self.manual,
            "order": self.order,
            "hidden": self.hidden,
            "added": self.added,
            "scoreboard": self.scoreboard,
        }

    @classmethod
    def FromDict(cls, data):
        config = cls(data.get("name") or "", bool(data.get("manual")))
        config.order = list(data.get("order") or [])
        config.hidden = list(data.get("hidden") or [])
        config.added = [a for a in data.get("added") or [] if a.get("key")]
        config.scoreboard = data.get("scoreboard")
        return config


class StreamQueueModel:
    def __init__(self):
        self.streams: list[StreamConfig] = []
        # start.gg's queue for each stream: name -> [set data]
        self.providerQueues = {}
        # start.gg streams removed by hand, so they don't come back
        self.removedStreams = []
        # Streams start.gg has get a tab on their own
        self.autoAddStreams = True
        self.afterSet = AFTER_SET_ASK
        self.lastUpdated = None

    # Streams

    def GetStream(self, name) -> StreamConfig:
        lname = str(name or "").lower()
        return next((s for s in self.streams if s.name.lower() == lname), None)

    def AddStream(self, name, manual=True):
        name = str(name or "").strip()
        if not name:
            return None
        existing = self.GetStream(name)
        if existing is not None:
            return existing
        self.removedStreams = [s for s in self.removedStreams if s.lower() != name.lower()]
        config = StreamConfig(name, manual)
        self.streams.append(config)
        return config

    def RemoveStream(self, name):
        config = self.GetStream(name)
        if config is None:
            return
        self.streams.remove(config)
        if self._ProviderStreamName(name) is not None:
            self.removedStreams.append(config.name)

    def MoveStream(self, name, offset):
        config = self.GetStream(name)
        if config is None:
            return
        i = self.streams.index(config)
        j = max(0, min(len(self.streams) - 1, i + offset))
        self.streams.insert(j, self.streams.pop(i))

    def _ProviderStreamName(self, name):
        lname = str(name or "").lower()
        return next((n for n in self.providerQueues if n.lower() == lname), None)

    # start.gg data

    def SetProviderQueues(self, queues):
        """start.gg's stream queue: {stream name: [set data] or {"1": set}}."""
        result = {}
        for name, sets in (queues or {}).items():
            if not name:
                continue
            if isinstance(sets, dict):
                sets = [
                    sets[k] for k in sorted(sets, key=lambda k: int(k) if str(k).isdigit() else 0)
                ]
            result[name] = [s for s in sets or [] if s]
        self.providerQueues = result
        self.lastUpdated = time.time()

        if self.autoAddStreams:
            removed = {s.lower() for s in self.removedStreams}
            for name in result:
                if name.lower() not in removed and self.GetStream(name) is None:
                    self.AddStream(name, manual=False)

    def AddedSetIds(self):
        """start.gg sets added by hand, whose data has to be fetched."""
        ids = []
        for config in self.streams:
            for entry in config.added:
                if entry.get("source") == SOURCE_ADDED and entry.get("setId") is not None:
                    ids.append(str(entry["setId"]))
        return list(dict.fromkeys(ids))

    def SetAddedSetData(self, data):
        """Fresh data of the start.gg sets added by hand: {set id: set
        data}. Finished sets leave the queues."""
        for config in self.streams:
            for entry in list(config.added):
                setId = entry.get("setId")
                if entry.get("source") != SOURCE_ADDED or setId is None:
                    continue
                fresh = (data or {}).get(str(setId))
                if not fresh:
                    continue
                if fresh.get("state") == STATE_COMPLETED:
                    self._Drop(config, entry["key"])
                else:
                    entry["set"] = fresh

    # Queues

    def Queue(self, name):
        """The stream's queue: [{"key", "source", "set"}], next set first."""
        config = self.GetStream(name)
        if config is None:
            return []

        entries = {}
        providerOrder = []
        providerName = self._ProviderStreamName(name)
        for s in self.providerQueues.get(providerName, []) if providerName else []:
            key = SetKey(s.get("id"))
            if key in config.hidden or key in entries:
                continue
            entries[key] = {"key": key, "source": SOURCE_STARTGG, "set": s}
            providerOrder.append(key)

        addedOrder = []
        for entry in config.added:
            if entry["key"] in entries:
                # Also in start.gg's queue now
                continue
            entries[entry["key"]] = {
                "key": entry["key"],
                "source": entry.get("source"),
                "set": entry.get("set") or {},
            }
            addedOrder.append(entry["key"])

        order = [k for k in config.order if k in entries]
        placed = set(order)
        order += [k for k in providerOrder + addedOrder if k not in placed]
        return [entries[k] for k in order]

    def Move(self, name, key, offset):
        config = self.GetStream(name)
        if config is None:
            return
        keys = [e["key"] for e in self.Queue(name)]
        if key not in keys:
            return
        i = keys.index(key)
        j = max(0, min(len(keys) - 1, i + offset))
        keys.insert(j, keys.pop(i))
        config.order = keys

    def MoveTo(self, name, key, index):
        config = self.GetStream(name)
        if config is None:
            return
        keys = [e["key"] for e in self.Queue(name)]
        if key not in keys:
            return
        keys.remove(key)
        keys.insert(max(0, min(len(keys), index)), key)
        config.order = keys

    def Remove(self, name, key):
        """Takes a set out of the stream's queue: start.gg's are hidden,
        added ones are removed."""
        config = self.GetStream(name)
        if config is None:
            return
        if any(e["key"] == key for e in config.added):
            config.added = [e for e in config.added if e["key"] != key]
        else:
            if key not in config.hidden:
                config.hidden.append(key)
        config.order = [k for k in config.order if k != key]

    def _Drop(self, config, key):
        config.added = [e for e in config.added if e["key"] != key]
        config.order = [k for k in config.order if k != key]

    def AddStartggSet(self, name, setId, data=None, index=None):
        config = self.GetStream(name)
        if config is None or setId is None:
            return None
        key = SetKey(setId)
        # Shown again if it was hidden
        config.hidden = [k for k in config.hidden if k != key]
        if not any(e["key"] == key for e in config.added) and not any(
            e["key"] == key for e in self.Queue(name)
        ):
            config.added.append(
                {
                    "key": key,
                    "source": SOURCE_ADDED,
                    "setId": str(setId),
                    "set": data or {"id": setId},
                }
            )
            self._KeepPlace(config, key)
        if index is not None:
            self.MoveTo(name, key, index)
        return key

    def AddCustomSet(self, name, team1, team2, match="", phase=""):
        config = self.GetStream(name)
        if config is None:
            return None
        key = f"custom:{uuid.uuid4().hex[:12]}"

        def Team(teamName):
            return {
                "teamName": teamName,
                "losers": False,
                "player": {"1": {"name": teamName, "team": "", "mergedName": teamName}},
            }

        config.added.append(
            {
                "key": key,
                "source": SOURCE_CUSTOM,
                "setId": None,
                "set": {
                    "id": None,
                    "match": match,
                    "phase": phase,
                    "state": 1,
                    "team": {"1": Team(team1), "2": Team(team2)},
                },
            }
        )
        self._KeepPlace(config, key)
        return key

    def _KeepPlace(self, config, key):
        # Once the queue was reordered by hand, sets added to it stay where
        # they were put, ahead of sets start.gg adds later
        if config.order and key not in config.order:
            config.order = [e["key"] for e in self.Queue(config.name) if e["key"] != key] + [key]

    def ResetOrder(self, name):
        """Back to start.gg's queue: order, hidden sets and added sets."""
        config = self.GetStream(name)
        if config is None:
            return
        config.order = []
        config.hidden = []
        config.added = []

    def SetFinished(self, setId):
        """A set is over: it leaves every queue it was added to by hand."""
        key = SetKey(setId)
        for config in self.streams:
            self._Drop(config, key)

    def NextEntry(self, name, currentSetId=None):
        """The set to show after `currentSetId` on this stream."""
        currentKey = SetKey(currentSetId) if currentSetId is not None else None
        for entry in self.Queue(name):
            if entry["key"] == currentKey:
                continue
            if (entry.get("set") or {}).get("state") == STATE_COMPLETED:
                continue
            return entry
        return None

    def StreamOfScoreboard(self, scoreboard):
        return next(
            (
                s
                for s in self.streams
                if s.scoreboard is not None and str(s.scoreboard) == str(scoreboard)
            ),
            None,
        )

    # Saving and exporting

    def ToDict(self):
        return {
            "streams": [s.ToDict() for s in self.streams],
            "removedStreams": self.removedStreams,
            "autoAddStreams": self.autoAddStreams,
            "afterSet": self.afterSet,
        }

    @classmethod
    def FromDict(cls, data):
        model = cls()
        data = data or {}
        model.streams = [
            StreamConfig.FromDict(s) for s in data.get("streams") or [] if s.get("name")
        ]
        model.removedStreams = list(data.get("removedStreams") or [])
        model.autoAddStreams = bool(data.get("autoAddStreams", True))
        if data.get("afterSet") in (AFTER_SET_NOTHING, AFTER_SET_LOAD_NEXT, AFTER_SET_ASK):
            model.afterSet = data["afterSet"]
        return model

    def Export(self, onStream=None):
        """For the layouts. onStream: {stream name: set id on its
        scoreboard}."""
        streams = []
        for config in self.streams:
            current = (onStream or {}).get(config.name)
            sets = []
            for i, entry in enumerate(self.Queue(config.name)):
                data = dict(entry.get("set") or {})
                data["queueKey"] = entry["key"]
                data["source"] = entry["source"]
                data["position"] = i + 1
                data["onStream"] = current is not None and entry["key"] == SetKey(current)
                sets.append(data)
            streams.append(
                {
                    "name": config.name,
                    "manual": config.manual,
                    "scoreboard": config.scoreboard,
                    "sets": sets,
                }
            )
        return {
            "streams": streams,
            "byName": {s["name"]: s["sets"] for s in streams},
            "lastUpdated": self.lastUpdated,
        }
