# Checks that the web server still has every HTTP route and socket.io event
# that clients use (the layouts, the web pages, the Stream Deck plugin and
# other tools): test/fixtures/web_server_surface.json lists them, and none may
# go missing. It also lists the events each event is answered with, which
# test_web_actions.py checks. New ones are fine; add them to the list with
#   python test/test_web_server_surface.py --update
# Run from the repository root: python test/test_web_server_surface.py
import json
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath("."))
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from qtpy.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from src.WebActionRegistry import ACTIONS
from src.WebServer import WebServer, api, sio

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
FIXTURE = os.path.join(FIXTURE, "web_server_surface.json")

# Adds the routes registered when the server is created (the player database
# admin, the dashboard and the files)
server = WebServer()


def Flatten(routes, prefix=""):
    for route in routes:
        # Newer FastAPI keeps an included router (the dashboard's, the
        # reporting pages') as one entry
        router = getattr(route, "original_router", None)
        if router is not None:
            yield from Flatten(router.routes, prefix + route.include_context.prefix)
        else:
            yield prefix + route.path, getattr(route, "methods", None)


def Routes():
    """Every route as "METHOD path", and mounted apps as "MOUNT path"."""
    routes = set()
    for path, methods in Flatten(api.routes):
        if methods is None:
            routes.add(f"MOUNT {path}")
        for method in methods or ():
            routes.add(f"{method} {path}")
    return sorted(routes)


def Events():
    return sorted(sio.handlers["/"].keys())


def TestNothingLost():
    with open(FIXTURE, encoding="utf-8") as f:
        expected = json.load(f)

    missing = sorted(set(expected["routes"]) - set(Routes()))
    assert not missing, f"HTTP routes that went missing: {missing}"

    missing = sorted(set(expected["events"]) - set(Events()))
    assert not missing, f"socket.io events that went missing: {missing}"
    print("TestNothingLost: OK")


if __name__ == "__main__":
    if "--update" in sys.argv:
        with open(FIXTURE, "w", encoding="utf-8") as f:
            replies = {a.socket: list(a.replies) for a in ACTIONS if a.socket}
            json.dump({"routes": Routes(), "events": Events(), "replies": replies}, f, indent=2)
            f.write("\n")
        print(f"Wrote {FIXTURE}")
    else:
        TestNothingLost()
