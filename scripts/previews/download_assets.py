"""Downloads the game asset packs the preview sample data uses into
user_data/games, the way TSH's asset downloader does.

Usage: python scripts/previews/download_assets.py
"""

import json
import os
import shutil
import sys
import tempfile

import py7zr
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
ASSETS_JSON = "https://raw.githubusercontent.com/joaorb64/StreamHelperAssets/main/assets.json"
RELEASE = "https://github.com/joaorb64/StreamHelperAssets/releases/latest/download/"


def download(url, out):
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            out.write(chunk)


def main():
    with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
        packs = json.load(f)["asset_packs"]

    assets = requests.get(ASSETS_JSON, timeout=60).json()

    for game, keys in packs.items():
        for key in keys:
            files = sorted(assets[game]["assets"][key]["files"].values(), key=lambda f: f["name"])
            print(f"Downloading {game} {key} ({sum(f.get('size', 0) for f in files) // 1000000}MB)")

            with tempfile.TemporaryDirectory() as tmp:
                # Multi part archives are split files, joined back before extracting
                merged = os.path.join(tmp, files[0]["name"])
                with open(merged, "wb") as out:
                    for f in files:
                        download(RELEASE + f["name"], out)

                extract_path = os.path.join(ROOT, "user_data", "games", game)
                os.makedirs(extract_path, exist_ok=True)
                if ".7z" in files[0]["name"]:
                    with py7zr.SevenZipFile(merged, "r") as archive:
                        archive.extractall(extract_path)
                else:
                    shutil.move(merged, os.path.join(extract_path, files[0]["name"]))


if __name__ == "__main__":
    sys.exit(main())
