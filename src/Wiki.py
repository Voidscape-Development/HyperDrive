# The in-app guide: Markdown pages in docs/wiki, shown by the Guide window
# (WikiWindow.py) and served at /wiki by the web server. contents.json lists
# the sections of the sidebar and their pages, in order. A page is
# docs/wiki/<page>.md, and its title is its first "# " heading.
#
# Translations go in docs/wiki/<language>/<page>.md (e.g. docs/wiki/fr/home.md)
# and pages that aren't translated fall back to English. Links between pages
# are relative links to their .md files, so they also work on GitHub, and
# hyperdrive://open/<target> links open a part of the app (see
# WikiWindow.APP_LINKS); on the web page they're shown as plain text.
import html
import os
import re
import unicodedata

import markdown
import orjson
from loguru import logger
from markdown.extensions import Extension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.tables import TableExtension
from markdown.extensions.toc import TocExtension
from markdown.treeprocessors import Treeprocessor

from .Helpers.DirHelper import ResolvePath

WIKI_DIR = "docs/wiki"
HOME_PAGE = "home"
GETTING_STARTED_PAGE = "getting-started"
APP_SCHEME = "hyperdrive://"
APP_LINK_PREFIX = APP_SCHEME + "open/"

# A page name: lowercase words separated by dashes
PAGE_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def Normalize(text: str) -> str:
    """Lowercase and without accents, for searching"""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def PageLink(href: str):
    """(page, anchor) for a link to another page of the guide ("scoreboard.md",
    "scoreboard.md#teams"), otherwise None"""
    if "://" in href or href.startswith(("/", "mailto:")):
        return None
    path, _, anchor = href.partition("#")
    if not path:
        return None
    name = os.path.basename(path)
    if not name.endswith(".md"):
        return None
    return name[:-3], anchor


def AppLinkTarget(href: str):
    """The target of a hyperdrive://open/<target> link, otherwise None"""
    if href.startswith(APP_LINK_PREFIX):
        return href[len(APP_LINK_PREFIX) :].strip("/")
    return None


