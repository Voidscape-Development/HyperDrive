# Checks Scheduler: runs never overlap, runs requested while running are
# folded into one, intervals are clamped, and a job finishing on a Worker
# thread reschedules correctly.
# Run from the repository root: python test/test_scheduler.py
import os
import sys
import threading
import time
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from qtpy.QtCore import QCoreApplication, QEventLoop, QThreadPool, QTimer

from src.Scheduler import Scheduler
from src.Workers import Worker

app = QCoreApplication.instance() or QCoreApplication(sys.argv)


def Wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def TestNoOverlapAndRerun():
    scheduler = Scheduler()
    calls = []
    scheduler.Register("job", lambda done: calls.append(done), 60000)

    scheduler.TriggerNow("job")
    assert len(calls) == 1 and scheduler.IsRunning("job")
    # Requested twice while running: folded into a single extra run
    scheduler.TriggerNow("job")
    scheduler.TriggerNow("job")
    assert len(calls) == 1

    calls[0]()
    assert len(calls) == 2 and scheduler.IsRunning("job")
    # A late or repeated done() from the previous run is ignored
    calls[0]()
    assert scheduler.IsRunning("job")

    calls[1]()
    assert not scheduler.IsRunning("job")
    # Not enabled, so nothing is scheduled
    assert scheduler.RemainingMs("job") is None


def TestStartStopAndInterval():
    scheduler = Scheduler()
    calls = []
    scheduler.Register("job", lambda done: [calls.append(1), done()], 1000, min_interval_ms=500)

    scheduler.SetInterval("job", 10)
    assert scheduler.jobs["job"].interval_ms == 500

    scheduler.Start("job")
    assert calls == [] and scheduler.IsEnabled("job")
    assert 0 < scheduler.RemainingMs("job") <= 500
    Wait(1300)
    assert len(calls) == 2, calls

    scheduler.Stop("job")
    assert scheduler.RemainingMs("job") is None
    Wait(700)
    assert len(calls) == 2

    scheduler.Start("job", run_now=True)
    assert len(calls) == 3
    assert scheduler.RemainingMs("job") is not None
    scheduler.Stop("job")


def TestUnregister():
    scheduler = Scheduler()
    calls = []
    changed = []
    scheduler.signals.job_state_changed.connect(changed.append)
    scheduler.Register("job", lambda done: calls.append(done), 1000)
    scheduler.Start("job", run_now=True)
    # Removed while running, with a rerun pending
    scheduler.TriggerNow("job")
    scheduler.Unregister("job")
    assert "job" not in scheduler.jobs
    changed.clear()
    calls[0]()
    # Neither the rerun nor the next scheduled run happen
    assert len(calls) == 1
    assert changed == []
    assert not scheduler.tickTimer.isActive()
    # The name can be registered again
    scheduler.Register("job", lambda done: done(), 1000)
    scheduler.Unregister("job")
    scheduler.Unregister("job")


def TestGroupInterval():
    scheduler = Scheduler()
    for name in ("a", "b"):
        scheduler.Register(name, lambda done: done(), 5000, min_interval_ms=3000, group="g")
    scheduler.Register("other", lambda done: done(), 5000)
    scheduler.Start("a")
    scheduler.SetGroupInterval("g", 1000)
    assert scheduler.jobs["a"].interval_ms == 3000
    assert scheduler.jobs["b"].interval_ms == 3000
    assert scheduler.jobs["other"].interval_ms == 5000
    # The running countdown picks up the new interval right away
    assert scheduler.RemainingMs("a") <= 3000
    scheduler.Stop("a")


def TestFailingCallback():
    scheduler = Scheduler()

    def Fail(done):
        raise RuntimeError("expected")

    scheduler.Register("job", Fail, 1000)
    scheduler.Start("job", run_now=True)
    assert not scheduler.IsRunning("job")
    assert scheduler.RemainingMs("job") is not None
    scheduler.Stop("job")


def TestWorkerFinished():
    scheduler = Scheduler()
    pool = QThreadPool()
    results = []
    doneThreads = []

    def Job(done):
        worker = Worker(lambda progress_callback, cancel_event: time.sleep(0.1) or 42)
        worker.signals.result.connect(results.append)
        # done() starts a QTimer, so it has to be called on the GUI thread
        worker.signals.finished.connect(
            lambda: [doneThreads.append(threading.current_thread()), done()]
        )
        pool.start(worker)

    scheduler.Register("job", Job, 60000)
    scheduler.Start("job", run_now=True)
    assert scheduler.IsRunning("job")
    Wait(500)
    assert results == [42]
    assert doneThreads == [threading.main_thread()]
    assert not scheduler.IsRunning("job")
    assert scheduler.RemainingMs("job") is not None
    scheduler.Stop("job")


for test in (
    TestNoOverlapAndRerun,
    TestStartStopAndInterval,
    TestUnregister,
    TestGroupInterval,
    TestFailingCallback,
    TestWorkerFinished,
):
    test()
    print(f"{test.__name__}: OK")
