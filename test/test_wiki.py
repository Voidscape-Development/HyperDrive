# Checks the in-app guide (docs/wiki): every page is listed and has a title,
# links between pages and to their headings work, hyperdrive:// links name a
# part of the app that exists, and search and translations work.
# Run from the repository root: python test/test_wiki.py
import ast
import os
import re
import shutil
import sys
import tempfile
import types

sys.path.insert(0, os.path.abspath("."))
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from markdown.extensions.toc import slugify

import src.Wiki as WikiModule
from src.Wiki import (
    HOME_PAGE,
    PAGE_NAME,
    AppLinkTarget,
    PageLink,
    WebPage,
    WebSearchPage,
    Wiki,
)

LINK = re.compile(r"\]\(([^)\s]+)\)")


def Read(path):
    with open(path, encoding="utf-8") as file:
        return file.read()


def AppTargets():
    """The hyperdrive://open/<target> targets the main window registers, and
    the settings pages settings/<page> can open"""
    source = Read("src/HyperDrive.py")
    start = source.index("self.RegisterGuideLinks(")
    docks = source[start : source.index(")", source.index("}", start))]
    targets = set(re.findall(r'"([a-z-]+)":', docks))
    targets |= set(re.findall(r'RegisterAppLink\(\s*"([a-z/-]+)"', source))
    # The keys passed to add_setting_widget()
    pages = {
        node.args[2].value
        for node in ast.walk(ast.parse(Read("src/Settings/SettingsWindow.py")))
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", "") == "add_setting_widget"
        and len(node.args) > 2
    }
    return targets, pages


def Anchors(page):
    return {slugify(h, "-") for h in page.headings}


def TestPagesAreListed():
    Wiki.Load()
    listed = [p for section in Wiki.sections for p in section.get("pages", [])]
    assert len(listed) == len(set(listed)), "A page is listed twice in contents.json"
    files = {n[:-3] for n in os.listdir("docs/wiki") if n.endswith(".md")}
    assert set(listed) == files, (
        f"Not listed: {files - set(listed)}, listed without a file: {set(listed) - files}"
    )
    assert HOME_PAGE in files
    for name in files:
        assert PAGE_NAME.match(name), f"{name}: page names are lowercase words with dashes"
        assert name != "search", "/wiki/search is the search page"


def TestPagesHaveTitles():
    Wiki.Load()
    for page in Wiki.pages.values():
        assert re.match(r"#\s+\S", page.source), f"{page.name} doesn't start with a # title"


def TestLinks():
    Wiki.Load()
    targets, settingsPages = AppTargets()
    assert "settings" in targets and "scoreboard" in targets, targets
    assert "api-keys" in settingsPages and "general" in settingsPages, settingsPages
    for page in Wiki.pages.values():
        for href in LINK.findall(page.source):
            target = AppLinkTarget(href)
            if target is not None:
                name, _, argument = target.partition("/")
                assert name in targets, f"{page.name}: no app link target {name}"
                if name == "settings" and argument:
                    assert argument in settingsPages, f"{page.name}: no settings page {argument}"
                continue
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            if href.startswith("#"):
                assert href[1:] in Anchors(page), f"{page.name}: no heading {href}"
                continue
            link = PageLink(href)
            assert link is not None, f"{page.name}: {href} isn't a page of the guide"
            name, anchor = link
            assert href.split("#")[0] == f"{name}.md", f"{page.name}: link pages by file name"
            assert name in Wiki.pages, f"{page.name}: no page {name}"
            if anchor:
                assert anchor in Anchors(Wiki.pages[name]), f"{page.name}: no heading {href}"


def TestRendering():
    Wiki.Load()
    for name in Wiki.pages:
        desktop = Wiki.Html(name)
        web = Wiki.Html(name, web=True)
        assert "<h1" in desktop and "<h1" in web
        # The web page can't open the app
        assert 'href="hyperdrive://' not in web, name
        # Pages link to /wiki/<page> on the web, to <page>.md in the window
        for href in re.findall(r'href="([^"]+)"', web):
            if "://" in href:
                continue
            assert not href.endswith(".md") and ".md#" not in href, (name, href)
        assert WebPage(name).startswith("<!doctype html>")

    html = Wiki.Html("home", web=True)
    assert 'href="/wiki/getting-started"' in html
    assert 'class="app-link"' in html
    assert 'href="getting-started.md"' in Wiki.Html("home")
    assert 'href="hyperdrive://open/settings"' in Wiki.Html("home")
    assert WebPage("no-such-page") is None
    # Tables and headings with ids, for #anchors
    html = Wiki.Html("scoreboard")
    assert "<table>" in html and 'id="several-scoreboards"' in html


def TestSearch():
    Wiki.Load()
    results = Wiki.Search("stream deck")
    assert results and results[0][0].name == "stream-deck", [p.name for p, _ in results]
    # Every word has to be there, accents and case don't matter
    assert Wiki.Search("ÉVENT STATS")[0][0].name == "event-stats"
    assert Wiki.Search("stream xyzzyunknownword") == []
    assert Wiki.Search("   ") == []
    page, snippet = Wiki.Search("profanity")[0]
    assert page.name == "settings" and "profanity" in snippet.lower(), snippet
    assert "Stream Deck" in WebSearchPage("stream deck")
    assert "No pages match" in WebSearchPage("xyzzyunknownword")
    # The query is escaped on the page
    page = WebSearchPage("<script>alert(1)</script>")
    assert "<script>alert" not in page and "&lt;script&gt;alert" in page


def TestTranslations():
    folder = tempfile.mkdtemp()
    try:
        with open(os.path.join(folder, "contents.json"), "w") as file:
            file.write('{"sections": [{"title": "Start", "pages": ["home", "other"]}]}')
        for name, text in [("home", "# Home"), ("other", "# Other"), ("extra", "# Extra")]:
            with open(os.path.join(folder, f"{name}.md"), "w") as file:
                file.write(text)
        os.makedirs(os.path.join(folder, "pt"))
        with open(os.path.join(folder, "pt", "home.md"), "w") as file:
            file.write("# Início")

        WikiModule.WIKI_DIR = folder
        Wiki.Load("pt-BR")
        assert Wiki.Get("home").title == "Início"
        # Not translated: English
        assert Wiki.Get("other").title == "Other"
        Wiki.Load("en-US")
        assert Wiki.Get("home").title == "Home"
        # A page contents.json doesn't list still gets a place in the sidebar
        sections = Wiki.Sections()
        assert [p.name for p in sections[-1][1]] == ["extra"], sections
    finally:
        WikiModule.WIKI_DIR = "docs/wiki"
        shutil.rmtree(folder)
        Wiki.Load()


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in list(globals().items()) if name.startswith("Test")]
    for name, fn in tests:
        fn()
        print(f"{name} OK")
    print(f"All {len(tests)} tests passed")
