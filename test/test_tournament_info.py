# Checks the Tournament Info tab: loading the tournament's data into it, the
# fields changed since (their "Edited" badge, going back to the tournament's
# value), the banner, clearing it all and the narrow layout.
# Run from the repository root: python test/test_tournament_info.py
# (with an optional folder to save screenshots of the tab to)
import contextlib
import os
import sys
import tempfile
import time
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
for name, path in [("src", "src"), ("src.Helpers", "src/Helpers")]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

from qtpy.QtCore import QDate, QObject, QUrl, Signal
from qtpy.QtGui import QColor, QPixmap
from qtpy.QtWidgets import QApplication, QDateEdit, QLineEdit, QSpinBox, QWidget

app = QApplication.instance() or QApplication(sys.argv)

screenshots = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else None
repoDir = os.path.abspath(".")
workDir = tempfile.mkdtemp()
os.makedirs(os.path.join(workDir, "user_data"))
os.makedirs(os.path.join(workDir, "layout"))
os.chdir(workDir)
# Theme reads the icons from the repository
os.symlink(os.path.join(repoDir, "assets"), os.path.join(workDir, "assets"))
# and the locale helper the list of languages
os.symlink(os.path.join(repoDir, "src"), os.path.join(workDir, "src"))


class FakeState:
    data = {}

    @staticmethod
    def Get(key, default=None):
        value = FakeState.data
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return value

    @staticmethod
    def Set(key, value):
        target = FakeState.data
        parts = key.split(".")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value

    @staticmethod
    @contextlib.contextmanager
    def SaveBlock():
        yield


module = types.ModuleType("src.StateManager")
module.StateManager = FakeState
sys.modules["src.StateManager"] = module


class FakeTournamentSignals(QObject):
    tournament_data_updated = Signal(dict)
    tournament_changed = Signal()


class FakeProvider:
    name = "StartGG"
    url = "https://www.start.gg/tournament/hd-invitational-42/event/ultimate-singles"


class FakeTournamentDataManager:
    instance = None

    def __init__(self):
        self.signals = FakeTournamentSignals()
        self.provider = None
        self.loads = 0

    def GetTournamentData(self):
        self.loads += 1


FakeTournamentDataManager.instance = FakeTournamentDataManager()
module = types.ModuleType("src.TournamentDataManager")
module.TournamentDataManager = FakeTournamentDataManager
sys.modules["src.TournamentDataManager"] = module

from src.Theme import Theme  # noqa: E402
from src.TournamentInfoWidget import TournamentInfoWidget  # noqa: E402

Theme.Apply()

failures = []


def check(condition, message):
    if not condition:
        failures.append(message)
        print("FAIL:", message)


def shot(widget, name):
    if screenshots:
        os.makedirs(screenshots, exist_ok=True)
        app.processEvents()
        widget.grab().save(os.path.join(screenshots, name))


def info(key):
    return FakeState.Get(f"tournamentInfo.{key}")


# A banner to show, as a local file
banner = QPixmap(1200, 340)
banner.fill(QColor("#3949ab"))
bannerPath = os.path.join(workDir, "banner.png")
banner.save(bannerPath)
bannerUrl = QUrl.fromLocalFile(bannerPath).toString()

start = time.mktime((2026, 10, 24, 12, 0, 0, 0, 0, -1))
end = time.mktime((2026, 10, 25, 12, 0, 0, 0, 0, -1))
DATA = {
    "tournamentName": "HyperDrive Invitational #42",
    "eventName": "Ultimate Singles",
    "numEntrants": 128,
    "address": "1 Example Street, Springfield",
    "city": "Springfield",
    "state": "IL",
    "cityState": "Springfield, IL",
    "shortLink": "hd-invitational-42",
    "startAt": start,
    "endAt": end,
    "eventStartAt": start,
    "eventEndAt": "",
    "logo": "https://images.example/logo.png",
    "banner": bannerUrl,
    "initial_load": False,
}

widget = TournamentInfoWidget()
widget.resize(1060, 820)
widget.show()
app.processEvents()

# Before any tournament: nothing to load from, the fields' keys are sent
check(not widget.btLoadInfoFromTournament.isEnabled(), "load button is off without a tournament")
check(info("tournamentName") == "", "the text fields are sent empty at first")
check(widget.headerTitle.text() == "No tournament loaded", "header without a tournament")

# The web dashboard finds the fields by their key
for key, kind in [
    ("tournamentName", QLineEdit),
    ("eventName", QLineEdit),
    ("address", QLineEdit),
    ("cityState", QLineEdit),
    ("shortLink", QLineEdit),
    ("numEntrants", QSpinBox),
    ("startAt", QDateEdit),
    ("endAt", QDateEdit),
]:
    found = widget.findChild(QWidget, key)
    check(isinstance(found, kind), f"{key} is a {kind.__name__} named after its key")

# Loading the tournament
FakeTournamentDataManager.instance.provider = FakeProvider()
FakeTournamentDataManager.instance.signals.tournament_changed.emit()
check(widget.btLoadInfoFromTournament.isEnabled(), "load button is on with a tournament")
check(widget.btLoadInfoFromTournament.text() == "Load from start.gg", "load button names start.gg")
widget.btLoadInfoFromTournament.click()
check(FakeTournamentDataManager.instance.loads == 1, "load button loads the tournament's data")

