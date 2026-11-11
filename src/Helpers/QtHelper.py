import functools
import os
import threading
import time

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtWidgets import QApplication

_STRICT_THREAD_ASSERT = os.environ.get("HYPERDRIVE_STRICT_THREAD_ASSERT", 0)
try:
    _STRICT_THREAD_ASSERT = int(_STRICT_THREAD_ASSERT)
except ValueError:
    logger.warning(
        f"Invalid value {_STRICT_THREAD_ASSERT} for _STRICT_THREAD_ASSERT. Defaulting to 0."
    )
    _STRICT_THREAD_ASSERT = 0


# =====================================================
# GUI THREAD DISPATCH
# =====================================================
# How often run_sync checks whether the GUI is shutting down while it waits
_SYNC_POLL_INTERVAL = 0.1


class GuiExecutor(QObject):
    _invoke = Signal(object)
    # object, not dict: the holder must reach the slot as the same dict, not a copy
    _invokeWithResult = Signal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Autoconnection makes this almost-free if the gui thread uses it.
        self._invoke.connect(self._run, Qt.ConnectionType.AutoConnection)
        self._invokeWithResult.connect(self._run, Qt.ConnectionType.AutoConnection)

        # Once the event loop stops, queued calls never run, so threads
        # waiting in run_sync must stop waiting
        self._shuttingDown = threading.Event()
        if (app := QCoreApplication.instance()) is not None:
            app.aboutToQuit.connect(self._shuttingDown.set)

    @Slot(object)
    @Slot(object, object)
    def _run(self, fn, resultHolder=None):
        if resultHolder is not None:
            try:
                resultHolder["result"] = fn()
            except Exception as e:
                resultHolder["result"] = None
                resultHolder["exc"] = e

            if (doneEvent := resultHolder.get("done", None)) is not None and isinstance(
                doneEvent, threading.Event
            ):
                doneEvent.set()
        else:
            fn()

    def __call__(self, fn, result_holder=None):
        if result_holder is None:
            self._invoke.emit(fn)
        else:
            self._invokeWithResult.emit(fn, result_holder)

    def run_sync(self, fn, timeout=None):
        """
        Runs fn on the gui thread and returns its result, blocking the calling thread until then.

        Raises TimeoutError if fn hasn't finished after `timeout` seconds, and RuntimeError if the
        application quits first. In both cases fn may still run later (or never), so the caller
        must not rely on its effects.
        """
        done = threading.Event()
        result_holder = {"done": done}
        # Fine if this throws exception... we want to re-throw anyway.
        self(fn, result_holder)

        deadline = None if timeout is None else time.monotonic() + timeout
        while not done.wait(_SYNC_POLL_INTERVAL):
            if self._shuttingDown.is_set():
                raise RuntimeError(f"The gui thread is shutting down, {fn} may not have run.")
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(f"{fn} didn't finish on the gui thread within {timeout}s.")

        if (exc := result_holder.get("exc", None)) is not None:
            raise exc
        else:
            return result_holder["result"]


gui_executor: GuiExecutor = None


def init_gui_executor():
    global gui_executor
    gui_executor = GuiExecutor(None)


def gui_thread_async(fn):
    """
    Helper decorator that automatically dispatches the target function to the gui thread. Note that there
    is no waiting and any changes caused by the dispatched function likely will not happen in the flow of the
    calling thread. If that is desired, look at `gui_thread_sync`
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if gui_executor is None:
            raise ValueError(
                "Can't marshal action to gui thread if the gui executor has not been initialized."
            )

        return gui_executor(lambda: fn(*args, **kwargs))

    return wrapper


def gui_thread_sync(fn):
    """
    Helper decorator that automatically dispatches the target function to the gui thread. Note that this
    function will block the calling thread until enough GUI cycles have completed to process the dispatched event.
    This is useful if it is desirable for changes to propagate before progressing, but it is slower than the async
    fire-and-forget version of this method.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if gui_executor is None:
            raise ValueError(
                "Can't marshal action to gui thread if the gui executor has not been initialized."
            )

        return gui_executor.run_sync(lambda: fn(*args, **kwargs))

    return wrapper


# =====================================================
# GUI THREAD CHECKS
# =====================================================
_app = None


def in_gui_thread() -> bool:
    global _app
    if _app is None and (_app := QApplication.instance()) is None:
        return False

    return _app.thread().isCurrentThread()


def assert_gui_thread(fn=None):
    """Functions as either a decorator or a standalone function with no args."""

    def _assert():
        if not in_gui_thread():
            if _STRICT_THREAD_ASSERT != 0:
                raise RuntimeError("Failed gui thread assertion in strict mode.")
            else:
                try:
                    raise RuntimeError("stack snapshot")
                except RuntimeError:
                    logger.opt(exception=True).warning(
                        "Failed gui thread assertion in permissive mode."
                    )

    if callable(fn):

        @functools.wraps(fn)
        def deco(*args, **kwargs):
            _assert()
            return fn(*args, **kwargs)

        return deco
    else:
        return _assert()


# =====================================================
# FOCUS
# =====================================================
class _FirstFocusFilter(QObject):
    def __init__(self, widgets, callback):
        super().__init__(widgets[0])
        self.widgets = widgets
        self.callback = callback
        for widget in widgets:
            widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.FocusIn and self.callback is not None:
            callback, self.callback = self.callback, None
            for widget in self.widgets:
                widget.removeEventFilter(self)
            callback()
        return False


def OnFirstFocus(widgets, callback):
    """Runs callback once, the first time one of the widgets gets focus. For
    setup that creates widgets only needed once a field is used, like a
    completer's popup: the popup can't show before the field has focus."""
    _FirstFocusFilter(list(widgets), callback)
