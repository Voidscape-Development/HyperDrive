# The bracket channels. Each channel shows a phase of the bracket widget's
# pool (a phase built there or a start.gg phase group loaded into it), with
# its own "only show the top N" and its own focus: what the bracket focus
# layouts (layout/bracket_focus) zoom to, as bracket.focus.<channel>: sets
# picked in the bracket widget, rounds, a player's run, the set on a
# scoreboard, or a tour of every round. Channels showing the same phase
# share its data. The bracket widget has a tab per channel; the
# /bracket-focus web page and the Stream Deck drive them too.
#
# Layouts pick their channel with ?channel=<name>, "main" by default. The
# bracket widget sends each channel's bracket as bracket.channels.<channel>.
from qtpy.QtCore import *

from .Helpers.BracketFocusHelper import *
from .SettingsManager import SettingsManager
from .StateManager import StateManager


class FocusChannelSignals(QObject):
    # What's in focus changed
    changed = Signal()


class FocusChannel(QObject):
    """One channel: its phase, its top N, its focus request, the tour's
    step and timers, and how the bracket widget's view was left on it."""

    # How often the set on the followed scoreboard is checked, in ms
    FOLLOW_INTERVAL = 1000

    def __init__(self, name, request=None, phase=None, limit=None, parent=None):
        super().__init__(parent)
        self.signals = FocusChannelSignals()
        self.name = name
        self.request = NormalizeRequest(request)
        # Id of the phase shown (None: none yet)
        self.phase = str(phase) if phase not in (None, "") else None
        self.limit = NormalizeLimit(limit)
        # The bracket widget's view of it: zoom, scroll and selection.
        # Not saved.
        self.viewState = None
        self.step = 0
        self.focus = None

        self.tourTimer = QTimer(self)
        self.tourTimer.timeout.connect(self.NextTourStep)
        self.followTimer = QTimer(self)
        self.followTimer.setInterval(FocusChannel.FOLLOW_INTERVAL)
        self.followTimer.timeout.connect(self.Refresh)
        self._StartTimers()

    # =====================================================
    # PHASE AND SETTINGS
    # =====================================================
    def Bracket(self):
        return StateManager.Get(f"bracket.channels.{self.name}.bracket", {}) or {}

    def SetPhase(self, phase):
        """Shows another phase of the pool, by id."""
        phase = str(phase) if phase not in (None, "") else None
        if phase == self.phase:
            return
        self.phase = phase
        # Sets, rounds and players picked are the old bracket's
        if self.request.get("mode") in (MODE_SETS, MODE_ROUNDS, MODE_PLAYER):
            self.request = {"mode": MODE_ALL}
        self.step = 0
        self.viewState = None
        self._StartTimers()
        self._SettingsChanged()

    def SetLimit(self, limit):
        limit = NormalizeLimit(limit)
        if limit != self.limit:
            self.limit = limit
            self._SettingsChanged()

    def _SettingsChanged(self):
        if BracketFocus.instance is not None:
            BracketFocus.instance.SaveChannels()
            BracketFocus.instance.signals.settingsChanged.emit(self.name)
        self.Refresh(force=True)

    # =====================================================
    # FOCUS MODES
    # =====================================================
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

    # =====================================================
    # ROUNDS AND TOUR STEPS
    # =====================================================
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

    # =====================================================
    # REFRESHING
    # =====================================================
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
        if force or focus != self.focus:
            self.focus = focus
            StateManager.Set(f"bracket.focus.{self.name}", focus)
            self.signals.changed.emit()


class BracketFocusSignals(QObject):
    # A channel's focus changed (its name)
    changed = Signal(str)
    # Channels were added, removed or renamed, or another one was picked
    channelsChanged = Signal()
    # A channel's phase or top N changed (its name): its bracket is sent again
    settingsChanged = Signal(str)


