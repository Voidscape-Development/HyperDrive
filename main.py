#!/usr/bin/env python3

import asyncio
import multiprocessing
import os
import signal
import sys

# Before anything imports Qt
os.environ["QT_API"] = "PyQt6"


if __name__ == "__main__":
    # Pyinstaller fix: a child process of the executable (multiprocessing
    # helpers) stops here, before the whole application is loaded
    multiprocessing.freeze_support()

    from qasync import QEventLoop

    import src

    try:
        loop = QEventLoop(src.App)
        asyncio.set_event_loop(loop)
        window = src.Window(loop)
        try:
            loop.add_signal_handler(signal.SIGINT, lambda: window.close())
            loop.add_signal_handler(signal.SIGTERM, lambda: window.close())
        except NotImplementedError:  # windows...
            pass

        # To run synchronously, you would do something like the following:
        # sys.exit(src.App.exec())

        # Since this is a QEventLoop, afaik it will run App.exec() in the background.
        with loop:
            loop.run_forever()

    except asyncio.exceptions.CancelledError:
        sys.exit(255)
    except RuntimeError:
        sys.exit(255)
