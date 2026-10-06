"""Renders the preview image of layout pages: <page>_preview.png next to each
page, 1920x1080 with a transparent background, using sample_state.json as the
program state.

Usage, from anywhere, after download_assets.py:
    python scripts/previews/render_previews.py [--all] [layout folder...]

With folders (e.g. layout/scoreboard), renders the pages in them. With --all,
every layout's pages. Needs Playwright with Chromium (or a Chromium at
$CHROMIUM_PATH).
"""

import argparse
import asyncio
import glob
import json
import os
import shutil
import sys
import time

from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
LAYOUT_DIR = os.path.join(ROOT, "layout")
STATE_FILE = os.path.join(ROOT, "out", "program_state.json")

# Folders in layout/ that hold layouts' shared files rather than a layout,
# and old layouts that aren't kept working
SKIPPED = {"include", "fonts", "icons", "game_screenshots", "deprecated"}

with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
    CONFIG = json.load(f)


def warn(page, message):
    # Shown as an annotation on GitHub Actions
    prefix = f"::warning file={page}::" if os.environ.get("GITHUB_ACTIONS") else "Warning: "
    print(f"{prefix}{page}: {message}")


def layout_folders():
    folders = []
    for path in sorted(glob.glob(os.path.join(LAYOUT_DIR, "*", ""))):
        if os.path.basename(os.path.dirname(path)) not in SKIPPED:
            folders.append(path)
    return [os.path.dirname(f) for f in folders]


def pages_of(folder):
    pages = []
    for page in sorted(glob.glob(os.path.join(folder, "*.html"))):
        key = os.path.relpath(page, ROOT).replace(os.sep, "/")
        options = CONFIG.get("pages", {}).get(key, {})
        if options.get("skip"):
            continue
        name = os.path.splitext(os.path.basename(page))[0]
        pages.append(
            {
                "key": key,
                "path": page,
                "query": options.get("query", ""),
                "output": os.path.join(folder, options.get("output", f"{name}_preview.png")),
                "wait": options.get("wait", CONFIG.get("wait", 3000)),
            }
        )
    return pages


async def render(browser, page_info, semaphore):
    async with semaphore:
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        # Layouts log "Start()" when they start their animations, once they
        # have loaded their data
        started = asyncio.Event()
        page.on("console", lambda m: started.set() if m.text == "Start()" else None)
        try:
            url = "file://" + page_info["path"].replace(os.sep, "/")
            if page_info["query"]:
                url += "?" + page_info["query"]
            await page.goto(url, wait_until="load")
            try:
                await asyncio.wait_for(started.wait(), timeout=30)
            except TimeoutError:
                # Broken with the sample data: keep the preview it has
                warn(
                    page_info["key"],
                    "didn't start in 30s, preview not updated" + "".join(f"; {e}" for e in errors),
                )
                return False
            # Frames are slow to draw without a GPU, and GSAP slows its
            # animations down to match by default
            await page.evaluate("window.gsap && gsap.ticker.lagSmoothing(0)")
            await page.evaluate("document.fonts.ready")
            # Let the animations play
            await page.wait_for_timeout(page_info["wait"])
            await page.screenshot(path=page_info["output"], omit_background=True)
            print(f"Rendered {os.path.relpath(page_info['output'], ROOT)}")
            for error in errors:
                warn(page_info["key"], error)
            return True
        except Exception as e:
            warn(page_info["key"], f"failed: {e}")
            return False
        finally:
            await context.close()


async def render_all(pages):
    semaphore = asyncio.Semaphore(CONFIG.get("parallel", 4))
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            args=["--allow-file-access-from-files"],
            # To use a Chromium other than Playwright's own
            executable_path=os.environ.get("CHROMIUM_PATH") or None,
        )
        try:
            results = await asyncio.gather(*[render(browser, page, semaphore) for page in pages])
        finally:
            await browser.close()
    print(f"Rendered {sum(results)} of {len(results)} pages")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("folders", nargs="*", help="Layout folders to render")
    parser.add_argument("--all", action="store_true", help="Render every layout")
    args = parser.parse_args()

    if args.all:
        folders = layout_folders()
    else:
        folders = []
        for folder in args.folders:
            folder = os.path.abspath(folder)
            if not os.path.isdir(folder):
                print(f"Skipping {folder}, it isn't a folder (removed?)")
                continue
            folders.append(folder)

    pages = [page for folder in folders for page in pages_of(folder)]
    if not pages:
        print("No pages to render")
        return 0

    # Layouts read the program state from out/program_state.json. Keep the
    # one that's there, if any, to put it back after
    backup = STATE_FILE + ".preview_backup"
    had_state = os.path.isfile(STATE_FILE)
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    if had_state:
        shutil.copy(STATE_FILE, backup)
    with open(os.path.join(HERE, "sample_state.json"), encoding="utf-8") as f:
        state = json.load(f)
    # Layouts only take data newer than what they have
    state["timestamp"] = time.time()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)

    try:
        asyncio.run(render_all(pages))
    finally:
        if had_state:
            shutil.move(backup, STATE_FILE)
        else:
            os.remove(STATE_FILE)

    return 0


if __name__ == "__main__":
    sys.exit(main())
