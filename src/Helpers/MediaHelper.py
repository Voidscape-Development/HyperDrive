import os
import re
import shutil

from loguru import logger
from PIL import Image
from qtpy.QtCore import QObject, Signal

# Characters that can't be in (Windows) file names; replaced by _
INVALID_CHARACTERS = r"[,/|;:<>\\?*]"

AVATAR_DIR = "./user_data/player_avatar"
SPONSOR_LOGO_DIR = "./user_data/sponsor_logo"
TEAM_LOGO_DIR = "./user_data/team_logo"
CUSTOM_PLAYER_DIR = "./user_data/custom_player_export"

# What the image pickers accept; saved as PNG
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff")


class MediaHelperSignals(QObject):
    # A player's media, a sponsor logo or a team logo was changed from the app
    changed = Signal()


class MediaHelper:
    """Where HyperDrive looks for the images and files of players, sponsors
    and teams in user_data, and saving them there."""

    signals = MediaHelperSignals()

    def Sanitize(name: str) -> str:
        return re.sub(INVALID_CHARACTERS, "_", name)

    def AvatarPath(team: str, name: str) -> str:
        merged = f"{team} {name}" if team else name
        return f"{AVATAR_DIR}/{MediaHelper.Sanitize(merged)}.png"

    def SponsorLogoPath(sponsor: str) -> str:
        return f"{SPONSOR_LOGO_DIR}/{MediaHelper.Sanitize(sponsor).upper()}.png"

    def TeamLogoPath(team: str) -> str:
        return f"{TEAM_LOGO_DIR}/{team.lower()}.png"

    def CustomFolderPath(name: str) -> str:
        """Where a new custom data folder for this tag is made"""
        return f"{CUSTOM_PLAYER_DIR}/{MediaHelper.Sanitize(name).strip()}"

    def IsImage(path: str) -> bool:
        return os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS

    def ImageFilter() -> str:
        """For QFileDialog"""
        return "Images (" + " ".join(f"*{e}" for e in IMAGE_EXTENSIONS) + ")"

    def SaveImageAsPng(source: str, destination: str):
        """Copies the image at source to destination as a PNG, converting it
        if it's in another format. Raises OSError if it can't be read or saved."""
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        # Written next to it then moved, so layouts never load half a file
        temporary = destination + ".tmp"
        try:
            if os.path.splitext(source)[1].lower() == ".png":
                shutil.copyfile(source, temporary)
            else:
                with Image.open(source) as image:
                    if image.mode not in ("RGB", "RGBA", "L", "LA"):
                        image = image.convert("RGBA")
                    image.save(temporary, "PNG")
            os.replace(temporary, destination)
        except Exception as e:
            if os.path.exists(temporary):
                os.remove(temporary)
            if isinstance(e, OSError):
                raise
            # PIL raises its own errors for files that aren't images
            raise OSError(f"{os.path.basename(source)} isn't an image HyperDrive can read") from e
        logger.info(f"Saved {source} as {destination}")

    def Remove(path: str):
        if os.path.isfile(path):
            os.remove(path)
            logger.info(f"Removed {path}")
        elif os.path.isdir(path):
            shutil.rmtree(path)
            logger.info(f"Removed {path}")

    def ListPngs(folder: str) -> list[str]:
        """The names (without .png) of the images in folder"""
        if not os.path.isdir(folder):
            return []
        return sorted(
            (
                os.path.splitext(e.name)[0]
                for e in os.scandir(folder)
                if e.name.lower().endswith(".png")
            ),
            key=str.lower,
        )

    def Changed():
        MediaHelper.signals.changed.emit()
