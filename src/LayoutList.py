"""The layout pages in layout/, for GET /layouts: tools such as the OBS
plugin use it to let the user pick a layout without browsing for its file."""

import os

# Folders in layout/ that hold layouts' shared files rather than a layout,
# and old layouts that aren't kept working (as in render_previews.py)
SKIPPED = {"include", "fonts", "icons", "game_screenshots", "deprecated"}


def ListLayouts(root="."):
    """Every layout folder with its pages, sorted by name:
    {"layouts": [{"folder", "pages": [{"name", "path", "preview"}]}]}.
    Paths are relative to root (the web server's root), with "/", so they
    can be appended to the server's address. "preview" is the page's
    <page>_preview.png, or None if it has none."""
    layout_dir = os.path.join(root, "layout")
    layouts = []
    try:
        folders = sorted(os.listdir(layout_dir), key=str.lower)
    except OSError:
        return {"layouts": []}

    for folder in folders:
        folder_path = os.path.join(layout_dir, folder)
        if folder in SKIPPED or folder.startswith(".") or not os.path.isdir(folder_path):
            continue
        try:
            files = set(os.listdir(folder_path))
        except OSError:
            continue
        pages = []
        for file in sorted(files, key=str.lower):
            name, ext = os.path.splitext(file)
            if ext.lower() != ".html" or not os.path.isfile(os.path.join(folder_path, file)):
                continue
            preview = f"{name}_preview.png"
            pages.append(
                {
                    "name": name,
                    "path": f"layout/{folder}/{file}",
                    "preview": f"layout/{folder}/{preview}" if preview in files else None,
                }
            )
        if pages:
            layouts.append({"folder": folder, "pages": pages})
    return {"layouts": layouts}
