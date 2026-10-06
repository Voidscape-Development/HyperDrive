import os
import re

from ..StateManager import StateManager
from .MediaHelper import MediaHelper


class SponsorHelper:
    def CandidatePaths(sponsor_name: str) -> list[str]:
        """The logos looked for, in order: the whole sponsor ("HD | GG"),
        then each of the sponsors in it ("HD", "GG")"""
        paths = [MediaHelper.SponsorLogoPath(sponsor_name)]
        for sponsor in re.split(r"[,/|;: <>\\?*]", sponsor_name):
            path = MediaHelper.SponsorLogoPath(sponsor)
            if sponsor and path not in paths:
                paths.append(path)
        return paths

    def ValidSponsors(sponsor_name: str) -> tuple[str | None, list[str]]:
        """(sponsor_logo, sponsor_logos) for a sponsor: the whole sponsor's
        logo and no list, or the logos of the sponsors in it, the first as
        sponsor_logo"""
        if not sponsor_name:
            return None, []
        candidates = SponsorHelper.CandidatePaths(sponsor_name)
        if os.path.exists(candidates[0]):
            return candidates[0], []
        logos = [p for p in candidates[1:] if os.path.exists(p)]
        return (logos[0] if logos else None), logos

    def ExportValidSponsors(sponsor_name: str, path: str):
        sponsor_logo, sponsor_logos = SponsorHelper.ValidSponsors(sponsor_name)

        if sponsor_logo is not None:
            StateManager.Set(f"{path}.sponsor_logo", sponsor_logo)
        else:
            StateManager.Unset(f"{path}.sponsor_logo")

        if sponsor_logos:
            StateManager.Set(
                f"{path}.sponsor_logos",
                {str(i + 1): logo for i, logo in enumerate(sponsor_logos)},
            )
        else:
            StateManager.Unset(f"{path}.sponsor_logos")
