import time

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from src.GameAssetManager import GameAssetManager
from src.Helpers import AssetCatalog
from src.Helpers.QtHelper import gui_thread_async
from src.Workers import Worker

from .Theme import ThemedIcon

# A catalog older than this is fetched again when the window opens or the
# game's assets load
CATALOG_MAX_AGE = 10 * 60

JOB_QUEUED = "queued"
JOB_DOWNLOADING = "downloading"
JOB_UNPACKING = "unpacking"
JOB_DONE = "done"
JOB_FAILED = "failed"
JOB_CANCELLED = "cancelled"
ACTIVE_STATES = (JOB_QUEUED, JOB_DOWNLOADING, JOB_UNPACKING)


class DownloadJob:
    """One pack to download and install. Jobs run one at a time, in order."""

    def __init__(self, game, pack, gameName, packName, files):
        self.game = game
        self.pack = pack
        self.gameName = gameName
        self.packName = packName
        self.files = files
        self.state = JOB_QUEUED
        self.total = sum(f["size"] for f in files)
        self.done = 0
        # Bytes per second, smoothed
        self.speed = 0.0
        self.error = ""
        self.cancelEvent = None
        self.cancelRequested = False
        self._sample = None

    @property
    def active(self):
        return self.state in ACTIVE_STATES

    def SecondsLeft(self):
        if self.speed <= 0:
            return None
        return max(0, self.total - self.done) / self.speed


class AssetDownloaderSignals(QObject):
    # {game: [pack info]} of installed packs with a newer version
    AssetUpdates = Signal(dict)
    # The catalog loaded, failed to load or started loading
    catalogChanged = Signal()
    # Jobs added, removed, started or finished
    jobsChanged = Signal()
    # A running job's progress
    jobProgress = Signal(object)