class BracketFocus(QObject):
    """The channels, and the one the bracket widget shows."""

    instance: "BracketFocus" = None

    def __init__(self):
        super().__init__()
        self.signals = BracketFocusSignals()
        self.channels: dict[str, FocusChannel] = {}

        saved = SettingsManager.Get("bracket_focus_channels", {})
        saved = saved if isinstance(saved, dict) else {}
        for name, data in saved.items():
            name = NormalizeChannelName(name)
            data = data if isinstance(data, dict) else {}
            if name and name not in self.channels:
                self._Add(name, data, data.get("phase"), data.get("limit"))
        if MAIN_CHANNEL not in self.channels:
            self.channels = {MAIN_CHANNEL: self._Make(MAIN_CHANNEL), **self.channels}
        current = SettingsManager.Get("bracket_focus_current", MAIN_CHANNEL)
        self.current = current if current in self.channels else MAIN_CHANNEL

    # =====================================================
    # CHANNELS
    # =====================================================
    def _Make(self, name, request=None, phase=None, limit=None):
        channel = FocusChannel(name, request, phase, limit, self)
        channel.signals.changed.connect(lambda: self.signals.changed.emit(channel.name))
        return channel

    def _Add(self, name, request=None, phase=None, limit=None):
        channel = self._Make(name, request, phase, limit)
        self.channels[name] = channel
        return channel

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

    def AddChannel(self, name, phase=None):
        """Adds a channel showing the phase (the current channel's by
        default) and picks it. Returns its name, or None if the name can't
        be used."""
        name = NormalizeChannelName(name)
        if not name or name in self.channels:
            return None
        self._Add(name, phase=phase if phase is not None else self.Current().phase)
        self.current = name
        self.SaveChannels()
        self.signals.channelsChanged.emit()
        self.signals.settingsChanged.emit(name)
        return name

    def RemoveChannel(self, name):
        if name == MAIN_CHANNEL or name not in self.channels:
            return False
        channel = self.channels.pop(name)
        channel.Stop()
        channel.deleteLater()
        StateManager.Unset(f"bracket.focus.{name}")
        StateManager.Unset(f"bracket.channels.{name}")
        if self.current == name:
            self.current = MAIN_CHANNEL
        self.SaveChannels()
        self.signals.channelsChanged.emit()
        return True

    def RenameChannel(self, name, new):
        """Renames a channel, keeping its phase and focus. The layouts
        showing it have to be changed to the new name."""
        new = NormalizeChannelName(new)
        if name == MAIN_CHANNEL or name not in self.channels or not new or new in self.channels:
            return None
        StateManager.Unset(f"bracket.focus.{name}")
        StateManager.Unset(f"bracket.channels.{name}")
        # In the same place in the list
        self.channels = {(new if n == name else n): c for n, c in self.channels.items()}
        channel = self.channels[new]
        channel.name = new
        if self.current == name:
            self.current = new
        self.SaveChannels()
        self.signals.channelsChanged.emit()
        self.signals.settingsChanged.emit(new)
        return new

    def ChannelsOn(self, phase):
        """Names of the channels showing a phase."""
        return [n for n, c in self.channels.items() if c.phase == str(phase)]

    def HasPhase(self, phase):
        return any(
            str(p.get("id")) == str(phase) for p in StateManager.Get("bracket.phases", []) or []
        )

    def SaveChannels(self):
        SettingsManager.Set(
            "bracket_focus_channels",
            {
                name: dict(c.request, phase=c.phase, limit=c.limit)
                for name, c in self.channels.items()
            },
        )
        SettingsManager.Set("bracket_focus_current", self.current)

    # =====================================================
    # FOCUS STATE
    # =====================================================
    def Refresh(self):
        for channel in list(self.channels.values()):
            channel.Refresh()

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
            # The pool: [{value, label, section}], section "local" or "startgg"
            "phases": [
                {
                    "value": p.get("id"),
                    "label": p.get("name") or "",
                    "section": p.get("source") or "local",
                }
                for p in StateManager.Get("bracket.phases", []) or []
            ],
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
