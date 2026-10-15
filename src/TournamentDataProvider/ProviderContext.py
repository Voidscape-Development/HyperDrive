"""What a tournament data provider needs from the app: the loaded game (to
turn the provider's character and stage ids into the game's), the local
player database (for the "local player data" setting), and that setting.
Providers get it as provider.context: AppContext, the app's, unless they're
given another one (the tests' stand-ins)."""

from ..GameAssetManager import GameAssetManager
from ..PlayerDB import PlayerDB
from ..SettingsManager import SettingsManager


class ProviderContext:
    @property
    def games(self):
        """The loaded game: selectedGame, GetCharacterFromStartGGId,
        GetStageFromStartGGId, GetCharacterFromParryGGSlug,
        GetCharacterAssets (see GameAssetManager)"""
        raise NotImplementedError

    def UseLocalPlayerData(self) -> bool:
        """Profile fields (Twitter, pronouns, location...) come from the
        local player database instead of the provider"""
        raise NotImplementedError

    def GetSavedPlayer(self, tag) -> dict | None:
        """The player saved in the local player database under tag"""
        raise NotImplementedError

    def SavePlayers(self, players):
        """Saves players to the local player database"""
        raise NotImplementedError


class AppContext(ProviderContext):
    """The app's game, player database and settings"""

    @property
    def games(self):
        return GameAssetManager.instance

    def UseLocalPlayerData(self):
        return bool(SettingsManager.Get("general.local_player_data", False))

    def GetSavedPlayer(self, tag):
        return PlayerDB.GetPlayer(tag)

    def SavePlayers(self, players):
        PlayerDB.AddPlayers(players)
