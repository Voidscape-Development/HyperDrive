"""A player's social media accounts.

They're kept as {platform: handle}, for example
{"twitter": "beast", "twitch": "beasttv"}, under the "socials" key of a
player. "twitter" is also kept in the player's own "twitter" field, which
the layouts and the rest of the app have always used.
"""

# Platform key, label and profile URL ({} is the handle). Platforms start.gg
# links come in as the lowercase AuthorizationType (twitter, twitch,
# discord, xbox...), others are entered by hand. Keys not listed here are
# kept as well, labelled with the key.
PLATFORMS = [
    ("twitter", "Twitter", "https://x.com/{}"),
    ("bluesky", "Bluesky", "https://bsky.app/profile/{}"),
    ("twitch", "Twitch", "https://twitch.tv/{}"),
    ("youtube", "YouTube", "https://youtube.com/@{}"),
    ("instagram", "Instagram", "https://instagram.com/{}"),
    ("tiktok", "TikTok", "https://tiktok.com/@{}"),
    ("kick", "Kick", "https://kick.com/{}"),
    ("discord", "Discord", None),
    ("xbox", "Xbox", None),
    ("steam", "Steam", None),
]

PLATFORM_KEYS = [key for key, _, _ in PLATFORMS]

# Old start.gg link types that no longer point anywhere
_IGNORED_TYPES = {"mixer"}


def CleanHandle(handle):
    """The handle without surrounding spaces. A leading @ is kept, the
    layouts handle it themselves."""
    return str(handle or "").strip()


def Label(platform):
    for key, label, _ in PLATFORMS:
        if key == platform:
            return label
    return platform.capitalize()


def URL(platform, handle):
    """The profile URL of a handle, or None when the platform has none."""
    handle = CleanHandle(handle).lstrip("@")
    for key, _, url in PLATFORMS:
        if key == platform:
            return url.format(handle) if url and handle else None
    return None


def Clean(socials):
    """socials as {platform: handle}, without empty handles, with the known
    platforms first in PLATFORMS order."""
    if not isinstance(socials, dict):
        return {}
    cleaned = {}
    for platform, handle in socials.items():
        platform = str(platform or "").strip().lower()
        handle = CleanHandle(handle)
        if platform and handle:
            cleaned[platform] = handle
    ordered = {key: cleaned.pop(key) for key in PLATFORM_KEYS if key in cleaned}
    ordered.update(cleaned)
    return ordered


def FromStartGG(authorizations):
    """{platform: handle} from a start.gg user's authorizations
    ([{type, externalUsername}]). The first account of each type is kept."""
    socials = {}
    for auth in authorizations or []:
        if not isinstance(auth, dict):
            continue
        platform = str(auth.get("type") or "").lower()
        handle = CleanHandle(auth.get("externalUsername"))
        if platform and handle and platform not in _IGNORED_TYPES:
            socials.setdefault(platform, handle)
    return Clean(socials)


def Get(player):
    """A player's socials. Their twitter field, when they have one, wins
    over socials["twitter"]: it's what the player widgets and the admin
    page edit, so an emptied twitter field removes the account."""
    player = player or {}
    socials = Clean(player.get("socials"))
    if "twitter" in player:
        twitter = CleanHandle(player.get("twitter"))
        if twitter:
            socials["twitter"] = twitter
        else:
            socials.pop("twitter", None)
    return Clean(socials)


def Normalize(player):
    """Keeps player's "socials" and "twitter" in step, in place, and returns
    it."""
    if not isinstance(player, dict):
        return player
    if "socials" not in player and "twitter" not in player:
        return player
    socials = Get(player)
    player["twitter"] = socials.get("twitter", "")
    player["socials"] = socials
    return player


def Merge(base, incoming):
    """base's socials updated with incoming's, platform by platform, so an
    account only base has (one typed in by hand) is kept."""
    merged = Clean(base)
    merged.update(Clean(incoming))
    return Clean(merged)
