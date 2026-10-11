# What the bracket focus layouts (layout/bracket_focus) zoom to, as
# bracket.focus: sets picked in the bracket widget, rounds, a player's run,
# the set on a scoreboard, or a tour of every round. Driven from the bracket
# widget and the /bracket-focus web page.
#
# There's a focus per channel (bracket.focus.<channel>), so layouts in
# different OBS sources can show different things: each picks its channel
# with ?channel=<name>, "main" by default. A channel shows the phase
# selected in the bracket widget, or is pinned to one of its phases or to a
# start.gg phase group (BracketPhaseGroups).
from qtpy.QtCore import *
from qtpy.QtWidgets import QApplication

from .BracketModel import BRACKET_TYPES
from .BracketPhaseGroups import PhaseGroupBrackets
from .Helpers.BracketFocusHelper import *
from .SettingsManager import SettingsManager
from .StateManager import StateManager


class FocusChannelSignals(QObject):
    # What's in focus changed
    changed = Signal()


class FocusChannel(QObject):
    """One channel's focus: its request, the tour's step and timers."""

    # How often the set on the followed scoreboard is checked, in ms
    FOLLOW_INTERVAL = 1000

    def __init__(self, name, request=None, phase=PHASE_SELECTED, parent=None):
        super().__init__(parent)
        self.signals = FocusChannelSignals()
        self.name = name
        self.request = NormalizeRequest(request)
        self.phase = NormalizePhase(phase)
        self.step = 0
        self.focus = None

        self.tourTimer = QTimer(self)
        self.tourTimer.timeout.connect(self.NextTourStep)
        self.followTimer = QTimer(self)
        self.followTimer.setInterval(FocusChannel.FOLLOW_INTERVAL)
        self.followTimer.timeout.connect(self.Refresh)
        self._StartTimers()

    def Bracket(self):
        return StateManager.Get(PhaseSource(self.phase)["bracket"], {}) or {}

    def SetPhase(self, key):
        """Shows another phase: "" for the one selected in the bracket
        widget, local:<id> or group:<id>."""
        key = NormalizePhase(key)
        if key == self.phase:
            return
        self.phase = key
        # Sets, rounds and players picked are the old bracket's
        if self.request.get("mode") in (MODE_SETS, MODE_ROUNDS, MODE_PLAYER):
            self.request = {"mode": MODE_ALL}
        self.step = 0
        if BracketFocus.instance is not None:
            BracketFocus.instance.PhasesChanged()
        self._StartTimers()
        self.Refresh(force=True)

    # Changing the focus

    def Set(self, request):
        request = NormalizeRequest(request)
        if request.get("mode") != self.request.get("mode") or request.get("mode") != MODE_TOUR:
            self.step = 0
        self.request = request
        if BracketFocus.instance is not None:
            BracketFocus.instance.SaveChannels()
        self._StartTimers()
        self.Refresh()

    def ShowAll(self):
        self.Set({"mode": MODE_ALL})

    def FocusSets(self, ids, rounds=()):
        """Sets and whole rounds picked by hand."""
        ids, rounds = list(ids or []), list(rounds or [])
        if not ids and not rounds:
            self.ShowAll()
        else:
            mode = MODE_SETS if ids else MODE_ROUNDS
            self.Set({"mode": mode, "sets": ids, "rounds": rounds})

    def FocusRounds(self, keys):
        self.FocusSets([], keys)

    def FocusPlayer(self, player):
        self.Set({"mode": MODE_PLAYER, "player": player} if player else {"mode": MODE_ALL})

    def Follow(self, scoreboard=1):
        self.Set({"mode": MODE_FOLLOW, "scoreboard": scoreboard})

    def Tour(self, interval=None):
        self.Set(
            {
                "mode": MODE_TOUR,
                "interval": interval
                or self.request.get("interval")
                or SettingsManager.Get("bracket_focus_tour_interval", DEFAULT_INTERVAL),
            }
        )

    def Toggle(self, mode):
        """Follow or tour on, or back to the whole bracket when it's on."""
        if self.request.get("mode") == mode:
            self.ShowAll()
        elif mode == MODE_FOLLOW:
            self.Follow(self.request.get("scoreboard") or 1)
        elif mode == MODE_TOUR:
            self.Tour()

    def MoveRound(self, offset):
        """The next (or previous) round. In a tour, its next step."""
        if self.request.get("mode") == MODE_TOUR:
            self.NextTourStep(offset)
            self.tourTimer.start()
            return
        self.Set(NextRound(self.Bracket(), self.focus, offset))

    def NextTourStep(self, offset=1):
        self.step += offset
        self.Refresh()

    def _StartTimers(self):
        mode = self.request.get("mode")
        if mode == MODE_TOUR:
            self.tourTimer.setInterval(self.request.get("interval", DEFAULT_INTERVAL) * 1000)
            SettingsManager.Set("bracket_focus_tour_interval", self.request.get("interval"))
            self.tourTimer.start()
        else:
            self.tourTimer.stop()
        if mode == MODE_FOLLOW:
            self.followTimer.start()
        else:
            self.followTimer.stop()

    def Stop(self):
        self.tourTimer.stop()
        self.followTimer.stop()

    # Exporting

    def Refresh(self, force=False):
        """Works out the focus again (the bracket, the scoreboard or the
        tour's step changed) and sends it to the layouts if it changed."""
        bracket = self.Bracket()
        score = None
        if self.request.get("mode") == MODE_FOLLOW:
            score = StateManager.Get(f"score.{self.request.get('scoreboard', 1)}", {})
        focus = Resolve(bracket, self.request, score, self.step)
        if focus.get("mode") == MODE_TOUR:
            self.step = focus.get("step", 0)
        focus["phase"] = self.phase
        focus["source"] = PhaseSource(self.phase)
        if force or focus != self.focus:
            self.focus = focus
            StateManager.Set(f"bracket.focus.{self.name}", focus)
            self.signals.changed.emit()


