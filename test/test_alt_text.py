# Checks the descriptive text for results: the simple mode's options, the
# templates with their [[ ]] optional parts, and seeds, Twitter and links.
# Run from the repository root: python test/test_alt_text.py
import os
import sys
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
for name, path in [("src", "src"), ("src.Helpers", "src/Helpers")]:
    package = types.ModuleType(name)
    package.__path__ = [os.path.abspath(path)]
    sys.modules[name] = package

from src.SettingsManager import SettingsManager

SettingsManager.SaveSettings = lambda: None

from qtpy.QtCore import QCoreApplication

app = QCoreApplication.instance() or QCoreApplication(sys.argv)

from src.Helpers.AltTextHelper import fill_template, generate_alt_text, load_options


def Player(name, twitter="", pronoun="", seed=0, country="", characters=()):
    return {
        "mergedName": name,
        "name": name,
        "twitter": twitter,
        "pronoun": pronoun,
        "seed": seed,
        "country": {"code": country} if country else {},
        "character": {
            str(i + 1): {"name": c, "variant": {"name": v} if v else {}}
            for i, (c, v) in enumerate(characters)
        },
    }


DATA = {
    "tournamentInfo": {
        "tournamentName": "Big House",
        "eventName": "Singles",
        "startAt": "2026-10-01",
        "shortLink": "bighouse",
    },
    "game": {"name": "Ultimate"},
    "commentary": {"1": {"mergedName": "Caster"}},
    "player_list": {
        "slot": {
            "1": {"player": {"1": Player("Alice", "@alice", "she/her", 3, "US", [("Fox", "Red")])}},
            "2": {"player": {"1": Player("Bob", "bob", seed=1, characters=[("Falco", "")])}},
            "5": {"name": "Duo", "player": {"1": Player("Cy"), "2": Player("Di", seed=8)}},
            "6": {"name": "", "player": {"1": Player("")}},
        }
    },
}


def Options(**changes):
    options = load_options()
    options.update(changes)
    return options


def TestSimpleDefaults():
    text = generate_alt_text(DATA, Options())
    assert text.splitlines()[:3] == ["BIG HOUSE", "Singles - 2026-10-01", "Game: Ultimate"]
    assert "1/ Alice (US, Fox - Red)" in text
    assert "2/ Bob (Falco)" in text
    assert "5/ Duo [Cy / Di]" in text
    assert "Commentators: Caster" in text
    # Empty slots are left out
    assert "6/" not in text
    assert text.endswith("Stream powered by HyperDrive")
    assert "@" not in text and "Seed" not in text and "start.gg" not in text
    print("TestSimpleDefaults: OK")


def TestSimpleExtras():
    options = Options(
        show_twitter=True,
        show_pronoun=True,
        show_seed=True,
        show_bracket_link=True,
        show_variants=False,
        header_text="Results!",
        footer_text="#BigHouse",
    )
    text = generate_alt_text(DATA, options, bracket_link="https://start.gg/t/event/singles")
    assert text.splitlines()[0] == "Results!"
    assert "Bracket: https://start.gg/t/event/singles" in text
    assert "1/ Alice @alice (she/her) (US, Fox) - Seed 3" in text
    assert "2/ Bob @bob (Falco) - Seed 1" in text
    # A team's seed is its first seeded player's
    assert "5/ Duo [Cy / Di] - Seed 8" in text
    assert text.endswith("#BigHouse")
    # No link given: the short link is used
    assert "Bracket: https://start.gg/bighouse" in generate_alt_text(DATA, options)
    print("TestSimpleExtras: OK")


def TestFillTemplate():
    values = {"name": "Bob", "twitter": "", "seed": "4"}
    assert fill_template("{name}[[ ({twitter})]][[ #{seed}]]", values) == "Bob #4"
    # Unknown names are kept so a typo shows
    assert fill_template("{nmae}", values) == "{nmae}"
    print("TestFillTemplate: OK")


def TestTemplateMode():
    options = Options(
        mode="template",
        template_header="{tournament} | {bracket_link}",
        template_entry="#{placement} [[{team}: ]]{players}[[ (seed {seed})]]",
        template_player="{name}[[ {twitter}]]",
        template_footer="[[Casters: {commentators}]]",
    )
    text = generate_alt_text(DATA, options, bracket_link="link")
    assert text == (
        "Big House | link\n\n"
        "#1 Alice @alice (seed 3)\n"
        "#2 Bob @bob (seed 1)\n"
        "#5 Duo: Cy / Di (seed 8)\n\n"
        "Casters: Caster"
    ), text
    print("TestTemplateMode: OK")


def TestEmptyState():
    assert "STANDINGS:" in generate_alt_text({}, Options())
    generate_alt_text({}, Options(mode="template"))
    print("TestEmptyState: OK")


TestSimpleDefaults()
TestSimpleExtras()
TestFillTemplate()
TestTemplateMode()
TestEmptyState()
