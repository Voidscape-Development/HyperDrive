# The Event Stats widget: pulls what the event's completed sets add up to
# (characters, stages, upsets, over- and underperformers), the event's
# schedule and the standings of its league, for the event_stats, schedule
# and league_standings layouts. The completed sets are kept between pulls,
# so only the first pull of an event fetches them all.
import time
import traceback

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .EventStats import BuildEventStats, BuildSchedule, Numbered
from .GameAssetManager import GameAssetManager
from .Helpers import CompletedSetsHelper
from .Scheduler import Scheduler
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .Theme import ThemedIcon
from .TournamentDataManager import TournamentDataManager
from .Workers import Worker

JOB_NAME = "event_stats"
DEFAULT_INTERVAL_SECS = 120
MIN_INTERVAL_SECS = 60
LEAGUE_PLAYERS = 32
STANDINGS_PLAYERS = 64


def CharacterLookup():
    """start.gg character id -> the character's data for layouts, with its
    key, cached as building assets for each game would be slow. Characters
    the game's assets don't have keep start.gg's name, without assets."""
    cache = {}

    def Lookup(startggId):
        if startggId not in cache:
            data = None
            found = GameAssetManager.instance.GetCharacterFromStartGGId(startggId)
            if found:
                data = CompletedSetsHelper.Character(found[0])
                if data:
                    data["key"] = found[0]
            if data is None:
                startgg = GameAssetManager.instance.startgg_id_to_character.get(str(startggId))
                if startgg and startgg.get("name"):
                    data = {
                        "key": f"startgg:{startggId}",
                        "name": startgg["name"],
                        "en_name": startgg["name"],
                        "codename": "",
                        "assets": {},
                    }
            cache[startggId] = data
        return cache[startggId]

    return Lookup


def StageLookup(startggId, name):
    found = GameAssetManager.instance.GetStageFromStartGGId(startggId) if startggId else None
    if not found:
        return None
    stage = found[1] or {}
    codename = stage.get("codename") or found[0]
    return {
        "key": codename,
        "name": stage.get("display_name") or stage.get("name") or name or codename,
        "codename": codename,
        "path": stage.get("path"),
    }