class BracketFocusSignals(QObject):
    # A channel's focus changed (its name)
    changed = Signal(str)
    # Channels were added, removed or renamed, or another one was picked
    channelsChanged = Signal()
    # The phases channels can be pinned to changed
    phaseOptionsChanged = Signal()
    # Channels were pinned to other phases of the bracket widget
    localPhasesChanged = Signal()


class BracketFocus(QObject):
    """The focus channels, and the one the bracket widget acts on."""

    instance: "BracketFocus" = None

    def __init__(self):
        super().__init__()
        self.signals = BracketFocusSignals()
        self.channels: dict[str, FocusChannel] = {}
        # The bracket widget's phase on screen, and start.gg's phases
        self.viewPhaseId = None
        self.localPhases = []
        self.providerPhases = []
        # Names and bracket types of the phase groups channels are pinned to
        groupInfo = SettingsManager.Get("bracket_focus_groups", {})
        self.groupInfo = groupInfo if isinstance(groupInfo, dict) else {}
        self.groups = PhaseGroupBrackets(self)
        self.groups.signals.changed.connect(self.GroupChanged)

        saved = SettingsManager.Get("bracket_focus_channels", {})
        saved = saved if isinstance(saved, dict) else {}
        for name, request in saved.items():
            name = NormalizeChannelName(name)
            if name and name not in self.channels:
                phase = request.get("phase") if isinstance(request, dict) else None
                self._Add(name, request, phase)
        if MAIN_CHANNEL not in self.channels:
            self.channels = {MAIN_CHANNEL: self._Make(MAIN_CHANNEL), **self.channels}
        current = SettingsManager.Get("bracket_focus_current", MAIN_CHANNEL)
        self.current = current if current in self.channels else MAIN_CHANNEL
        self.KeepGroups()

    def _Make(self, name, request=None, phase=PHASE_SELECTED):
        channel = FocusChannel(name, request, phase, self)
        channel.signals.changed.connect(lambda: self.signals.changed.emit(channel.name))
        return channel

    def _Add(self, name, request=None, phase=PHASE_SELECTED):
        channel = self._Make(name, request, phase)
        self.channels[name] = channel
        return channel

    def SaveChannels(self):
        SettingsManager.Set(
            "bracket_focus_channels",
            {
                name: dict(c.request, phase=c.phase) if c.phase else c.request
                for name, c in self.channels.items()
            },
        )
        SettingsManager.Set("bracket_focus_current", self.current)

    # Channels

    def Channel(self, name=None):
        """A channel by name (the current one without a name), or None."""
        if name in (None, ""):
            return self.Current()
        return self.channels.get(NormalizeChannelName(name))

    def Current(self) -> FocusChannel:
        return self.channels.get(self.current) or self.channels[MAIN_CHANNEL]

    def SetCurrent(self, name):
        if name in self.channels and name != self.current:
            self.current = name
            self.SaveChannels()
            self.signals.channelsChanged.emit()

    def AddChannel(self, name):
        """Adds a channel, showing the whole bracket. Returns its name, or
        None if the name can't be used."""
        name = NormalizeChannelName(name)
        if not name or name in self.channels:
            return None
        self._Add(name).Refresh(force=True)
        self.current = name
        self.SaveChannels()
        self.signals.channelsChanged.emit()
        return name

    def RemoveChannel(self, name):
        if name == MAIN_CHANNEL or name not in self.channels:
            return False
        channel = self.channels.pop(name)
        channel.Stop()
        channel.deleteLater()
        StateManager.Unset(f"bracket.focus.{name}")
        if self.current == name:
            self.current = MAIN_CHANNEL
        self.PhasesChanged()
        self.signals.channelsChanged.emit()
        return True

    def RenameChannel(self, name, new):
        """Renames a channel, keeping its focus. The layouts showing it have
        to be changed to the new name."""
        new = NormalizeChannelName(new)
        if name == MAIN_CHANNEL or name not in self.channels or not new or new in self.channels:
            return None
        channel = self.channels.pop(name)
        StateManager.Unset(f"bracket.focus.{name}")
        channel.name = new
        # In the same place in the list
        self.channels[new] = channel
        if self.current == name:
            self.current = new
        channel.Refresh(force=True)
        self.SaveChannels()
        self.signals.channelsChanged.emit()
        return new

    def Refresh(self):
        for channel in list(self.channels.values()):
            channel.Refresh()

    # Phases

    def PhasesChanged(self):
        """A channel was pinned to another phase, or removed."""
        self.SaveChannels()
        self.KeepGroups()
        self.signals.localPhasesChanged.emit()

    def PinnedLocalPhases(self):
        return {
            id
            for c in self.channels.values()
            for kind, id in [ParsePhase(c.phase)]
            if kind == PHASE_LOCAL
        }

    def KeepGroups(self):
        """Loads the phase groups channels are pinned to, and drops the others."""
        pinned = {
            id
            for c in self.channels.values()
            for kind, id in [ParsePhase(c.phase)]
            if kind == PHASE_GROUP
        }
        for id in pinned:
            info = self.ProviderGroup(id)
            if info is not None:
                self.groupInfo[id] = info
        self.groupInfo = {id: info for id, info in self.groupInfo.items() if id in pinned}
        SettingsManager.Set("bracket_focus_groups", self.groupInfo)
        self.groups.Keep({id: self.groupInfo.get(id, {}) for id in pinned})

    def GroupChanged(self, id):
        for channel in list(self.channels.values()):
            if ParsePhase(channel.phase) == (PHASE_GROUP, id):
                channel.Refresh()

    def ProviderGroup(self, id):
        """A start.gg phase group's names and bracket type, or None."""
        for phase in self.providerPhases:
            groups = phase.get("groups") or []
            for group in groups:
                if str(group.get("id")) == str(id):
                    return {
                        "phase": phase.get("name") or "",
                        "group": group.get("name") or "" if len(groups) > 1 else "",
                        "bracketType": group.get("bracketType"),
                    }
        return None

    def SetProviderPhases(self, phases):
        """start.gg's phases and their groups, from the bracket widget."""
        self.providerPhases = list(phases or [])
        self.KeepGroups()
        self.groups.LoadMissing()
        self.signals.phaseOptionsChanged.emit()

    def SetViewPhase(self, id):
        """The bracket widget's phase on screen, and its phases changed."""
        phases = [
            {"id": p.get("id"), "name": p.get("name")}
            for p in StateManager.Get("bracket.phases", []) or []
        ]
        if id != self.viewPhaseId or phases != self.localPhases:
            self.viewPhaseId = id
            self.localPhases = phases
            self.signals.phaseOptionsChanged.emit()

    def ShowsView(self, channel=None):
        """Whether the channel shows the bracket on screen in the widget,
        so its sets can be picked there."""
        channel = channel or self.Current()
        return channel.phase in (PHASE_SELECTED, f"{PHASE_LOCAL}:{self.viewPhaseId}")

    def PhaseOptions(self):
        """What channels can be pinned to: [{value, label, section}], the
        section being "selected", "local" or "group"."""
        options = [
            {
                "value": PHASE_SELECTED,
                "label": QApplication.translate("app", "Selected phase"),
                "section": "selected",
            }
        ]
        for p in self.localPhases:
            options.append(
                {
                    "value": f"{PHASE_LOCAL}:{p['id']}",
                    "label": p.get("name") or "",
                    "section": "local",
                }
            )
        seen = set()
        for phase in self.providerPhases:
            groups = phase.get("groups") or []
            for group in groups:
                if group.get("bracketType") not in BRACKET_TYPES or group.get("id") is None:
                    continue
                id = str(group.get("id"))
                seen.add(id)
                name = phase.get("name") or ""
                if len(groups) > 1:
                    name = f"{name} - {group.get('name') or ''}"
                options.append({"value": f"{PHASE_GROUP}:{id}", "label": name, "section": "group"})
        # Pinned before, while start.gg's phases aren't loaded
        for id, info in self.groupInfo.items():
            if id not in seen:
                name = " - ".join(n for n in (info.get("phase"), info.get("group")) if n)
                options.append(
                    {"value": f"{PHASE_GROUP}:{id}", "label": name or id, "section": "group"}
                )
        return options

    def PhaseLabel(self, key):
        return next((o["label"] for o in self.PhaseOptions() if o["value"] == key), key)

    # The web page

    def State(self, name=None):
        """What's in focus on a channel and what can be picked."""
        channel = self.Channel(name) or self.Current()
        bracket = channel.Bracket()
        sets = bracket.get("sets") or {}
        players = {}
        for s in sets.values():
            for p in s.get("players") or []:
                if (p or {}).get("id") and p.get("name"):
                    players[p["id"]] = {"id": p["id"], "name": p["name"], "seed": p.get("seed")}
        return {
            "channel": channel.name,
            "channels": list(self.channels.keys()),
            "phase": channel.phase,
            "phases": self.PhaseOptions(),
            "focus": channel.focus or Resolve(bracket, channel.request),
            "name": bracket.get("name", ""),
            "rounds": [
                {
                    "key": c.get("key"),
                    "name": c.get("name"),
                    "sets": [
                        {
                            "id": id,
                            "identifier": sets[id].get("identifier"),
                            "players": [(p or {}).get("name") or "" for p in sets[id]["players"]],
                            "completed": sets[id].get("completed"),
                        }
                        for id in c.get("sets") or []
                        if id in sets
                    ],
                }
                for c in Columns(bracket)
            ],
            "players": sorted(players.values(), key=lambda p: (p.get("seed") or 9999, p["name"])),
        }