def PlainText(source: str) -> str:
    """A page's Markdown without its syntax, for search snippets"""
    text = re.sub(r"```.*?\n", "", source)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\|?[-:| ]+\|?\s*$", "", text, flags=re.MULTILINE)
    # List markers and quotes
    text = re.sub(r"^\s*(?:[-*>]|\d+\.)\s+", "", text, flags=re.MULTILINE)
    # Emphasis, but not the underscores of names like stream_queue
    text = re.sub(r"\*+|(?<!\w)_+|_+(?!\w)", "", text)
    text = re.sub(r"[`|]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class _LinkRewriter(Treeprocessor):
    """Points links between pages at where the page is shown, and turns links
    into the app into plain text on the web, where they can't work"""

    def __init__(self, md, web):
        super().__init__(md)
        self.web = web

    def run(self, root):
        for el in root.iter("a"):
            href = el.get("href", "")
            if AppLinkTarget(href) is not None:
                if self.web:
                    el.tag = "span"
                    del el.attrib["href"]
                    el.set("class", "app-link")
                    el.set("title", "Opens this in HyperDrive's desktop window")
                else:
                    el.set("class", "app-link")
                continue
            link = PageLink(href)
            if link is None:
                continue
            page, anchor = link
            if self.web:
                href = f"/wiki/{page}"
            else:
                href = f"{page}.md"
            el.set("href", href + (f"#{anchor}" if anchor else ""))


class _LinkExtension(Extension):
    def __init__(self, web):
        super().__init__()
        self.web = web

    def extendMarkdown(self, md):
        # After the inline patterns, which make the links
        md.treeprocessors.register(_LinkRewriter(md, self.web), "wiki_links", 5)


class Page:
    def __init__(self, name: str, path: str, source: str):
        self.name = name
        self.path = path
        self.source = source
        match = re.search(r"^#\s+(.+?)\s*$", source, flags=re.MULTILINE)
        self.title = match.group(1) if match else name.replace("-", " ").capitalize()
        self.headings = re.findall(r"^#{2,6}\s+(.+?)\s*$", source, flags=re.MULTILINE)
        self.text = PlainText(source)
        self._title = Normalize(self.title)
        self._headings = Normalize(" ".join(self.headings))
        self._text = Normalize(self.text)

    def Score(self, words: list[str]) -> int:
        """How well the page matches the search's words, 0 if it lacks one"""
        score = 0
        for word in words:
            count = self._text.count(word)
            if count == 0 and word not in self._title:
                return 0
            score += count + 20 * (word in self._title) + 5 * self._headings.count(word)
        return score

    def Snippet(self, words: list[str], width=160) -> str:
        """The text around the first match of the search"""
        positions = [self._text.find(w) for w in words if self._text.find(w) >= 0]
        if not positions:
            return self.text[:width] + ("…" if len(self.text) > width else "")
        start = max(0, min(positions) - width // 3)
        # Start on a word
        if start > 0:
            space = self.text.find(" ", start)
            start = space + 1 if 0 <= space < start + 20 else start
        end = min(len(self.text), start + width)
        return (
            ("…" if start > 0 else "")
            + self.text[start:end]
            + ("…" if end < len(self.text) else "")
        )


class Wiki:
    language: str | None = None
    # [{"title": str, "pages": [str]}]
    sections: list[dict] = []
    pages: dict[str, Page] = {}

    def Load(language: str | None = None):
        """Reads the pages, in language (e.g. "fr" or "pt-BR") where they're
        translated"""
        # Read into these, then swapped in at once: the web server reads
        # the guide from another thread
        pages = {}
        sections = []

        root = ResolvePath(WIKI_DIR)
        try:
            with open(os.path.join(root, "contents.json"), "rb") as file:
                sections = orjson.loads(file.read()).get("sections", [])
        except Exception:
            logger.opt(exception=True).error("Could not read the guide's contents.json")

        names = (
            [n[:-3] for n in sorted(os.listdir(root)) if n.endswith(".md")]
            if os.path.isdir(root)
            else []
        )
        for name in names:
            path = Wiki._PagePath(root, name, language)
            try:
                with open(path, encoding="utf-8") as file:
                    pages[name] = Page(name, path, file.read())
            except Exception:
                logger.opt(exception=True).error(f"Could not read the guide's page {path}")

        # Pages contents.json doesn't list go at the end, so none is hidden
        listed = {p for s in sections for p in s.get("pages", [])}
        unlisted = [n for n in pages if n not in listed]
        if unlisted:
            sections.append({"title": "More", "pages": unlisted})

        Wiki.language = language
        Wiki.sections = sections
        Wiki.pages = pages

    def _PagePath(root, name, language):
        for candidate in Wiki._Languages(language):
            path = os.path.join(root, candidate, f"{name}.md")
            if os.path.isfile(path):
                return path
        return os.path.join(root, f"{name}.md")

    def _Languages(language):
        """The folders to look in for a translation: "pt-BR" then "pt" """
        if not language or language.lower().startswith("en"):
            return []
        language = language.replace("_", "-")
        return [language, language.split("-")[0]] if "-" in language else [language]

    def EnsureLoaded():
        if not Wiki.pages:
            Wiki.Load(Wiki.language)

    def Get(name: str) -> Page | None:
        Wiki.EnsureLoaded()
        return Wiki.pages.get(name)

    def Sections() -> list[tuple[str, list[Page]]]:
        """The sidebar: each section's title and its pages that exist"""
        Wiki.EnsureLoaded()
        return [
            (s.get("title", ""), [Wiki.pages[p] for p in s.get("pages", []) if p in Wiki.pages])
            for s in Wiki.sections
        ]

    def Html(name: str, web=False) -> str:
        page = Wiki.Get(name)
        if page is None:
            return ""
        md = markdown.Markdown(
            extensions=[
                TableExtension(),
                FencedCodeExtension(),
                # Ids on the headings, for links to a part of a page
                TocExtension(permalink=False),
                _LinkExtension(web),
            ]
        )
        return md.convert(page.source)

    def Search(query: str, limit=50, snippetWidth=160) -> list[tuple[Page, str]]:
        """The pages with every word of the query, best match first, with the
        text around the match"""
        Wiki.EnsureLoaded()
        words = [w for w in Normalize(query).split() if w]
        if not words:
            return []
        scored = [(page.Score(words), page) for page in Wiki.pages.values()]
        scored = [(s, p) for s, p in scored if s > 0]
        scored.sort(key=lambda sp: (-sp[0], sp[1].title))
        return [(p, p.Snippet(words, snippetWidth)) for _, p in scored[:limit]]


# The guide's web page, at /wiki on the web server
WEB_STYLE = """
:root { color-scheme: light dark; --bg: #f2f3f7; --surface: #ffffff; --raised: #e7e9f0;
  --border: #c9cdd9; --text: #1b1d27; --muted: #5c6275; --accent: #d02670; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #14151b; --surface: #1c1e26; --raised: #262935; --border: #353a4a;
    --text: #e9eaf0; --muted: #9298ab; --accent: #e8689f; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 16px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
a { color: var(--accent); }
.layout { display: flex; min-height: 100vh; }
nav { width: 270px; flex-shrink: 0; padding: 16px; border-right: 1px solid var(--border);
  background: var(--surface); }
nav .brand { display: block; font-weight: 700; font-size: 18px; color: var(--text);
  text-decoration: none; margin-bottom: 12px; }
nav form input { width: 100%; padding: 8px 10px; border: 1px solid var(--border);
  border-radius: 6px; background: var(--bg); color: var(--text); font: inherit; }
nav h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .06em;
  color: var(--muted); margin: 18px 0 4px; }
nav ul { list-style: none; margin: 0; padding: 0; }
nav li a { display: block; padding: 3px 8px; border-radius: 6px; color: var(--text);
  text-decoration: none; }
nav li a:hover { background: var(--raised); }
nav li a.current { background: var(--accent); color: #fff; }
main { flex: 1; min-width: 0; padding: 24px 40px 64px; max-width: 900px;
  overflow-wrap: break-word; }
main h1 { margin-top: 0; }
code { background: var(--raised); padding: 1px 5px; border-radius: 4px; font-size: .92em;
  overflow-wrap: anywhere; }
pre { background: var(--raised); padding: 12px; border-radius: 6px; overflow-x: auto; }
pre code { padding: 0; background: none; }
table { border-collapse: collapse; display: block; overflow-x: auto; margin: 8px 0 16px; }
th, td { border: 1px solid var(--border); padding: 6px 10px; text-align: left;
  vertical-align: top; }
th { background: var(--raised); }
blockquote { margin: 0; padding-left: 12px; border-left: 3px solid var(--border);
  color: var(--muted); }
.app-link { font-weight: 600; border-bottom: 1px dotted var(--muted); cursor: help; }
.result { margin-bottom: 18px; }
.result p { margin: 2px 0 0; color: var(--muted); }
details.contents > summary { display: none; }
@media (max-width: 760px) {
  .layout { display: block; }
  nav { width: auto; border-right: none; border-bottom: 1px solid var(--border); }
  details.contents > summary { display: block; cursor: pointer; margin-top: 12px;
    color: var(--muted); }
  main { padding: 16px; }
}
"""


def _WebNav(current=None, query=""):
    sections = []
    for title, pages in Wiki.Sections():
        items = "".join(
            f'<li><a href="/wiki/{p.name}"'
            + (' class="current" aria-current="page"' if p.name == current else "")
            + f">{html.escape(p.title)}</a></li>"
            for p in pages
        )
        sections.append(f"<h2>{html.escape(title)}</h2><ul>{items}</ul>")
    return (
        '<nav><a class="brand" href="/wiki">HyperDrive Guide</a>'
        '<form action="/wiki/search" role="search">'
        f'<input type="search" name="q" value="{html.escape(query)}" '
        'placeholder="Search the guide" aria-label="Search the guide"></form>'
        '<details class="contents" open><summary>Contents</summary>'
        + "".join(sections)
        + "</details></nav>"
        # On a phone the contents start folded, so the page comes first
        + "<script>if (matchMedia('(max-width: 760px)').matches)"
        + " document.querySelector('details.contents').open = false;</script>"
    )


def _WebDocument(title, nav, body):
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(title)} - HyperDrive Guide</title>"
        f"<style>{WEB_STYLE}</style></head><body>"
        f'<div class="layout">{nav}<main>{body}</main></div></body></html>'
    )


def WebPage(name: str) -> str | None:
    """A page of the guide for the browser, None if there's no such page"""
    page = Wiki.Get(name)
    if page is None:
        return None
    return _WebDocument(page.title, _WebNav(name), Wiki.Html(name, web=True))


def WebSearchPage(query: str) -> str:
    results = Wiki.Search(query)
    if results:
        body = "".join(
            f'<div class="result"><a href="/wiki/{p.name}">{html.escape(p.title)}</a>'
            f"<p>{html.escape(snippet)}</p></div>"
            for p, snippet in results
        )
    else:
        body = "<p>No pages match your search.</p>"
    heading = f"<h1>Search: {html.escape(query)}</h1>" if query.strip() else "<h1>Search</h1>"
    return _WebDocument("Search", _WebNav(query=query), heading + body)
