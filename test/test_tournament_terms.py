# Checks the user's match and phase names and pronouns: cleaning them up,
# saving and loading them, and how they replace or add to the built-in names.
# Run from the repository root: python test/test_tournament_terms.py
import json
import os
import sys
import tempfile
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from src.SettingsManager import SettingsManager

SettingsManager.SaveSettings = lambda: None

from qtpy.QtCore import QCoreApplication

app = QCoreApplication.instance() or QCoreApplication(sys.argv)

import src.Helpers.LocaleHelper as LocaleHelperModule
import src.Helpers.PronounHelper as PronounHelperModule
from src.Helpers.LocaleHelper import LocaleHelper
from src.Helpers.PronounHelper import NormalizePronouns, PronounHelper

tmp = tempfile.mkdtemp()
LocaleHelperModule.CUSTOM_TERMS_FILE = os.path.join(tmp, "tournament_terms.json")
PronounHelperModule.PRONOUNS_FILE = os.path.join(tmp, "pronouns_list.txt")

# Normalizing drops empty and invalid entries and duplicate extras
normalized = LocaleHelper.NormalizeCustomTerms(
    {
        "match": {"grand_final": "Grand Finals", "winners_final": "", "bad": 3},
        "phase": "not a dict",
        "custom_match": ["Side Event", " Side Event ", "", None],
    }
)
assert normalized == {
    "match": {"grand_final": "Grand Finals"},
    "phase": {},
    "custom_match": ["Side Event"],
    "custom_phase": [],
}, normalized
assert LocaleHelper.NormalizeCustomTerms(None)["match"] == {}

# Without a file, the names in use are the defaults
LocaleHelper.fgTermLocale = "en-US"
LocaleHelper.LoadRoundNames()
assert LocaleHelper.matchNames["grand_final"] == "Grand Final"
assert LocaleHelper.defaultNames["phase"]["top_8"] == "Top 8"
assert LocaleHelper.customTerms["custom_phase"] == []

# A translation missing a term keeps the English one
LocaleHelper.fgTermLocale = "fr"
LocaleHelper.LoadRoundNames()
assert LocaleHelper.matchNames["grand_final"] != "Grand Final"
assert set(LocaleHelper.defaultNames["match"]) >= set(
    json.load(open("src/i18n/tournament_term/en.json"))["match"]
)
LocaleHelper.fgTermLocale = "en-US"
LocaleHelper.LoadRoundNames()

# Saving applies the names right away and tells the dropdowns
emitted = []
LocaleHelper.signals.termsChanged.connect(lambda: emitted.append(True))
assert LocaleHelper.SaveCustomTerms(
    {
        "match": {"grand_final": "Grand Finals", "my_key": "Amateur Final"},
        "phase": {"top_8": ""},
        "custom_phase": ["Amateur Bracket"],
    }
)
assert emitted == [True]
assert LocaleHelper.matchNames["grand_final"] == "Grand Finals"
assert LocaleHelper.matchNames["my_key"] == "Amateur Final"
assert LocaleHelper.phaseNames["top_8"] == "Top 8"
assert LocaleHelper.defaultNames["match"]["grand_final"] == "Grand Final"

# ...and they're loaded again on the next start
saved = json.load(open(LocaleHelperModule.CUSTOM_TERMS_FILE, encoding="utf-8"))
assert saved["custom_phase"] == ["Amateur Bracket"]
LocaleHelper.matchNames = {}
LocaleHelper.LoadRoundNames()
assert LocaleHelper.matchNames["grand_final"] == "Grand Finals"
assert LocaleHelper.customTerms["custom_phase"] == ["Amateur Bracket"]


# The dropdowns list the extra names, and refilling one keeps its text
class FakeCombo:
    def __init__(self):
        self.items, self.text = [], ""

    def addItem(self, text):
        self.items.append(text)

    def findText(self, text):
        return self.items.index(text) if text in self.items else -1

    def clear(self):
        self.items = []

    def currentText(self):
        return self.text

    def setCurrentText(self, text):
        self.text = text

    def blockSignals(self, block):
        pass


combo = FakeCombo()
combo.text = "Pools"
LocaleHelper.RefreshNamesInWidget(combo, LocaleHelper.LoadPhaseNamesToWidget)
assert combo.items[0] == "" and combo.items[1] == "Amateur Bracket"
assert "Pool A" in combo.items and combo.text == "Pools"

combo = FakeCombo()
LocaleHelper.LoadMatchNamesToWidget(combo)
assert "Grand Finals" in combo.items and "Grand Final" not in combo.items

# A broken file doesn't stop the defaults from loading
with open(LocaleHelperModule.CUSTOM_TERMS_FILE, "w") as f:
    f.write("{ not json")
LocaleHelper.LoadRoundNames()
assert LocaleHelper.matchNames["grand_final"] == "Grand Final"

# Pronouns: cleaned up, saved one per line, and added once
assert NormalizePronouns([" she/her ", "", "he/him", "she/her", None]) == ["she/her", "he/him"]
assert PronounHelper.Load() == [] and os.path.isfile(PronounHelperModule.PRONOUNS_FILE)
assert PronounHelper.Save(["they/them", "", "she/her", "they/them"])
assert PronounHelper.Model().stringList() == ["they/them", "she/her"]
PronounHelper.Add("él/ella")
PronounHelper.Add("she/her")
PronounHelper.Add("  ")
assert PronounHelper.Model().stringList() == ["they/them", "she/her", "él/ella"]
assert PronounHelper.Load() == ["they/them", "she/her", "él/ella"]

print("All tournament term tests passed")
