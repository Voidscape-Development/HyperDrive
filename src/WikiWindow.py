# The Guide window: the pages of docs/wiki (see Wiki.py) with a contents
# sidebar, search, and back and forward. Links to other pages open here,
# links to websites in the browser, and hyperdrive://open/<target> links
# open the part of the app they name (registered with RegisterAppLink).
import html
import re

from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from .Theme import Theme, ThemedIcon
from .Wiki import HOME_PAGE, AppLinkTarget, PageLink, Wiki

PAGE_ROLE = Qt.ItemDataRole.UserRole


def Highlight(text, query):
    """text as HTML, with the words of the search in bold"""
    words = [re.escape(w) for w in query.split() if w]
    if not words:
        return html.escape(text)
    # Split before escaping, so a word can't match inside an entity like &amp;
    parts = re.split("(" + "|".join(words) + ")", text, flags=re.IGNORECASE)
    return "".join(
        f"<b>{html.escape(part)}</b>" if i % 2 else html.escape(part)
        for i, part in enumerate(parts)
    )


class WikiWindow(QWidget):
    # target -> function that opens it, for hyperdrive://open/<target> links.
    # hyperdrive://open/<target>/<argument> calls it with the argument.
    APP_LINKS: dict = {}

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(QApplication.translate("wiki", "HyperDrive Guide"))
        self.setWindowIcon(ThemedIcon("assets/icons/book.svg"))
        self.resize(1000, 700)

        # [(page, anchor)] and the position in it
        self.history = []
        self.historyIndex = -1
        self.page = None

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        layout.addLayout(toolbar)

        self.backBt = self._ToolButton(
            "assets/icons/arrow_left.svg", QApplication.translate("wiki", "Back")
        )
        self.backBt.clicked.connect(lambda: self.Navigate(-1))
        toolbar.addWidget(self.backBt)

        self.forwardBt = self._ToolButton(
            "assets/icons/arrow_right.svg", QApplication.translate("wiki", "Forward")
        )
        self.forwardBt.clicked.connect(lambda: self.Navigate(1))
        toolbar.addWidget(self.forwardBt)

        homeBt = self._ToolButton("assets/icons/home.svg", QApplication.translate("wiki", "Home"))
        homeBt.clicked.connect(lambda: self.Open(HOME_PAGE))
        toolbar.addWidget(homeBt)

        self.search = QLineEdit()
        self.search.setPlaceholderText(QApplication.translate("wiki", "Search the guide"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.UpdateSearch)
        self.search.returnPressed.connect(self.OpenFirstResult)
        toolbar.addWidget(self.search, 1)

        QShortcut(QKeySequence.StandardKey.Find, self, activated=self._FocusSearch)
        QShortcut(QKeySequence.StandardKey.Back, self, activated=lambda: self.Navigate(-1))
        QShortcut(QKeySequence.StandardKey.Forward, self, activated=lambda: self.Navigate(1))
        QShortcut(QKeySequence("Alt+Home"), self, activated=lambda: self.Open(HOME_PAGE))
        QShortcut(QKeySequence("Esc"), self.search, activated=self.search.clear)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        # The contents, or the search results while searching
        self.sidebar = QStackedWidget()
        splitter.addWidget(self.sidebar)

        self.contents = QTreeWidget()
        self.contents.setHeaderHidden(True)
        self.contents.setRootIsDecorated(False)
        self.contents.setIndentation(12)
        self.contents.itemClicked.connect(self._ItemClicked)
        self.contents.itemActivated.connect(self._ItemClicked)
        self.sidebar.addWidget(self.contents)

        # A page of links, one per page found
        self.results = QTextBrowser()
        self.results.setOpenLinks(False)
        self.results.anchorClicked.connect(self._ResultClicked)
        self.resultPages = []
        self.sidebar.addWidget(self.results)

        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self.LinkClicked)
        self.browser.highlighted.connect(self._LinkHovered)
        splitter.addWidget(self.browser)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 740])

        self.status = QLabel()
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status.setStyleSheet("color: palette(placeholder-text);")
        layout.addWidget(self.status)

        self.FillContents()
        self.UpdateButtons()

    # =====================================================
    # SETUP
    # =====================================================
    def _ToolButton(self, icon, tooltip):
        button = QToolButton()
        button.setIcon(ThemedIcon(icon))
        button.setToolTip(tooltip)
        button.setAutoRaise(True)
        return button

    def StyleSheet(self):
        # QTextDocument's subset of CSS, in the theme's colors
        colors = Theme.Colors()
        text = colors["text"].name()
        muted = colors["muted"].name()
        border = colors["border"].name()
        raised = colors["raised"].name()
        accent = colors["accentText"].name()
        return f"""
            body {{ color: {text}; }}
            h1 {{ font-size: x-large; margin-bottom: 8px; }}
            h2 {{ font-size: large; margin-top: 18px; }}
            h3 {{ font-size: medium; margin-top: 14px; }}
            p, li {{ line-height: 130%; }}
            a {{ color: {accent}; }}
            a.app-link {{ color: {accent}; font-weight: bold; }}
            code {{ background-color: {raised}; font-family: monospace; }}
            pre {{ background-color: {raised}; font-family: monospace; padding: 6px; }}
            table {{ border-collapse: collapse; margin-top: 4px; margin-bottom: 8px; }}
            th {{ background-color: {raised}; text-align: left; }}
            th, td {{ border: 1px solid {border}; padding: 4px 8px; }}
            blockquote {{ color: {muted}; margin-left: 12px; }}
        """

    def FillContents(self):
        self.contents.clear()
        bold = self.contents.font()
        bold.setBold(True)
        for title, pages in Wiki.Sections():
            section = QTreeWidgetItem([title])
            section.setFont(0, bold)
            section.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.contents.addTopLevelItem(section)
            for page in pages:
                item = QTreeWidgetItem([page.title])
                item.setData(0, PAGE_ROLE, page.name)
                section.addChild(item)
        self.contents.expandAll()

    # =====================================================
    # APP LINKS
    # =====================================================
    def RegisterAppLink(target: str, open):
        WikiWindow.APP_LINKS[target] = open

    def OpenInApp(self, target):
        # "settings/api-keys" is the "settings" link, given "api-keys"
        name, _, argument = target.partition("/")
        open = WikiWindow.APP_LINKS.get(name)
        if open is None:
            logger.warning(f"The guide links to {target}, which isn't a part of the app")
            self.status.setText(
                QApplication.translate("wiki", "This version of HyperDrive can't open {0}.").format(
                    target
                )
            )
            return
        try:
            open(argument) if argument else open()
        except Exception:
            logger.opt(exception=True).error(f"Could not open {target} from the guide")

    # =====================================================
    # NAVIGATION
    # =====================================================
    def Open(self, page=None, anchor=None):
        """Shows the window, on page if given"""
        if page:
            self.ShowPage(page, anchor)
        elif self.page is None:
            self.ShowPage(HOME_PAGE)
        self.show()
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def ShowPage(self, page, anchor=None, addToHistory=True, highlight=None):
        if Wiki.Get(page) is None:
            logger.warning(f"The guide has no page named {page}")
            self.status.setText(
                QApplication.translate("wiki", "The page {0} doesn't exist.").format(page)
            )
            return

        if page != self.page or addToHistory is False:
            self.browser.document().setDefaultStyleSheet(self.StyleSheet())
            self.browser.setHtml(Wiki.Html(page))
        self.page = page

        if addToHistory:
            del self.history[self.historyIndex + 1 :]
            if not self.history or self.history[-1] != (page, anchor):
                self.history.append((page, anchor))
            self.historyIndex = len(self.history) - 1

        if anchor:
            self.browser.scrollToAnchor(anchor)
        else:
            self.browser.verticalScrollBar().setValue(0)

        if highlight:
            # Selects the first match, which also scrolls to it
            self.browser.moveCursor(QTextCursor.MoveOperation.Start)
            for word in highlight.split():
                if self.browser.find(word):
                    break

        self._SelectInContents(page)
        self.setWindowTitle(
            f"{Wiki.Get(page).title} - " + QApplication.translate("wiki", "HyperDrive Guide")
        )
        self.status.setText("")
        self.UpdateButtons()

    def _SelectInContents(self, page):
        iterator = QTreeWidgetItemIterator(self.contents)
        while iterator.value():
            item = iterator.value()
            if item.data(0, PAGE_ROLE) == page:
                self.contents.setCurrentItem(item)
                return
            iterator += 1
        self.contents.setCurrentItem(None)

    def Navigate(self, step):
        index = self.historyIndex + step
        if 0 <= index < len(self.history):
            self.historyIndex = index
            page, anchor = self.history[index]
            self.ShowPage(page, anchor, addToHistory=False)

    def UpdateButtons(self):
        self.backBt.setEnabled(self.historyIndex > 0)
        self.forwardBt.setEnabled(self.historyIndex < len(self.history) - 1)

    def _ItemClicked(self, item, column=0):
        page = item.data(0, PAGE_ROLE)
        if page:
            self.ShowPage(page)

    def LinkClicked(self, url: QUrl):
        href = url.toString()

        target = AppLinkTarget(href)
        if target is not None:
            self.OpenInApp(target)
            return

        if href.startswith("#"):
            self.ShowPage(self.page, href[1:])
            return

        link = PageLink(href)
        if link is not None:
            page, anchor = link
            self.ShowPage(page, anchor or None)
            return

        QDesktopServices.openUrl(url)

    def _LinkHovered(self, url: QUrl):
        href = url.toString()
        target = AppLinkTarget(href)
        if target is not None:
            self.status.setText(QApplication.translate("wiki", "Opens it in HyperDrive"))
        elif href and PageLink(href) is None and not href.startswith("#"):
            self.status.setText(href)
        else:
            self.status.setText("")

    # =====================================================
    # SEARCH
    # =====================================================
    def _FocusSearch(self):
        self.search.setFocus()
        self.search.selectAll()

    def UpdateSearch(self, text):
        if not text.strip():
            self.sidebar.setCurrentWidget(self.contents)
            return
        self.sidebar.setCurrentWidget(self.results)
        results = Wiki.Search(text, snippetWidth=120)
        self.resultPages = [page.name for page, _ in results]
        colors = Theme.Colors()
        if results:
            # The whole result is the link
            body = "".join(
                f'<p><a href="{page.name}.md" style="color: {colors["text"].name()};'
                f' text-decoration: none;"><b>{html.escape(page.title)}</b><br>'
                f'<span style="color: {colors["muted"].name()};">'
                f"{Highlight(snippet, text)}</span></a></p>"
                for page, snippet in results
            )
        else:
            body = "<p>" + QApplication.translate("wiki", "No pages match your search.") + "</p>"
        self.results.setHtml(body)

    def OpenFirstResult(self):
        if self.sidebar.currentWidget() is self.results and self.resultPages:
            self.ShowPage(self.resultPages[0], highlight=self.search.text())

    def _ResultClicked(self, url: QUrl):
        link = PageLink(url.toString())
        if link is not None:
            self.ShowPage(link[0], highlight=self.search.text())
