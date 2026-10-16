# Checks GuiExecutor.run_sync: calls from a worker thread run on the GUI
# thread and return their result or exception, calls from the GUI thread run
# inline, a timeout stops the wait, and so does the application quitting.
# Run from the repository root: python test/test_qt_helper.py
import os
import sys
import threading
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from qtpy.QtCore import QCoreApplication, QEventLoop, QTimer

app = QCoreApplication.instance() or QCoreApplication(sys.argv)

from src.Helpers import QtHelper

QtHelper.init_gui_executor()
executor = QtHelper.gui_executor


def RunInThread(fn):
    """Runs fn on a new thread while the GUI thread processes events, and
    returns what fn returned or raised."""
    outcome = {}

    def Target():
        try:
            outcome["result"] = fn()
        except Exception as e:
            outcome["exc"] = e

    thread = threading.Thread(target=Target)
    loop = QEventLoop()
    thread.start()
    timer = QTimer()
    timer.timeout.connect(lambda: thread.is_alive() or loop.quit())
    timer.start(10)
    loop.exec()
    timer.stop()
    return outcome


def TestFromWorkerThread():
    outcome = RunInThread(lambda: executor.run_sync(threading.current_thread))
    assert outcome["result"] is threading.main_thread()


def TestExceptionReachesCaller():
    def Fail():
        raise ValueError("boom")

    outcome = RunInThread(lambda: executor.run_sync(Fail))
    assert isinstance(outcome["exc"], ValueError)


def TestFromGuiThread():
    # No event loop running: it has to run inline, or it would wait forever
    assert executor.run_sync(lambda: 42) == 42


def TestDecorator():
    @QtHelper.gui_thread_sync
    def Add(a, b=0):
        return (a + b, threading.current_thread())

    outcome = RunInThread(lambda: Add(1, b=2))
    assert outcome["result"] == (3, threading.main_thread())


def TestTimeout():
    # The GUI thread is busy joining the worker, so the call can't run
    outcome = {}

    def Target():
        try:
            executor.run_sync(lambda: None, timeout=0.3)
        except Exception as e:
            outcome["exc"] = e

    thread = threading.Thread(target=Target)
    thread.start()
    thread.join(5)
    assert not thread.is_alive()
    assert isinstance(outcome["exc"], TimeoutError)
    # The queued call still runs once the GUI thread gets to it
    app.processEvents()


def TestShutdown():
    # The application quits before getting to the call: the caller must not
    # wait forever
    outcome = {}
    quit = threading.Event()
    app.aboutToQuit.connect(quit.set)

    def Target():
        # Called once the event loop has stopped, so the call is never run
        quit.wait(5)
        try:
            executor.run_sync(lambda: None)
        except Exception as e:
            outcome["exc"] = e

    thread = threading.Thread(target=Target)
    thread.start()
    QTimer.singleShot(0, app.quit)
    app.exec()
    thread.join(5)
    assert not thread.is_alive()
    assert isinstance(outcome["exc"], RuntimeError)


for test in (
    TestFromWorkerThread,
    TestExceptionReachesCaller,
    TestFromGuiThread,
    TestDecorator,
    TestTimeout,
    # Last: it quits the application
    TestShutdown,
):
    test()
    print(f"{test.__name__}: OK")
