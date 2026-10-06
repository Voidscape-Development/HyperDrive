# Checks the files of players, sponsors and teams in user_data: where
# MediaHelper looks for them, saving images as PNG, the sponsor logos a
# player gets, and DynamicExport keeping avatars and sponsor logos up to date.
# Run from the repository root: python test/test_player_media.py
import os
import sys
import tempfile
import types

sys.path.insert(0, os.path.abspath("."))
# Import only the modules needed, not the whole application
package = types.ModuleType("src")
package.__path__ = [os.path.abspath("src")]
sys.modules["src"] = package

# Everything reads and writes ./user_data
os.chdir(tempfile.mkdtemp())
os.makedirs("user_data")

from PIL import Image

from src.Helpers.DynamicExport import DynamicExport
from src.Helpers.MediaHelper import MediaHelper
from src.Helpers.SponsorHelper import SponsorHelper
from src.StateManager import StateManager

PATH = "score.1.team.1.player.1"


def Image_(path, mode="RGB", size=(8, 8)):
    Image.new(mode, size, "red").save(path)
    return path


def TestPaths():
    assert MediaHelper.AvatarPath("HD", "Bay|Blade") == "./user_data/player_avatar/HD Bay_Blade.png"
    assert MediaHelper.AvatarPath("", "Azure") == "./user_data/player_avatar/Azure.png"
    assert MediaHelper.SponsorLogoPath("hd") == "./user_data/sponsor_logo/HD.png"
    assert MediaHelper.TeamLogoPath("Team Azure") == "./user_data/team_logo/team azure.png"
    assert MediaHelper.CustomFolderPath("a/b ") == "./user_data/custom_player_export/a_b"


def TestSaveImageAsPng():
    source = Image_("photo.jpg")
    destination = MediaHelper.SponsorLogoPath("HD")
    MediaHelper.SaveImageAsPng(source, destination)
    with Image.open(destination) as image:
        assert image.format == "PNG"
        assert image.size == (8, 8)

    # Palette and CMYK images become RGBA
    Image.new("CMYK", (4, 4)).save("print.jpg")
    MediaHelper.SaveImageAsPng("print.jpg", MediaHelper.SponsorLogoPath("GG"))
    with Image.open(MediaHelper.SponsorLogoPath("GG")) as image:
        assert image.mode == "RGBA"

    with open("notes.txt", "w") as f:
        f.write("not an image")
    try:
        MediaHelper.SaveImageAsPng("notes.txt", MediaHelper.SponsorLogoPath("BAD"))
        raise AssertionError("expected an error")
    except OSError:
        pass
    assert not os.path.exists(MediaHelper.SponsorLogoPath("BAD"))
    assert not os.path.exists(MediaHelper.SponsorLogoPath("BAD") + ".tmp")

    assert MediaHelper.ListPngs("./user_data/sponsor_logo") == ["GG", "HD"]


def TestSponsors():
    # HD.png and GG.png exist (TestSaveImageAsPng)
    hd, gg = MediaHelper.SponsorLogoPath("HD"), MediaHelper.SponsorLogoPath("GG")
    assert SponsorHelper.ValidSponsors("hd") == (hd, [])
    # Each sponsor's logo, not only the first one's
    assert SponsorHelper.ValidSponsors("HD | GG") == (hd, [hd, gg])
    assert SponsorHelper.ValidSponsors("NONE") == (None, [])
    assert SponsorHelper.ValidSponsors("") == (None, [])

    StateManager.Set(f"{PATH}.name", "Azure")
    SponsorHelper.ExportValidSponsors("HD | GG", PATH)
    assert StateManager.Get(f"{PATH}.sponsor_logos") == {"1": hd, "2": gg}
    # A sponsor fewer leaves no stale logo behind
    SponsorHelper.ExportValidSponsors("HD | XX", PATH)
    assert StateManager.Get(f"{PATH}.sponsor_logos") == {"1": hd}
    SponsorHelper.ExportValidSponsors("", PATH)
    assert StateManager.Get(f"{PATH}.sponsor_logo") is None
    assert StateManager.Get(f"{PATH}.sponsor_logos") is None


def TestLiveRefresh():
    StateManager.Set(f"{PATH}.name", "Kestrel")
    DynamicExport.ExportPlayerMedia("Kestrel", "ZZ", PATH)
    assert StateManager.Get(f"{PATH}.avatar") is None
    assert StateManager.Get(f"{PATH}.sponsor_logo") is None

    # Added while the player is on the scoreboard
    MediaHelper.SaveImageAsPng(Image_("a.png"), MediaHelper.AvatarPath("ZZ", "Kestrel"))
    MediaHelper.SaveImageAsPng(Image_("b.png"), MediaHelper.SponsorLogoPath("ZZ"))
    DynamicExport.Refresh()
    assert StateManager.Get(f"{PATH}.avatar") == MediaHelper.AvatarPath("ZZ", "Kestrel")
    assert StateManager.Get(f"{PATH}.sponsor_logo") == MediaHelper.SponsorLogoPath("ZZ")

    MediaHelper.Remove(MediaHelper.AvatarPath("ZZ", "Kestrel"))
    MediaHelper.Remove(MediaHelper.SponsorLogoPath("ZZ"))
    DynamicExport.Refresh()
    assert StateManager.Get(f"{PATH}.avatar") is None
    assert StateManager.Get(f"{PATH}.sponsor_logo") is None


if __name__ == "__main__":
    for test in [TestPaths, TestSaveImageAsPng, TestSponsors, TestLiveRefresh]:
        test()
        print(f"{test.__name__}: OK")
