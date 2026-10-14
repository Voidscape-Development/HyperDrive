import json

from loguru import logger

from .DirHelper import ResolvePath

# GitHub repository ("owner/name") HyperDrive is published from. Unset until
# the project moves to its new repository, which leaves the updater and the
# alerts feed as stubs: no releases or alerts are fetched.
REPOSITORY = None

# Where HyperDrive's source, releases and issues are, for the About dialog
# and the Help menu
PROJECT_URL = "https://github.com/Voidscape-Development/HyperDrive"


def get_versions() -> dict:
    """assets/versions.json, or {} if it can't be read"""
    try:
        with open(ResolvePath("./assets/versions.json"), encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        logger.error("Local version file not found")
        return {}


def get_program_version(default="?") -> str:
    return get_versions().get("program", default)


def get_supported_providers():
    return get_versions().get("supported_providers", [])