class EventStatsWidget(QDockWidget):
    def __init__(self, *args):
        super().__init__(*args)
        self.setWindowTitle(QApplication.translate("app", "Event Stats"))
        self.setFloating(True)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)

        self.threadPool = QThreadPool()
        # The event's completed sets pulled so far: {set id: set}
        self.sets = {}
        self.provider = None
        self.lastUpdated = None
        self.progress = None
        self.message = ""

        contents = QWidget()
        contents.setLayout(QVBoxLayout())
        self.setWidget(contents)

        top = QHBoxLayout()
        contents.layout().addLayout(top)
        self.btUpdate = QPushButton(QApplication.translate("app", "Update now"))
        self.btUpdate.setIcon(ThemedIcon("./assets/icons/undo.svg"))
        self.btUpdate.clicked.connect(self.UpdateNow)
        top.addWidget(self.btUpdate)
        self.autoUpdate = QCheckBox(QApplication.translate("app", "Update every"))
        self.autoUpdate.setToolTip(
            QApplication.translate(
                "app",
                "The first update of an event pulls all of its completed sets, which takes a while for a big event. Later ones only pull the new sets.",
            )
        )
        self.autoUpdate.setChecked(SettingsManager.Get("event_stats.auto_update", False))
        self.autoUpdate.toggled.connect(self.AutoUpdateChanged)
        top.addWidget(self.autoUpdate)
        self.interval = QSpinBox()
        self.interval.setRange(MIN_INTERVAL_SECS, 3600)
        self.interval.setSuffix(QApplication.translate("app", " s"))
        self.interval.setValue(SettingsManager.Get("event_stats.interval", DEFAULT_INTERVAL_SECS))
        self.interval.valueChanged.connect(self.IntervalChanged)
        top.addWidget(self.interval)
        top.addStretch()
        btReload = QPushButton(QApplication.translate("app", "Pull all sets again"))
        btReload.setToolTip(
            QApplication.translate(
                "app", "Forgets the sets already pulled, e.g. after sets were reset on start.gg"
            )
        )
        btReload.clicked.connect(self.ReloadAll)
        top.addWidget(btReload)

        league = QHBoxLayout()
        contents.layout().addLayout(league)
        league.addWidget(QLabel(QApplication.translate("app", "League")))
        self.leagueSlug = QLineEdit()
        self.leagueSlug.setPlaceholderText(
            QApplication.translate(
                "app", "Paste the start.gg link of the league (circuit) to show its standings"
            )
        )
        self.leagueSlug.setText(SettingsManager.Get("event_stats.league", ""))
        self.leagueSlug.editingFinished.connect(self.LeagueChanged)
        league.addWidget(self.leagueSlug)

        self.statusLabel = QLabel()
        self.statusLabel.setWordWrap(True)
        contents.layout().addWidget(self.statusLabel)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        contents.layout().addWidget(self.summary)
        contents.layout().addStretch()

        Scheduler.instance.Register(
            JOB_NAME, self.Run, self.interval.value() * 1000, MIN_INTERVAL_SECS * 1000
        )
        Scheduler.instance.signals.tick.connect(self.UpdateStatus)
        Scheduler.instance.signals.job_state_changed.connect(
            lambda name: self.UpdateStatus() if name == JOB_NAME else None
        )
        TournamentDataManager.instance.signals.tournament_changed.connect(self.TournamentChanged)
        self.UpdateStatus()

    # Settings

    def AutoUpdateChanged(self, checked):
        SettingsManager.Set("event_stats.auto_update", checked)
        if checked and TournamentDataManager.instance.provider is not None:
            Scheduler.instance.Start(JOB_NAME, run_now=True)
        else:
            Scheduler.instance.Stop(JOB_NAME)

    def IntervalChanged(self, value):
        SettingsManager.Set("event_stats.interval", value)
        Scheduler.instance.SetInterval(JOB_NAME, value * 1000)

    def LeagueChanged(self):
        slug = self.leagueSlug.text().strip()
        if slug == SettingsManager.Get("event_stats.league", ""):
            return
        SettingsManager.Set("event_stats.league", slug)
        self.RunLight()

    # Pulling

    def TournamentChanged(self):
        self.sets = {}
        self.lastUpdated = None
        self.message = ""
        self.provider = TournamentDataManager.instance.provider
        with StateManager.SaveBlock():
            StateManager.Set("event_stats", {})
            StateManager.Set("schedule", {})
            StateManager.Set("league", {})
        if self.provider is not None and self.autoUpdate.isChecked():
            Scheduler.instance.Start(JOB_NAME, run_now=True)
        else:
            Scheduler.instance.Stop(JOB_NAME)
            # The schedule and the league are one request each
            self.RunLight()
        self.UpdateStatus()

    def UpdateNow(self):
        if TournamentDataManager.instance.provider is None:
            return
        Scheduler.instance.TriggerNow(JOB_NAME)

    def ReloadAll(self):
        self.sets = {}
        self.UpdateNow()

    def RunLight(self):
        """Just the schedule and the league."""
        provider = TournamentDataManager.instance.provider
        if provider is None:
            return
        slug = self.leagueSlug.text().strip() or None

        def Fetch(progress_callback=None, cancel_event=None):
            return {
                "schedule": self._Try(provider.GetSchedule),
                "league": self._Try(lambda: provider.GetLeague(slug, LEAGUE_PLAYERS)),
            }

        worker = Worker(Fetch)
        worker.signals.result.connect(
            lambda result, provider=provider: self.Fetched(result, provider)
        )
        self.threadPool.start(worker)

    def Run(self, done):
        provider = TournamentDataManager.instance.provider
        if provider is None:
            done()
            return
        knownIds = list(self.sets)
        slug = self.leagueSlug.text().strip() or None

        def Fetch(progress_callback=None, cancel_event=None):
            return {
                "sets": self._Try(
                    lambda: provider.GetEventStatsSets(
                        knownIds, progress_callback=progress_callback, cancel_event=cancel_event
                    )
                ),
                "standings": self._Try(lambda: provider.GetEventStandings(STANDINGS_PLAYERS)),
                "schedule": self._Try(provider.GetSchedule),
                "league": self._Try(lambda: provider.GetLeague(slug, LEAGUE_PLAYERS)),
                "full": True,
            }

        worker = Worker(Fetch)
        worker.signals.progress.connect(self.Progress)
        worker.signals.result.connect(
            lambda result, provider=provider: self.Fetched(result, provider)
        )
        worker.signals.finished.connect(lambda: [setattr(self, "progress", None), done()])
        self.threadPool.start(worker)

    @staticmethod
    def _Try(fn):
        try:
            return fn()
        except Exception:
            logger.error(traceback.format_exc())
            return None

    def Progress(self, page, pages):
        self.progress = (page, pages)
        self.UpdateStatus()

    def Fetched(self, result, provider):
        # Another tournament was loaded meanwhile
        if provider is not TournamentDataManager.instance.provider:
            return
        result = result or {}
        try:
            with StateManager.SaveBlock():
                if result.get("schedule") is not None:
                    StateManager.Set("schedule", BuildSchedule(result["schedule"]))
                league = result.get("league")
                if league is not None:
                    StateManager.Set(
                        "league", dict(league, standings=Numbered(league.get("standings")))
                    )
                elif self.leagueSlug.text().strip() or result.get("full"):
                    StateManager.Set("league", {})

                if result.get("full"):
                    if result.get("sets") is None:
                        if provider.name != "StartGG":
                            self.message = QApplication.translate(
                                "app", "Event stats are only available for start.gg events"
                            )
                        else:
                            self.message = QApplication.translate(
                                "app", "The sets couldn't be pulled, trying again next update"
                            )
                    else:
                        self.message = ""
                        for s in result["sets"]:
                            self.sets[str(s.get("id"))] = s
                        self.lastUpdated = time.time()
                        StateManager.Set(
                            "event_stats",
                            BuildEventStats(
                                list(self.sets.values()),
                                result.get("standings"),
                                CharacterLookup(),
                                StageLookup,
                            ),
                        )
        except Exception:
            logger.error(traceback.format_exc())
        self.UpdateSummary()
        self.UpdateStatus()

    # Showing it

    def UpdateStatus(self):
        parts = []
        if self.progress:
            page, pages = self.progress
            parts.append(
                QApplication.translate("app", "Pulling completed sets... {0}/{1}").format(
                    page, pages
                )
            )
        elif JOB_NAME in Scheduler.instance.jobs and Scheduler.instance.IsRunning(JOB_NAME):
            parts.append(QApplication.translate("app", "Updating..."))
        elif self.lastUpdated:
            ago = int(time.time() - self.lastUpdated)
            parts.append(QApplication.translate("app", "Updated {0}s ago").format(ago))
        if self.message:
            parts.append(self.message)
        self.statusLabel.setText(" · ".join(parts))

    def UpdateSummary(self):
        stats = StateManager.Get("event_stats", {}) or {}
        schedule = StateManager.Get("schedule", {}) or {}
        league = StateManager.Get("league", {}) or {}
        lines = []
        if stats:
            line = QApplication.translate("app", "{0} sets, {1} games, {2} DQs").format(
                stats.get("sets", 0), stats.get("games", 0), stats.get("dqs", 0)
            )
            if stats.get("average_set_minutes"):
                line += " · " + QApplication.translate("app", "a set takes ~{0} min").format(
                    stats["average_set_minutes"]
                )
            lines.append(line)
            top = list((stats.get("characters") or {}).values())[:3]
            if top:
                lines.append(
                    QApplication.translate("app", "Most played: {0}").format(
                        ", ".join(f"{c.get('name')} ({c.get('games')})" for c in top)
                    )
                )
            upset = (stats.get("upsets") or {}).get("1")
            if upset:
                lines.append(
                    QApplication.translate("app", "Biggest upset: {0} ({1}) over {2} ({3})").format(
                        upset["winner"]["name"],
                        upset["winner"]["seed"],
                        upset["loser"]["name"],
                        upset["loser"]["seed"],
                    )
                )
        phases = list((schedule.get("phases") or {}).values())
        if phases:
            lines.append(
                QApplication.translate("app", "Schedule: {0}").format(
                    ", ".join(
                        p["name"] + (f" {p['time']}" if p.get("time") else "") for p in phases
                    )
                )
            )
        if league:
            lines.append(
                QApplication.translate("app", "League: {0} ({1} players)").format(
                    league.get("name"), league.get("players")
                )
            )
        elif TournamentDataManager.instance.provider is not None:
            lines.append(QApplication.translate("app", "No league: paste its link above"))
        self.summary.setText("\n".join(lines))