FakeTournamentDataManager.instance.signals.tournament_data_updated.emit(dict(DATA))
app.processEvents()
check(info("tournamentName") == "HyperDrive Invitational #42", "tournament name sent")
check(info("numEntrants") == 128, "entrants sent")
check(info("cityState") == "Springfield, IL", "city and state sent together")
check(info("city") == "Springfield" and info("state") == "IL", "city and state sent alone")
check(widget.fields["startAt"].date() == QDate(2026, 10, 24), "start date shown")
check(widget.fields["endAt"].date() == QDate(2026, 10, 25), "end date shown")
check(bool(info("endAt")), "end date sent")
check(info("eventStartAt") == time.strftime("%x", time.localtime(start)), "event start sent")
check(info("eventEndAt") == "", "an empty event end is sent as it is")
check(info("banner") == bannerUrl, "banner sent")
check(widget.headerTitle.text() == "Loaded from start.gg", "header says where it's from")
check(widget.EditedCount() == 0, "nothing edited after loading")
check(not widget.btRestoreBanner.isVisible(), "no banner to restore")

# The banner preview loads
for _ in range(50):
    app.processEvents()
    if widget.bannerPixmap is not None:
        break
    time.sleep(0.02)
check(widget.bannerPixmap is not None, "banner preview loaded")

# Changing a field marks it
eventName = widget.fields["eventName"]
eventName.setText("Ultimate Singles — Top 8")
eventName.editingFinished.emit()
app.processEvents()
check(info("eventName") == "Ultimate Singles — Top 8", "edited event name sent")
check(widget.IsEdited("eventName"), "event name counts as edited")
block = next(b for b in widget.blocks if b[0] == ["eventName"])
check(block[1].isVisible() and block[2].isVisible(), "edited badge and revert button shown")
check("1 field changed by you" in widget.headerDetail.text(), "header counts the change")
check(widget.summaryValues["eventName"].text().startswith("●"), "summary marks the change")
shot(widget, "tournament_info.png")

# The city and state can be changed on their own
cityState = widget.fields["cityState"]
cityState.setText("Springfield")
cityState.editingFinished.emit()
check(info("cityState") == "Springfield", "edited city and state sent")
check(widget.IsEdited("cityState"), "city and state count as edited")
next(b for b in widget.blocks if b[0] == ["cityState"])[2].click()
check(info("cityState") == "Springfield, IL", "city and state reverted")

# Going back to the tournament's value
block[2].click()
check(eventName.text() == "Ultimate Singles", "revert gives the tournament's value back")
check(info("eventName") == "Ultimate Singles", "reverted value sent")
check(not block[1].isVisible(), "edited badge gone after reverting")

widget.fields["endAt"].setDate(QDate(2026, 10, 26))
datesBlock = next(b for b in widget.blocks if b[0] == ["startAt", "endAt"])
check(datesBlock[1].isVisible(), "a changed date marks the dates")
datesBlock[2].click()
check(widget.fields["endAt"].date() == QDate(2026, 10, 25), "dates reverted")

# Removing and restoring the banner
widget.btRemoveBanner.click()
check(info("banner") == "", "banner removed")
check(not widget.btRestoreBanner.isHidden(), "banner can be restored")
check(widget.EditedCount() == 1, "a removed banner counts as a change")
widget.btRestoreBanner.click()
check(info("banner") == bannerUrl, "banner restored")

# A start.gg tournament without dates doesn't fail
FakeTournamentDataManager.instance.signals.tournament_data_updated.emit(
    dict(DATA, startAt="", endAt="")
)
check(info("tournamentName") == "HyperDrive Invitational #42", "loaded without dates")

# A later load keeps the fields filled in at startup
widget.UpdateData({"eventName": "Doubles", "initial_load": True})
check(info("tournamentName") == "HyperDrive Invitational #42", "initial load keeps other fields")
check(info("eventName") == "Doubles", "initial load sets its fields")

# Narrow: the side column goes under the form
widget.resize(600, 900)
app.processEvents()
check(
    widget.bodyLayout.direction() == widget.bodyLayout.Direction.TopToBottom,
    "narrow tab stacks the side column",
)
shot(widget, "tournament_info_narrow.png")
widget.resize(1060, 820)
app.processEvents()

# Clearing it all
widget.btClearInfo.click()
check(info("tournamentName") == "" and info("numEntrants") == 0, "clear empties the fields")
check(info("cityState") == "", "clear empties the city and state")
check(info("banner") == "" and info("logo") == "", "clear empties the images")
check(widget.EditedCount() == 0, "nothing edited after clearing")
check(widget.headerTitle.text() == "Not loaded from the tournament", "header after clearing")
shot(widget, "tournament_info_cleared.png")

# Dropping a logo saves it as the layouts' logo
logo = QPixmap(64, 64)
logo.fill(QColor("#e53935"))
logoPath = os.path.join(workDir, "mylogo.png")
logo.save(logoPath)
widget.iconView.fileDropped.emit(logoPath)
check(os.path.isfile("./layout/logo.png"), "dropped logo saved")

if failures:
    print(f"{len(failures)} check(s) failed")
    sys.exit(1)
print("All tournament info checks passed")
