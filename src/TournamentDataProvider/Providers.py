"""The tournament data providers HyperDrive supports, and which one an event
link is for. Adding a provider: a TournamentDataProvider subclass with its
HOST (and the rest of "What the provider is" and "What it can do" in
TournamentDataProvider.py) listed here."""

from .ParryGGDataProvider import ParryGGDataProvider
from .StartGGDataProvider import StartGGDataProvider

PROVIDERS = [StartGGDataProvider, ParryGGDataProvider]


def ProviderClassFor(url):
    """The provider class for an event link, None if no provider has it"""
    if not url:
        return None
    return next((p for p in PROVIDERS if p.HOST in url), None)
