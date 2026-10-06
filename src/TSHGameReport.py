# The games of the set on a scoreboard: who won each game, on which stage,
# with which characters. The set's score is worked out from them, and they're
# what gets reported to start.gg.
#
# Teams are the scoreboard's: 1 is the left side, 2 the right side. start.gg
# slots can be the other way around when the teams were swapped on the
# scoreboard.
#
# Nothing in here depends on Qt, so it can be tested on its own.

# Game winners
DRAW = 0
UNDECIDED = None


def EmptyGame():
    return {"winner": UNDECIDED, "stage": None, "characters": {1: [], 2: []}}


class GameReport:
    def __init__(self):
        self.games = []
        self.bestOf = 0

    def Reset(self):
        self.games = [EmptyGame() for _ in range(self.bestOf)]

    def SetBestOf(self, bestOf):
        """Shows `bestOf` games, keeping the results of games already played."""
        self.bestOf = max(0, int(bestOf or 0))
        played = max(
            [i + 1 for i, g in enumerate(self.games) if g["winner"] is not UNDECIDED] + [0]
        )
        size = max(self.bestOf, played)
        while len(self.games) < size:
            self.games.append(EmptyGame())
        del self.games[size:]

    def _Ensure(self, index):
        while len(self.games) <= index:
            self.games.append(EmptyGame())
        return self.games[index]

    def SetWinner(self, index, winner):
        """1 or 2 for the team that won, DRAW, or UNDECIDED to clear it."""
        self._Ensure(index)["winner"] = winner

    def SetStage(self, index, codename):
        self._Ensure(index)["stage"] = codename or None

    def SetCharacters(self, index, team, characters):
        self._Ensure(index)["characters"][int(team)] = list(characters or [])

    def Score(self):
        wins = {1: 0, 2: 0}
        for g in self.games:
            if g["winner"] in (1, 2):
                wins[g["winner"]] += 1
        return wins[1], wins[2]

    def Wins(self, team):
        return [i for i, g in enumerate(self.games) if g["winner"] == team]

    def CurrentGameIndex(self):
        """The game being played: the first one without a result."""
        for i, g in enumerate(self.games):
            if g["winner"] is UNDECIDED:
                return i
        return len(self.games)

    def SetScore(self, team, value):
        """The score was changed outside of the games (e.g. the scoreboard's
        score): adds the team's wins to the next games, or removes its last
        ones. Returns True if the games changed."""
        value = max(0, int(value))
        changed = False
        while len(self.Wins(team)) < value:
            self.SetWinner(self.CurrentGameIndex(), team)
            changed = True
        while len(self.Wins(team)) > value:
            self.SetWinner(self.Wins(team)[-1], UNDECIDED)
            changed = True
        if changed:
            self.SetBestOf(self.bestOf)
        return changed

    def Swap(self):
        """The teams were swapped on the scoreboard."""
        for g in self.games:
            if g["winner"] in (1, 2):
                g["winner"] = 3 - g["winner"]
            g["characters"] = {1: g["characters"].get(2, []), 2: g["characters"].get(1, [])}

    def SetWinnerTeam(self):
        """Team that won the set by games, or None."""
        t1, t2 = self.Score()
        if t1 == t2:
            return None
        return 1 if t1 > t2 else 2

    def HasResults(self):
        return any(g["winner"] is not UNDECIDED for g in self.games)

    def ToDict(self):
        return {
            "bestOf": self.bestOf,
            "games": [
                {
                    "winner": g["winner"],
                    "stage": g["stage"],
                    "characters": {str(k): v for k, v in g["characters"].items()},
                }
                for g in self.games
            ],
        }

    @classmethod
    def FromDict(cls, data):
        report = cls()
        report.bestOf = int((data or {}).get("bestOf") or 0)
        for g in (data or {}).get("games") or []:
            game = EmptyGame()
            game["winner"] = g.get("winner")
            game["stage"] = g.get("stage")
            for k, v in (g.get("characters") or {}).items():
                game["characters"][int(k)] = list(v or [])
            report.games.append(game)
        return report

    def SetFromProvider(self, games, swapped=False):
        """Games already reported on start.gg, in slot order: [{"winner": slot
        (0 or 1) or None, "stage": codename, "characters": [[slot 0's], [slot
        1's]]}]."""
        self.games = []
        for i, g in enumerate(games or []):
            game = EmptyGame()
            slot = g.get("winner")
            if slot in (0, 1):
                game["winner"] = TeamOfSlot(slot, swapped)
            game["stage"] = g.get("stage")
            for s, chars in enumerate(g.get("characters") or [[], []]):
                game["characters"][TeamOfSlot(s, swapped)] = list(chars or [])
            self.games.append(game)
        self.SetBestOf(self.bestOf)


def SlotOfTeam(team, swapped):
    """start.gg slot (0 or 1) of a scoreboard team (1 or 2)."""
    slot = int(team) - 1
    return 1 - slot if swapped else slot


def TeamOfSlot(slot, swapped):
    return (1 - int(slot) if swapped else int(slot)) + 1


def BuildGameData(report, entrantIds, swapped, characterId=lambda c: None, stageId=lambda s: None):
    """The games in start.gg's BracketSetGameDataInput format. Undecided
    games and draws (start.gg can't take them) are left out."""
    gameData = []
    for i, g in enumerate(report.games):
        if g["winner"] not in (1, 2):
            continue
        game = {
            "gameNum": i + 1,
            "winnerId": str(entrantIds[SlotOfTeam(g["winner"], swapped)]),
        }
        stage = stageId(g["stage"]) if g.get("stage") else None
        if stage is not None:
            game["stageId"] = str(stage)
        selections = []
        for team in (1, 2):
            entrant = entrantIds[SlotOfTeam(team, swapped)]
            for character in g["characters"].get(team) or []:
                id = characterId(character) if character else None
                if id is not None:
                    selections.append({"entrantId": str(entrant), "characterId": int(id)})
        if selections:
            game["selections"] = selections
        gameData.append(game)
    return gameData


def SetWinnerEntrant(report, entrantIds, swapped):
    team = report.SetWinnerTeam()
    if team is None:
        return None
    return str(entrantIds[SlotOfTeam(team, swapped)])


MARK_IN_PROGRESS = """
mutation MarkSetInProgress($setId: ID!) {
  markSetInProgress(setId: $setId) { id state }
}"""

UPDATE_SET = """
mutation UpdateBracketSet($setId: ID!, $winnerId: ID, $gameData: [BracketSetGameDataInput]) {
  updateBracketSet(setId: $setId, winnerId: $winnerId, gameData: $gameData) { id state }
}"""

REPORT_SET = """
mutation ReportBracketSet($setId: ID!, $winnerId: ID, $gameData: [BracketSetGameDataInput]) {
  reportBracketSet(setId: $setId, winnerId: $winnerId, gameData: $gameData) { id state }
}"""

RESET_SET = """
mutation ResetSet($setId: ID!) {
  resetSet(setId: $setId) { id state }
}"""

CURRENT_USER = """
query CurrentUser {
  currentUser { id slug player { gamerTag } }
}"""
