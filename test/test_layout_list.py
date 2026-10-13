# Checks the layout list of GET /layouts: folders and pages, previews, and the
# folders that aren't layouts.
# Run from the repository root: python test/test_layout_list.py
import os
import sys
import tempfile
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

from src.LayoutList import ListLayouts

root = tempfile.mkdtemp()


def touch(path):
    path = os.path.join(root, path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").close()


touch("layout/scoreboard/index.html")
touch("layout/scoreboard/index_preview.png")
touch("layout/scoreboard/index.js")
touch("layout/scoreboard/Bblue.html")
touch("layout/scoreboard - MTF/index.html")
touch("layout/include/globals.html")
touch("layout/deprecated/old/index.html")
touch("layout/only_css/index.css")
touch("layout/settings.json")

result = ListLayouts(root)
assert [layout["folder"] for layout in result["layouts"]] == ["scoreboard", "scoreboard - MTF"], (
    result
)

pages = result["layouts"][0]["pages"]
assert pages == [
    {"name": "Bblue", "path": "layout/scoreboard/Bblue.html", "preview": None},
    {
        "name": "index",
        "path": "layout/scoreboard/index.html",
        "preview": "layout/scoreboard/index_preview.png",
    },
], pages

# No layout folder at all
assert ListLayouts(os.path.join(root, "missing")) == {"layouts": []}

# The real layouts: every page is listed, with the preview it has
real = ListLayouts(".")
folders = {layout["folder"]: layout for layout in real["layouts"]}
assert "scoreboard_simple" in folders and "include" not in folders, list(folders)
for layout in real["layouts"]:
    for page in layout["pages"]:
        assert os.path.isfile(page["path"]), page
        assert page["preview"] is None or os.path.isfile(page["preview"]), page

print("OK")
