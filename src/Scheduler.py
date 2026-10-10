import traceback

from loguru import logger
from qtpy.QtCore import QObject, Qt, QTimer, Signal

# Each pull is a full event query, so it isn't allowed to run too often
COMPLETED_SETS_DEFAULT_INTERVAL_SECS = 60
COMPLETED_SETS_MIN_INTERVAL_SECS = 30
# Each scoreboard on auto update refreshes its set this often
SCOREBOARD_AUTO_UPDATE_DEFAULT_INTERVAL_SECS = 5
SCOREBOARD_AUTO_UPDATE_MIN_INTERVAL_SECS = 3
SCOREBOARD_AUTO_UPDATE_GROUP = "scoreboard_auto_update"
# The loaded bracket's set results are pulled this often
BRACKET_AUTO_UPDATE_DEFAULT_INTERVAL_SECS = 30
BRACKET_AUTO_UPDATE_MIN_INTERVAL_SECS = 15


class SchedulerSignals(QObject):
    # Name of the job that was started, stopped, ran or finished running
    job_state_changed = Signal(str)
    # Every second while any job is enabled, so countdown labels can share it
    tick = Signal()


class ScheduledJob:
    def __init__(self, name, callback, interval_ms, min_interval_ms, group):
        self.name = name
        self.callback = callback
        # Jobs of a group share their interval setting, e.g. one per scoreboard
        self.group = group
        self.min_interval_ms = min_interval_ms
        self.interval_ms = max(interval_ms, min_interval_ms)
        self.enabled = False
        self.running = False
        # A run was requested while running (e.g. the tournament changed
        # during a pull), so it runs again once done
        self.rerun = False
        # Lets a late done() from an older run be told apart from the current one
        self.run_id = 0
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        # Coarse timers can be 5% off, which shows in the countdowns
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)


class Scheduler(QObject):
    """Runs the recurring jobs of the application (e.g. the completed sets pull).

    A job's callback is called with a `done` function that it must call, from
    the GUI thread, once its work has finished (e.g. from a Worker's finished
    signal). A job never runs twice at the same time: runs requested while it's
    still running are folded into a single run that starts once it's done, and
    the next scheduled run starts one interval after the current one is done,
    so slow requests can't pile up.
    """

    instance: "Scheduler" = None
    TICK_MS = 1000

    def __init__(self) -> None:
        super().__init__(None)
        self.signals = SchedulerSignals()
        self.jobs: dict[str, ScheduledJob] = {}
        # Created on first use, once the QApplication exists
        self.tickTimer: QTimer = None

    def Register(self, name, callback, interval_ms, min_interval_ms=0, group=None):
        self.Unregister(name)
        job = ScheduledJob(name, callback, interval_ms, min_interval_ms, group)
        job.timer.timeout.connect(lambda job=job: self._Run(job))
        self.jobs[name] = job

    def Unregister(self, name):
        """Removes a job, e.g. when the widget it updates is deleted. A run
        still in progress finishes, but nothing runs after it."""
        job = self.jobs.pop(name, None)
        if job is None:
            return
        job.enabled = False
        job.rerun = False
        job.timer.stop()
        self._UpdateTickTimer()

    def Start(self, name, run_now=False):
        job = self.jobs[name]
        job.enabled = True
        if run_now:
            self._Run(job)
        elif not job.running:
            job.timer.start(job.interval_ms)
        self._UpdateTickTimer()
        self.signals.job_state_changed.emit(name)

    def Stop(self, name):
        job = self.jobs[name]
        job.enabled = False
        job.timer.stop()
        self._UpdateTickTimer()
        self.signals.job_state_changed.emit(name)

    def TriggerNow(self, name):
        self._Run(self.jobs[name])

    def SetInterval(self, name, interval_ms):
        job = self.jobs[name]
        job.interval_ms = max(interval_ms, job.min_interval_ms)
        if job.timer.isActive():
            job.timer.start(job.interval_ms)
            self.signals.job_state_changed.emit(name)

    def SetGroupInterval(self, group, interval_ms):
        for name, job in list(self.jobs.items()):
            if job.group == group:
                self.SetInterval(name, interval_ms)

    def IsEnabled(self, name):
        return self.jobs[name].enabled

    def IsRunning(self, name):
        return self.jobs[name].running

    def RemainingMs(self, name):
        """Time until the next run, or None if no run is scheduled."""
        job = self.jobs[name]
        if not job.timer.isActive():
            return None
        return max(0, job.timer.remainingTime())

    def _Run(self, job: ScheduledJob):
        if job.running:
            logger.debug(f"Scheduler: {job.name} is still running, running again once done")
            job.rerun = True
            return
        job.timer.stop()
        job.running = True
        job.run_id += 1
        run_id = job.run_id
        self.signals.job_state_changed.emit(job.name)

        def done():
            self._Done(job, run_id)

        try:
            job.callback(done)
        except Exception:
            logger.error(f"Scheduler: {job.name} failed: {traceback.format_exc()}")
            done()

    def _Done(self, job: ScheduledJob, run_id):
        if not job.running or run_id != job.run_id:
            return
        job.running = False
        if job.rerun:
            job.rerun = False
            self._Run(job)
            return
        if job.enabled:
            job.timer.start(job.interval_ms)
        # Not for a job that was unregistered while it ran
        if self.jobs.get(job.name) is job:
            self.signals.job_state_changed.emit(job.name)

    def _UpdateTickTimer(self):
        if self.tickTimer is None:
            self.tickTimer = QTimer()
            self.tickTimer.setInterval(self.TICK_MS)
            self.tickTimer.timeout.connect(self.signals.tick.emit)
        anyEnabled = any(job.enabled for job in self.jobs.values())
        if anyEnabled and not self.tickTimer.isActive():
            self.tickTimer.start()
        elif not anyEnabled:
            self.tickTimer.stop()


Scheduler.instance = Scheduler()