class AssetDownloader(QObject):
    instance: "AssetDownloader" = None

    def __init__(self) -> None:
        super().__init__()
        self.threadpool = QThreadPool()
        # Logos are many small requests: kept apart so they never wait on a download
        self.logoPool = QThreadPool()
        self.logoPool.setMaxThreadCount(4)
        self.signals = AssetDownloaderSignals()

        self.catalog = None
        self.catalogError = None
        self.catalogTime = None
        self.catalogLoading = False
        # Game logos loaded this session, {game: PNG bytes or None}
        self.logos = {}
        # Logos being loaded, {game: [callbacks]}
        self.logoWaiters = {}

        self.jobs = []
        self.runningJob = None
        self.installedSomething = False
        self.window = None

    def UiMounted(self):
        self.iconUpdateAvailable = ThemedIcon("assets/icons/update_available.svg")
        self.iconInstalled = ThemedIcon("assets/icons/installed.svg")
        # Installed versions change when the games are loaded again
        GameAssetManager.instance.signals.onLoadAssets.connect(self.EmitUpdates)
        # A download would otherwise hold up quitting until it finished
        QApplication.instance().aboutToQuit.connect(self.CancelAll)
        QApplication.instance().aboutToQuit.connect(self.logoPool.clear)

    # =====================================================
    # CATALOG
    # =====================================================
    def CatalogIsFresh(self):
        return (
            self.catalog is not None
            and self.catalogTime is not None
            and time.monotonic() - self.catalogTime < CATALOG_MAX_AGE
        )

    def LoadCatalog(self, force=False):
        if self.catalogLoading:
            return
        if not force and self.CatalogIsFresh():
            self.EmitUpdates()
            return

        self.catalogLoading = True
        self.signals.catalogChanged.emit()
        worker = Worker(lambda progress_callback, cancel_event: AssetCatalog.FetchCatalog())
        worker.signals.result.connect(self._CatalogLoaded)
        worker.signals.error.connect(self._CatalogFailed)
        self.threadpool.start(worker)

    def _CatalogLoaded(self, catalog):
        self.catalog = catalog
        self.catalogError = None
        self.catalogTime = time.monotonic()
        self.catalogLoading = False
        self.signals.catalogChanged.emit()
        self.EmitUpdates()

    def _CatalogFailed(self, error):
        _, value, _ = error
        self.catalogError = str(value)
        self.catalogLoading = False
        self.signals.catalogChanged.emit()

    def Updates(self):
        if self.catalog is None:
            return []
        return AssetCatalog.Updates(self.catalog, GameAssetManager.instance.games)

    def EmitUpdates(self):
        updates = {}
        for game, pack in self.Updates():
            updates.setdefault(game, []).append(self.catalog[game]["assets"][pack])
        self.signals.AssetUpdates.emit(updates)

    def CheckAssetUpdates(self, game_codename=None):
        self.LoadCatalog()

    def RequestLogo(self, game, onLoaded):
        """Calls onLoaded(game, bytes or None) with the game's logo. It comes
        from the disk cache when it can, and is loaded once a session however
        many times it's asked for."""
        if game in self.logos:
            onLoaded(game, self.logos[game])
            return
        if game in self.logoWaiters:
            # Already loading: called back with the others
            self.logoWaiters[game].append(onLoaded)
            return
        self.logoWaiters[game] = [onLoaded]

        def Loaded(data):
            self.logos[game] = data
            for callback in self.logoWaiters.pop(game, []):
                callback(game, data)

        worker = Worker(lambda progress_callback, cancel_event: AssetCatalog.LoadLogo(game))
        worker.signals.result.connect(Loaded)
        # Not kept as missing: a later request tries again
        worker.signals.error.connect(lambda error: self.logoWaiters.pop(game, None))
        self.logoPool.start(worker)

    # =====================================================
    # WINDOW
    # =====================================================
    def DownloadAssets(self, main_window):
        if self.window is None:
            from src.AssetDownloaderWindow import AssetDownloaderWindow

            self.window = AssetDownloaderWindow(main_window)
        self.window.Open()
        self.LoadCatalog(force=self.catalogError is not None)

    # =====================================================
    # DOWNLOAD QUEUE
    # =====================================================
    def ActiveJob(self, game, pack):
        for job in self.jobs:
            if job.game == game and job.pack == pack and job.active:
                return job
        return None

    def JustInstalled(self, game, pack):
        """Installed by a job this session, though the games may not have been
        loaded again yet to show it."""
        for job in reversed(self.jobs):
            if job.game == game and job.pack == pack:
                return job.state == JOB_DONE
        return False

    def Enqueue(self, packs):
        """Queues [(game, pack)] from the catalog. A game without its base files
        gets them first, since its other packs need them."""
        games = GameAssetManager.instance.games
        toAdd = []
        for game, pack in packs:
            if (
                pack != AssetCatalog.BASE_FILES
                and not AssetCatalog.HasBaseFiles(games, game)
                and not self.JustInstalled(game, AssetCatalog.BASE_FILES)
                and (game, AssetCatalog.BASE_FILES) not in toAdd
            ):
                toAdd.append((game, AssetCatalog.BASE_FILES))
            if (game, pack) not in toAdd:
                toAdd.append((game, pack))

        # Base files go first, so they're installed before the packs that need them
        toAdd.sort(key=lambda p: p[1] != AssetCatalog.BASE_FILES)

        for game, pack in toAdd:
            if self.ActiveJob(game, pack) is not None:
                continue
            info = self.catalog[game]
            self.jobs.append(
                DownloadJob(
                    game,
                    pack,
                    info.get("name", game),
                    # The catalog names base files after the game
                    QApplication.translate("app", "Base files")
                    if pack == AssetCatalog.BASE_FILES
                    else info["assets"][pack].get("name", pack),
                    AssetCatalog.PackFiles(self.catalog, game, pack),
                )
            )
        self.signals.jobsChanged.emit()
        self._StartNext()

    def _StartNext(self):
        if self.runningJob is not None:
            return
        job = next((j for j in self.jobs if j.state == JOB_QUEUED), None)
        if job is None:
            if self.installedSomething:
                self.installedSomething = False
                # Picks up what was installed, then EmitUpdates runs again
                GameAssetManager.instance.LoadGames()
            return

        job.state = JOB_DOWNLOADING
        job.done = 0
        job.speed = 0.0
        job._sample = None
        self.runningJob = job

        def Run(progress_callback, cancel_event):
            return AssetCatalog.InstallPack(
                job.game,
                job.pack,
                job.files,
                progress_callback,
                cancel_event.is_set,
                onUnpack=lambda: gui_thread_async(self._JobUnpacking)(job),
            )

        worker = Worker(Run)
        job.cancelEvent = worker.cancel_event
        if job.cancelRequested:
            job.cancelEvent.set()
        worker.signals.progress.connect(lambda n, t: self._JobProgress(job, n, t))
        worker.signals.result.connect(lambda ok: self._JobResult(job, ok))
        worker.signals.error.connect(lambda error: self._JobFailed(job, error))
        worker.signals.finished.connect(lambda: self._JobFinished(job))
        self.threadpool.start(worker)
        self.signals.jobsChanged.emit()

    def _JobProgress(self, job, done, total):
        job.done = done
        job.total = total
        now = time.monotonic()
        if job._sample is None:
            job._sample = (now, done)
        else:
            then, before = job._sample
            if now - then >= 0.5:
                speed = (done - before) / (now - then)
                job.speed = speed if job.speed == 0 else job.speed * 0.7 + speed * 0.3
                job._sample = (now, done)
        self.signals.jobProgress.emit(job)

    def _JobUnpacking(self, job):
        if job.state == JOB_DOWNLOADING:
            job.state = JOB_UNPACKING
            self.signals.jobsChanged.emit()

    def _JobResult(self, job, ok):
        if ok:
            job.state = JOB_DONE
            self.installedSomething = True
        else:
            job.state = JOB_CANCELLED

    def _JobFailed(self, job, error):
        _, value, _ = error
        job.state = JOB_FAILED
        job.error = str(value)
        logger.error(f"Downloading {job.game}/{job.pack} failed: {value}")

    def _JobFinished(self, job):
        if job.active:
            # Neither result nor error arrived: count it as failed, not stuck
            job.state = JOB_FAILED
        self.runningJob = None
        self.signals.jobsChanged.emit()
        self._StartNext()

    def Cancel(self, job):
        if job.state == JOB_QUEUED:
            job.state = JOB_CANCELLED
        elif job.active:
            job.cancelRequested = True
            if job.cancelEvent is not None:
                job.cancelEvent.set()
        self.signals.jobsChanged.emit()

    def CancelAll(self):
        for job in list(self.jobs):
            if job.active:
                self.Cancel(job)

    def Retry(self, job):
        if job.active:
            return
        self.jobs.remove(job)
        job.state = JOB_QUEUED
        job.error = ""
        job.done = 0
        job.cancelRequested = False
        job.cancelEvent = None
        self.jobs.append(job)
        self.signals.jobsChanged.emit()
        self._StartNext()

    def ClearFinished(self):
        self.jobs = [j for j in self.jobs if j.active]
        self.signals.jobsChanged.emit()

    def RemovePack(self, game, pack):
        try:
            AssetCatalog.RemovePack(game, pack)
        finally:
            GameAssetManager.instance.LoadGames()


AssetDownloader.instance = AssetDownloader()
