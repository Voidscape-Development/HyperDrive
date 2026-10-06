# The bracket widget's bracket: every format is a set of matches and the
# links between them. A match's two slots each say where their player comes
# from (a seed, the winner or loser of another match, a bye...), so the same
# code places players, works out results, names rounds and ranks players for
# every format, whether the bracket was generated here or loaded from start.gg.
#
# Nothing in here depends on Qt, so it can be tested on its own.
import math
import string

from .Helpers.LocaleHelper import LocaleHelper

# Player ids are 1-based indexes in the bracket widget's player list
BYE = -1
# Not known yet, e.g. the winner of a match that hasn't been played
PENDING = -2

TYPE_SINGLE_ELIMINATION = "SINGLE_ELIMINATION"
TYPE_DOUBLE_ELIMINATION = "DOUBLE_ELIMINATION"
TYPE_ROUND_ROBIN = "ROUND_ROBIN"
TYPE_SWISS = "SWISS"
ELIMINATION_TYPES = (TYPE_SINGLE_ELIMINATION, TYPE_DOUBLE_ELIMINATION)
POOL_TYPES = (TYPE_ROUND_ROBIN, TYPE_SWISS)
BRACKET_TYPES = ELIMINATION_TYPES + POOL_TYPES

SIDE_WINNERS = "winners"
SIDE_LOSERS = "losers"
SIDE_GRAND_FINAL = "grand_final"
SIDE_THIRD_PLACE = "third_place"
SIDE_POOL = "pool"
# Order the sides are laid out and played in
SIDES = (SIDE_WINNERS, SIDE_GRAND_FINAL, SIDE_THIRD_PLACE, SIDE_LOSERS, SIDE_POOL)

# Standings points per set result, for round robin and swiss
POINTS_WIN = 3
POINTS_DRAW = 1
POINTS_LOSS = 0


def NextPowerOf2(x):
    return 1 if x <= 1 else 2 ** math.ceil(math.log2(x))


def SeedingOrder(size):
    """Seeds in bracket position order for a bracket of `size` (a power of
    2) slots, so that 1 and 2 can only meet in the final: 1, 8, 4, 5, 2, 7..."""
    order = [1]
    while len(order) < size:
        total = len(order) * 2 + 1
        order = [s for seed in order for s in (seed, total - seed)]
    return order


def _Identifier(index):
    # A, B, ..., Z, AA, AB, ... like start.gg
    letters = string.ascii_uppercase
    result = ""
    index += 1
    while index > 0:
        index, rem = divmod(index - 1, 26)
        result = letters[rem] + result
    return result


def _IdentifierKey(identifier):
    identifier = str(identifier or "")
    return (len(identifier), identifier)


# Where a slot's player comes from
def SeedSource(seed):
    return {"type": "seed", "seed": int(seed)}


def WinnerSource(matchId):
    return {"type": "winner", "match": str(matchId)}


def LoserSource(matchId):
    return {"type": "loser", "match": str(matchId)}


def SlotSource(matchId, slot):
    # The same player as a slot of another match (grand final reset)
    return {"type": "slot", "match": str(matchId), "slot": int(slot)}


def ByeSource():
    return {"type": "bye"}


def PendingSource():
    return {"type": "pending"}


class BracketMatch:
    def __init__(self, id, side, sources=None):
        self.id = str(id)
        self.side = side
        # Round for pools; worked out from the links for elimination
        self.round = 0
        self.identifier = ""
        # Round name the provider gave it
        self.name = ""
        self.sources = list(sources or [PendingSource(), PendingSource()])
        # Players set by hand, replacing what the sources give
        self.override = [None, None]
        # -1 is a DQ
        self.score = [0, 0]
        self.finished = False
        # Winner set by hand or reported by the provider without a score
        self.winnerOverride = None
        self.providerId = None
        self.isGrandFinal = False
        self.isReset = False
        # Round the provider put it in (abs), for its column
        self.providerRound = None

        # Worked out by Bracket.Resolve
        self.players = [PENDING, PENDING]
        self.winnerSlot = None
        self.winner = PENDING
        self.loser = PENDING
        # Has a bye: it isn't played, and isn't shown
        self.isBye = False
        # Grand final reset that isn't needed
        self.notNeeded = False
        # Where its winner and loser go: (match id, slot)
        self.nextWin = None
        self.nextLose = None
        # Placement its loser gets, when losing it ends their run
        self.loserPlacement = None
        # Layout: column within its side (1-based) and row in that column
        self.column = 0
        self.row = 0

    def IsDraw(self):
        return (
            self.finished
            and self.winnerSlot is None
            and self.score[0] == self.score[1]
            and self.players[0] > 0
            and self.players[1] > 0
        )

    def ToDict(self):
        return {
            "id": self.id,
            "side": self.side,
            "round": self.round,
            "identifier": self.identifier,
            "name": self.name,
            "sources": self.sources,
            "override": self.override,
            "score": self.score,
            "finished": self.finished,
            "winnerOverride": self.winnerOverride,
            "providerId": self.providerId,
            "isGrandFinal": self.isGrandFinal,
            "isReset": self.isReset,
            "providerRound": self.providerRound,
        }

    @classmethod
    def FromDict(cls, data):
        m = cls(data.get("id"), data.get("side"), data.get("sources"))
        m.round = int(data.get("round") or 0)
        m.identifier = data.get("identifier") or ""
        m.name = data.get("name") or ""
        m.override = list(data.get("override") or [None, None])
        m.score = list(data.get("score") or [0, 0])
        m.finished = bool(data.get("finished"))
        m.winnerOverride = data.get("winnerOverride")
        m.providerId = data.get("providerId")
        m.isGrandFinal = bool(data.get("isGrandFinal"))
        m.isReset = bool(data.get("isReset"))
        m.providerRound = data.get("providerRound")
        return m


class Bracket:
    """A bracket of any type. `seeds` are the player ids of the bracket's
    seeds, best first: a player id (> 0), BYE or PENDING (e.g. a player
    coming from another bracket that isn't decided yet)."""

    def __init__(self, type=TYPE_DOUBLE_ELIMINATION, seeds=None):
        if type not in BRACKET_TYPES:
            raise ValueError(f"Unknown bracket type: {type}")
        self.type = type
        self.seeds = list(seeds or [])
        self.matches: dict[str, BracketMatch] = {}
        # Names typed in for rounds, by RoundKey
        self.roundNames = {}
        # Loaded from the provider: results come from it
        self.fromProvider = False
        # Players come out of it to another bracket instead of it having a
        # champion
        self.progressionsOut = 0
        # Swiss: how many rounds will be played
        self.totalRounds = 0
        # Round robin and swiss: players sitting out each round
        self.byes = {}
        # Provider's entrant id -> seed, to place players the provider pairs
        # after the bracket was loaded
        self.entrantIndex = {}
        # Play order, worked out by _Build
        self.order = []
        self._nextId = 1

    # Structure

    def IsPool(self):
        return self.type in POOL_TYPES

    def NewMatch(self, side, sources):
        m = BracketMatch(f"m{self._nextId}", side, sources)
        self._nextId += 1
        self.matches[m.id] = m
        return m

    def SeedCount(self):
        return len(self.seeds)

    def _Build(self):
        """Works out the links between matches, the play order and the
        layout. Called once the matches are all there."""
        for m in self.matches.values():
            m.nextWin = None
            m.nextLose = None

        for m in self.matches.values():
            for slot, source in enumerate(m.sources):
                target = self.matches.get(str(source.get("match")))
                if target is None:
                    continue
                if source.get("type") == "winner":
                    target.nextWin = (m.id, slot)
                elif source.get("type") == "loser":
                    target.nextLose = (m.id, slot)
                elif source.get("type") == "slot" and target.nextWin is None:
                    # Grand final into its reset
                    target.nextWin = (m.id, slot)

        # Play order: every match after the ones feeding it
        incoming = {id: 0 for id in self.matches}
        consumers = {id: [] for id in self.matches}
        for m in self.matches.values():
            for prereq in self._Prereqs(m):
                incoming[m.id] += 1
                consumers[prereq].append(m.id)

        ready = sorted([id for id, n in incoming.items() if n == 0], key=self._MatchSortKey)
        order = []
        while ready:
            id = ready.pop(0)
            order.append(self.matches[id])
            for c in consumers[id]:
                incoming[c] -= 1
                if incoming[c] == 0:
                    ready.append(c)
            ready.sort(key=self._MatchSortKey)

        if len(order) != len(self.matches):
            raise ValueError("Bracket has a cycle")
        self.order = order

        if self.IsPool():
            for side in (SIDE_POOL,):
                rounds = sorted({m.round for m in self.matches.values()})
                for m in self.matches.values():
                    m.column = rounds.index(m.round) + 1
                for r in rounds:
                    roundMatches = [m for m in order if m.round == r]
                    for i, m in enumerate(roundMatches):
                        m.row = i
        else:
            self._LayOut()

        self.Resolve()

    def _Prereqs(self, m):
        for source in m.sources:
            if (
                source.get("type") in ("winner", "loser", "slot")
                and str(source.get("match")) in self.matches
            ):
                yield str(source.get("match"))

    def _MatchSortKey(self, id):
        # Only breaks ties, so it doesn't depend on anything _Build works out
        m = self.matches[id]
        return (
            SIDES.index(m.side) if m.side in SIDES else 99,
            m.round if self.IsPool() else 0,
            len(id),
            id,
        )

    def _LayOut(self):
        # Column: matches come after the matches of the same side that feed
        # them. Grand finals and the third place match get their own
        # columns after the winners side.
        depth = {}
        for m in self.order:
            d = 1
            for prereq in self._Prereqs(m):
                p = self.matches[prereq]
                if p.side == m.side:
                    d = max(d, depth[prereq] + 1)
            depth[m.id] = d

        for side in SIDES:
            ids = [m.id for m in self.order if m.side == side]
            if self.fromProvider and side in (SIDE_WINNERS, SIDE_LOSERS):
                # start.gg's own rounds, so each column is one of its rounds
                # (byes can make a set's links say otherwise)
                key = {id: self.matches[id].providerRound or depth[id] for id in ids}
            else:
                key = depth
            used = sorted({key[id] for id in ids})
            for id in ids:
                self.matches[id].column = used.index(key[id]) + 1

        # Rows: walk back from the last column of each side, so the matches
        # feeding a match are next to it
        for side in SIDES:
            sideMatches = [m for m in self.order if m.side == side]
            if not sideMatches:
                continue
            columns = {}
            for m in sideMatches:
                columns.setdefault(m.column, []).append(m)
            keys = sorted(columns)

            def ByIdentifier(ms):
                return sorted(ms, key=lambda m: (_IdentifierKey(m.identifier), m.id))

            ordered = {keys[-1]: ByIdentifier(columns[keys[-1]])}
            for k in reversed(keys[:-1]):
                result = []
                seen = set()
                for consumer in ordered[k + 1] if (k + 1) in ordered else []:
                    for prereq in self._Prereqs(consumer):
                        p = self.matches[prereq]
                        if p.side == side and p.column == k and p.id not in seen:
                            seen.add(p.id)
                            result.append(p)
                result.extend(ByIdentifier([m for m in columns[k] if m.id not in seen]))
                ordered[k] = result

            for k, ms in ordered.items():
                for row, m in enumerate(ms):
                    m.row = row
            for m in sideMatches:
                m.round = m.column

    def AssignIdentifiers(self):
        """Letters in play order, like start.gg. Provider brackets keep
        their own."""
        order = sorted(
            [m for m in self.order if not m.isBye],
            key=lambda m: (
                m.column + (1000 if m.side in (SIDE_GRAND_FINAL, SIDE_THIRD_PLACE) else 0),
                0 if m.side in (SIDE_WINNERS, SIDE_POOL) else 1,
                m.row,
            ),
        )
        for i, m in enumerate(order):
            m.identifier = _Identifier(i)
        for m in self.order:
            if m.isBye:
                m.identifier = ""

    # Results

    def _SourcePlayer(self, source):
        type = source.get("type")
        if type == "seed":
            seed = int(source.get("seed") or 0)
            if 1 <= seed <= len(self.seeds):
                player = self.seeds[seed - 1]
                return player if player is not None else BYE
            return BYE
        if type == "player":
            return int(source.get("player") or PENDING)
        if type == "bye":
            return BYE
        m = self.matches.get(str(source.get("match")))
        if m is None:
            return PENDING
        if type == "winner":
            return m.winner
        if type == "loser":
            return m.loser
        if type == "slot":
            return m.players[int(source.get("slot") or 0)]
        return PENDING

    def Resolve(self):
        """Places players and works out every match's result."""
        for m in self.order:
            players = []
            for slot in range(2):
                if m.override[slot] is not None:
                    players.append(int(m.override[slot]))
                else:
                    players.append(self._SourcePlayer(m.sources[slot]))
            m.players = players
            m.notNeeded = False
            p1, p2 = players

            m.isBye = BYE in players
            m.winnerSlot = None

            if p1 == BYE and p2 == BYE:
                m.winner, m.loser = BYE, BYE
            elif p2 == BYE:
                m.winnerSlot = 0
                m.winner, m.loser = p1, BYE
            elif p1 == BYE:
                m.winnerSlot = 1
                m.winner, m.loser = p2, BYE
            else:
                if m.isReset:
                    gf = self._ResetGrandFinal(m)
                    if (
                        gf is not None
                        and gf.winnerSlot is not None
                        and gf.winnerSlot == self._WinnersSideSlot(gf)
                    ):
                        m.notNeeded = True

                winner = self.DecideWinner(m) if p1 > 0 and p2 > 0 else None
                if winner is None or m.notNeeded:
                    m.winner, m.loser = PENDING, PENDING
                else:
                    m.winnerSlot = winner
                    m.winner, m.loser = players[winner], players[1 - winner]

        if not self.IsPool():
            self._Placements()

    @staticmethod
    def DecideWinner(m):
        """0 or 1 for the slot that won, None if undecided or a draw."""
        if not m.finished:
            return None
        if m.winnerOverride in (0, 1):
            return m.winnerOverride
        s1, s2 = m.score
        # A DQ loses
        if s1 == -1 and s2 != -1:
            return 1
        if s2 == -1 and s1 != -1:
            return 0
        if s1 != s2:
            return 0 if s1 > s2 else 1
        return None

    def _ResetGrandFinal(self, m):
        for source in m.sources:
            gf = self.matches.get(str(source.get("match")))
            if gf is not None:
                return gf
        return None

    def _WinnersSideSlot(self, gf):
        """The slot of the grand final's player from the winners side."""
        for slot, source in enumerate(gf.sources):
            p = self.matches.get(str(source.get("match")))
            if p is not None and p.side == SIDE_WINNERS and source.get("type") == "winner":
                return slot
        return 0

    def MainFinal(self):
        """The match deciding the champion, or None with progressions out."""
        if self.IsPool() or self.progressionsOut > 0:
            return None
        resets = [m for m in self.matches.values() if m.isReset]
        if resets:
            return resets[0]
        candidates = [m for m in self.order if m.nextWin is None and m.side != SIDE_THIRD_PLACE]
        return candidates[-1] if len(candidates) == 1 else None

    def Champion(self):
        final = self.MainFinal()
        if final is None:
            return PENDING
        if final.isReset and final.notNeeded:
            gf = self._ResetGrandFinal(final)
            return gf.winner
        return final.winner

    def _EliminationGroups(self):
        """Matches whose loser is out, grouped by round, from the last
        round played to the first."""
        # Longest path to the end of the bracket, so later rounds come first
        distance = {}
        for m in reversed(self.order):
            d = 0
            for nxt in (m.nextWin, m.nextLose):
                if nxt is not None:
                    d = max(d, distance[nxt[0]] + 1)
            distance[m.id] = d

        groups = {}
        for m in self.order:
            if m.nextLose is not None or m.side == SIDE_THIRD_PLACE:
                continue
            if m.isGrandFinal and any(r.isReset for r in self.matches.values()):
                # Its loser goes to the reset (or comes 2nd without one)
                continue
            groups.setdefault((distance[m.id], m.side, m.column), []).append(m)

        return [
            groups[k]
            for k in sorted(
                groups, key=lambda k: (k[0], SIDES.index(k[1]) if k[1] in SIDES else 99, -k[2])
            )
        ]

    def _Placements(self):
        for m in self.matches.values():
            m.loserPlacement = None

        groups = self._EliminationGroups()
        # With progressions out, the winners of the last matches go on and
        # rank above everyone eliminated here
        ahead = self.progressionsOut if self.progressionsOut > 0 else 1

        third = [m for m in self.matches.values() if m.side == SIDE_THIRD_PLACE]
        for i, group in enumerate(groups):
            real = [m for m in group if not m.isBye]
            if i == 0 and third and self.progressionsOut <= 0:
                # Final, then 3rd and 4th from the third place match
                for m in group:
                    m.loserPlacement = ahead + 1
                ahead += len(real) + 2
                for m in third:
                    m.loserPlacement = 4
                continue
            for m in group:
                m.loserPlacement = ahead + 1
            ahead += len(real)

        # A grand final without a reset needed: its loser comes 2nd
        for m in self.matches.values():
            if m.isGrandFinal and m.loserPlacement is None:
                m.loserPlacement = 2

    def LoserPlacementOf(self, m):
        """Placement the match's loser gets if they lose their next match:
        the match's own when it knocks them out, otherwise the one of the
        match they drop to (skipping byes, which they go straight through)."""
        seen = set()
        while m is not None and m.id not in seen:
            seen.add(m.id)
            if m.nextLose is None or m.isGrandFinal:
                return m.loserPlacement
            m = self.matches.get(m.nextLose[0])
            while m is not None and m.isBye and m.id not in seen:
                seen.add(m.id)
                m = self.matches.get(m.nextWin[0]) if m.nextWin else None
        return None

    def InTopN(self, m, n):
        """For exporting only the end of the bracket: the match's loser can
        still place in the top n."""
        if n is None or n <= 0:
            return True
        if m.isGrandFinal or m.isReset:
            return True
        placement = self.LoserPlacementOf(m)
        return placement is not None and placement <= n

    def Results(self):
        """The bracket's players in finishing order, as a list of player ids
        (PENDING where not decided yet). With progressions out, the players
        going on, winners side first."""
        if self.IsPool():
            return [
                row["playerId"] if self.PoolFinished() else PENDING for row in self.GetStandings()
            ]

        if self.progressionsOut > 0:
            outs = [
                m
                for m in self.order
                if m.nextWin is None and not m.isBye and m.side != SIDE_THIRD_PLACE
            ]
            outs.sort(key=lambda m: (SIDES.index(m.side), m.row))
            return [m.winner for m in outs]

        results = []
        champion = self.Champion()
        results.append(champion)

        final = self.MainFinal()
        if final is not None:
            if final.isReset and final.notNeeded:
                results.append(self._ResetGrandFinal(final).loser)
            else:
                results.append(final.loser)

        third = [m for m in self.matches.values() if m.side == SIDE_THIRD_PLACE]
        for m in third:
            results.append(m.winner)
            results.append(m.loser)

        # Everyone else by the round they were knocked out in, then by seed
        placed = []
        for m in self.matches.values():
            if m.side == SIDE_THIRD_PLACE or m.isBye or m is final:
                continue
            if m.nextLose is not None or m.isGrandFinal or m.isReset:
                continue
            placed.append((m.loserPlacement or 9999, self.SeedOf(m.loser), m.loser))
        placed.sort()
        results.extend([p for _place, _seed, p in placed])
        return results

    def SeedOf(self, player):
        try:
            return self.seeds.index(player) + 1
        except ValueError:
            return 9999

    # Editing

    def SetScore(self, matchId, slot, value):
        self.matches[matchId].score[slot] = int(value)
        self.Resolve()

    def SetFinished(self, matchId, finished):
        self.matches[matchId].finished = bool(finished)
        self.Resolve()

    def SetWinner(self, matchId, slot):
        """Sets who won by hand (None to go by the score again)."""
        m = self.matches[matchId]
        m.winnerOverride = slot
        if slot is not None:
            m.finished = True
        self.Resolve()

    def ClearResult(self, matchId):
        m = self.matches[matchId]
        m.score = [0, 0]
        m.finished = False
        m.winnerOverride = None
        self.Resolve()

    def SetSlotPlayer(self, matchId, slot, player):
        """Puts a player in a slot by hand (None to go back to whoever the
        bracket gives it)."""
        self.matches[matchId].override[slot] = player
        self.Resolve()

    def SwapSlots(self, matchA, slotA, matchB, slotB):
        a = self.matches[matchA]
        b = self.matches[matchB]
        playerA = a.players[slotA]
        playerB = b.players[slotB]
        a.override[slotA] = playerB
        b.override[slotB] = playerA
        self.Resolve()

    def ClearOverrides(self):
        for m in self.matches.values():
            m.override = [None, None]
        self.Resolve()

    def HasOverrides(self):
        return any(o is not None for m in self.matches.values() for o in m.override)

    # Layout and names

    def Columns(self, side, includeHidden=False):
        """The side's columns, each a list of matches top to bottom. Matches
        against a bye (and columns left empty) are left out unless
        includeHidden."""
        columns = {}
        for m in self.matches.values():
            if m.side == side:
                columns.setdefault(m.column, []).append(m)
        result = []
        for k in sorted(columns):
            ms = sorted(columns[k], key=lambda m: m.row)
            if not includeHidden:
                ms = [m for m in ms if not m.isBye]
                if not ms:
                    continue
            result.append(ms)
        return result

    @staticmethod
    def RoundKey(side, column):
        return f"{side}:{column}"

    def RoundName(self, side, column):
        """Name typed in, then the provider's, then a default one."""
        typed = self.roundNames.get(Bracket.RoundKey(side, column))
        if typed:
            return typed
        for m in self.matches.values():
            if m.side == side and m.column == column and m.name:
                return m.name
        return self.DefaultRoundName(side, column)

    def DefaultRoundName(self, side, column):
        names = LocaleHelper.matchNames or {}

        def Name(key, default, *args):
            return (names.get(key) or default).format(*args)

        if side == SIDE_POOL:
            return Name("round", "Round {0}", column)
        if side == SIDE_THIRD_PLACE:
            return Name("third_place", "3rd Place Match")
        if side == SIDE_GRAND_FINAL:
            matches = [m for m in self.matches.values() if m.side == side and m.column == column]
            if any(m.isReset for m in matches):
                return Name("grand_final_reset", "Grand Final Reset")
            return Name("grand_final", "Grand Final")

        visible = [c[0].column for c in self.Columns(side)]
        if column in visible:
            number = visible.index(column) + 1
            fromEnd = len(visible) - visible.index(column)
        else:
            number = column
            fromEnd = None

        if self.progressionsOut > 0:
            fromEnd = None

        if side == SIDE_WINNERS and self.type == TYPE_SINGLE_ELIMINATION:
            if fromEnd == 1:
                return Name("single_elim_final", "Final")
            if fromEnd == 2:
                return Name("single_elim_semi_final", "Semi-Final")
            if fromEnd == 3:
                return Name("single_elim_quarter_final", "Quarter-Final")
            return Name("round", "Round {0}", number)
        if side == SIDE_WINNERS:
            if fromEnd == 1:
                return Name("winners_final", "Winners Final")
            if fromEnd == 2:
                return Name("winners_semi_final", "Winners Semi-Final")
            if fromEnd == 3:
                return Name("winners_quarter_final", "Winners Quarter-Final")
            return Name("winners_round", "Winners Round {0}", number)
        if side == SIDE_LOSERS:
            if fromEnd == 1:
                return Name("losers_final", "Losers Final")
            if fromEnd == 2:
                return Name("losers_semi_final", "Losers Semi-Final")
            if fromEnd == 3:
                return Name("losers_quarter_final", "Losers Quarter-Final")
            return Name("losers_round", "Losers Round {0}", number)
        return Name("round", "Round {0}", column)

    # Round robin and swiss

    def PoolRounds(self):
        return sorted({m.round for m in self.matches.values()})

    def PoolMatchWinner(self, m):
        """0 or 1 for the slot that won, "draw", or None if undecided."""
        p1, p2 = m.players
        if p1 <= 0 or p2 <= 0 or not m.finished:
            return None
        winner = Bracket.DecideWinner(m)
        if winner is not None:
            return winner
        return "draw"

    def PoolFinished(self):
        if not self.matches:
            return False
        if self.type == TYPE_SWISS and len(self.PoolRounds()) < self.totalRounds:
            return False
        return all(self.PoolMatchWinner(m) is not None for m in self.matches.values())

    def _PoolRoundFinished(self, round):
        return all(
            self.PoolMatchWinner(m) is not None for m in self.matches.values() if m.round == round
        )

    def GetStandings(self):
        """The players ranked, best first. Each row: {rank, playerId, played,
        wins, draws, losses, points, gameWins, gameLosses, gameDiff,
        buchholz, byes}"""
        players = [p for p in self.seeds if p is not None and p > 0]
        rows = {
            p: {
                "playerId": p,
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "points": 0,
                "gameWins": 0,
                "gameLosses": 0,
                "gameDiff": 0,
                "buchholz": 0,
                "byes": 0,
            }
            for p in players
        }
        opponents = {p: [] for p in rows}
        results = []

        for m in self.matches.values():
            winner = self.PoolMatchWinner(m)
            if winner is None:
                continue
            p1, p2 = m.players
            if p1 not in rows or p2 not in rows:
                continue
            opponents[p1].append(p2)
            opponents[p2].append(p1)
            for slot, p in enumerate((p1, p2)):
                row = rows[p]
                row["played"] += 1
                row["gameWins"] += max(m.score[slot], 0)
                row["gameLosses"] += max(m.score[1 - slot], 0)
                if winner == "draw":
                    row["draws"] += 1
                elif winner == slot:
                    row["wins"] += 1
                else:
                    row["losses"] += 1
            if winner != "draw":
                results.append(((p1, p2)[winner], (p1, p2)[1 - winner]))

        # A bye counts as a win in swiss, so the player isn't penalized for it
        if self.type == TYPE_SWISS:
            for round, byes in self.byes.items():
                for p in byes:
                    if p in rows and self._PoolRoundFinished(int(round)):
                        rows[p]["byes"] += 1
                        rows[p]["wins"] += 1

        for row in rows.values():
            row["points"] = (
                row["wins"] * POINTS_WIN + row["draws"] * POINTS_DRAW + row["losses"] * POINTS_LOSS
            )
            row["gameDiff"] = row["gameWins"] - row["gameLosses"]

        for p, row in rows.items():
            row["buchholz"] = sum(rows[o]["points"] for o in opponents[p])

        def HeadToHead(p, tied):
            return sum(1 for w, l in results if w == p and l in tied)

        def Key(row):
            seed = self.SeedOf(row["playerId"])
            if self.type == TYPE_SWISS:
                return (-row["points"], -row["buchholz"], -row["gameDiff"], -row["gameWins"], seed)
            return (-row["points"], -row["gameDiff"], -row["gameWins"], seed)

        ranked = sorted(rows.values(), key=Key)

        # Round robin: players tied on points are split by the sets they
        # played against each other first
        if self.type == TYPE_ROUND_ROBIN:
            grouped = []
            for row in ranked:
                if grouped and grouped[-1][0]["points"] == row["points"]:
                    grouped[-1].append(row)
                else:
                    grouped.append([row])
            ranked = []
            for group in grouped:
                tied = {r["playerId"] for r in group}
                group.sort(key=lambda r: (-HeadToHead(r["playerId"], tied),) + Key(r))
                ranked.extend(group)

        keys = ["points", "gameDiff", "gameWins"]
        if self.type == TYPE_SWISS:
            keys.append("buchholz")
        for i, row in enumerate(ranked):
            if (
                i > 0
                and all(ranked[i - 1][k] == row[k] for k in keys)
                and ranked[i - 1]["played"] == row["played"]
            ):
                row["rank"] = ranked[i - 1]["rank"]
            else:
                row["rank"] = i + 1

        return ranked

    def PoolOpponents(self):
        played = set()
        for m in self.matches.values():
            p1, p2 = m.players
            if p1 > 0 and p2 > 0:
                played.add(frozenset((p1, p2)))
        return played

    def CanPairNextRound(self):
        """Swiss only: there are rounds left and the last one is done."""
        if self.type != TYPE_SWISS or self.fromProvider:
            return False
        rounds = self.PoolRounds()
        last = rounds[-1] if rounds else 0
        if last >= self.totalRounds:
            return False
        return last == 0 or self._PoolRoundFinished(last)

    def _AddPoolRound(self, round, pairs, bye=None):
        for p1, p2 in pairs:
            m = self.NewMatch(
                SIDE_POOL, [{"type": "player", "player": p1}, {"type": "player", "player": p2}]
            )
            m.round = round
        self.byes[str(round)] = [bye] if bye else []

    def PairNextRound(self):
        """Swiss: pairs the next round from the standings so far. Players are
        matched with someone on the same score where possible, never with
        someone they already played unless there's no other way."""
        if self.type != TYPE_SWISS:
            return False
        rounds = self.PoolRounds()
        round = (rounds[-1] if rounds else 0) + 1
        players = [p for p in self.seeds if p is not None and p > 0]

        if round == 1:
            # Top half against bottom half by seed: 1 v n/2+1, 2 v n/2+2...
            bye = None
            if len(players) % 2 == 1:
                bye = players.pop()
            half = len(players) // 2
            self._AddPoolRound(round, [(players[i], players[i + half]) for i in range(half)], bye)
        else:
            order = [row["playerId"] for row in self.GetStandings()]
            bye = None
            if len(order) % 2 == 1:
                hadBye = {p for byes in self.byes.values() for p in byes}
                bye = next((p for p in reversed(order) if p not in hadBye), order[-1])
                order.remove(bye)
            pairs = _PairAvoidingRematches(order, self.PoolOpponents())
            if pairs is None:
                pairs = [(order[i], order[i + 1]) for i in range(0, len(order), 2)]
            self._AddPoolRound(round, pairs, bye)

        self._Build()
        self.AssignIdentifiers()
        return True

    def UnpairLastRound(self):
        """Swiss: removes the last round so it can be paired again, unless
        it's the only one."""
        if self.type != TYPE_SWISS or self.fromProvider:
            return False
        rounds = self.PoolRounds()
        if len(rounds) <= 1:
            return False
        last = rounds[-1]
        for id in [id for id, m in self.matches.items() if m.round == last]:
            del self.matches[id]
        self.byes.pop(str(last), None)
        self.roundNames.pop(Bracket.RoundKey(SIDE_POOL, len(rounds)), None)
        self._Build()
        return True

    # Saving

    def ToDict(self):
        return {
            "type": self.type,
            "seeds": self.seeds,
            "matches": [m.ToDict() for m in self.matches.values()],
            "roundNames": self.roundNames,
            "fromProvider": self.fromProvider,
            "progressionsOut": self.progressionsOut,
            "totalRounds": self.totalRounds,
            "byes": self.byes,
            "nextId": self._nextId,
        }

    @classmethod
    def FromDict(cls, data):
        bracket = cls(data.get("type", TYPE_DOUBLE_ELIMINATION), data.get("seeds"))
        for md in data.get("matches") or []:
            m = BracketMatch.FromDict(md)
            bracket.matches[m.id] = m
        bracket.roundNames = dict(data.get("roundNames") or {})
        bracket.fromProvider = bool(data.get("fromProvider"))
        bracket.progressionsOut = int(data.get("progressionsOut") or 0)
        bracket.totalRounds = int(data.get("totalRounds") or 0)
        bracket.byes = dict(data.get("byes") or {})
        bracket._nextId = int(data.get("nextId") or len(bracket.matches) + 1)
        bracket._Build()
        return bracket


def _PairAvoidingRematches(order, played, maxSteps=20000):
    """Pairs players in standings order, each with the next best player they
    haven't played. Backtracks when that leaves someone with nobody to play.
    Returns None if there's no way to avoid a rematch (or it takes too long
    to find one)."""
    steps = [0]

    def Pair(remaining):
        if not remaining:
            return []
        steps[0] += 1
        if steps[0] > maxSteps:
            return None
        first = remaining[0]
        for i in range(1, len(remaining)):
            other = remaining[i]
            if frozenset((first, other)) in played:
                continue
            rest = Pair(remaining[1:i] + remaining[i + 1 :])
            if rest is not None:
                return [(first, other)] + rest
        return None

    return Pair(list(order))


def RoundRobinSchedule(playerCount):
    """All play all with the circle method: player 1 stays in place and the
    rest rotate, so everyone plays once per round. Returns a list of rounds,
    each a list of (a, b) with 1-based seeds, and the seed with the bye each
    round (None when the number of players is even)."""
    players = list(range(1, playerCount + 1))
    if playerCount % 2 == 1:
        players.append(None)
    n = len(players)

    rounds = []
    byes = []
    for r in range(n - 1):
        pairs = []
        bye = None
        for i in range(n // 2):
            a, b = players[i], players[n - 1 - i]
            if a is None or b is None:
                bye = a if b is None else b
                continue
            if i == 0 and r % 2 == 1:
                a, b = b, a
            pairs.append((a, b))
        pairs.sort(key=lambda p: min(p))
        rounds.append(pairs)
        byes.append(bye)
        players = [players[0]] + [players[-1]] + players[1:-1]

    return rounds, byes


# Generators


def GenerateBracket(
    type,
    seeds,
    grandFinalReset=True,
    thirdPlace=False,
    progressionsOut=0,
    losersSeeds=None,
    swissRounds=None,
):
    """Builds a new bracket for `seeds` (player ids, best first).

    Elimination brackets take any number of players: the bracket is the next
    power of 2 in size, and the missing seeds are byes that aren't shown.

    progressionsOut: how many players go on to another bracket instead of
    playing to a champion. For double elimination, half of them come from
    each side.

    losersSeeds: double elimination only, players starting on the losers
    side (e.g. from pools where they lost), best first.
    """
    seeds = list(seeds or [])
    if type == TYPE_SINGLE_ELIMINATION:
        return _GenerateSingle(seeds, thirdPlace, progressionsOut)
    if type == TYPE_DOUBLE_ELIMINATION:
        return _GenerateDouble(seeds, grandFinalReset, progressionsOut, losersSeeds or [])
    if type == TYPE_ROUND_ROBIN:
        bracket = Bracket(type, seeds)
        players = [p for p in seeds]
        schedule, byes = RoundRobinSchedule(len(players))
        for r, pairs in enumerate(schedule):
            for a, b in pairs:
                m = bracket.NewMatch(SIDE_POOL, [SeedSource(a), SeedSource(b)])
                m.round = r + 1
            bracket.byes[str(r + 1)] = [players[byes[r] - 1]] if byes[r] else []
        bracket.totalRounds = len(schedule)
        bracket._Build()
        bracket.AssignIdentifiers()
        return bracket
    if type == TYPE_SWISS:
        bracket = Bracket(type, seeds)
        bracket.totalRounds = swissRounds or SwissRoundsFor(len(seeds))
        bracket._Build()
        bracket.PairNextRound()
        return bracket
    raise ValueError(f"Unknown bracket type: {type}")


def SwissRoundsFor(playerCount):
    # Enough rounds for a single undefeated player
    return max(1, math.ceil(math.log2(max(playerCount, 2))))


def _FirstRound(bracket, side, size, sourceFor):
    """Pairs `size` (a power of 2) bracket positions by seeding order."""
    order = SeedingOrder(size)
    matches = []
    for j in range(size // 2):
        matches.append(
            bracket.NewMatch(side, [sourceFor(order[2 * j]), sourceFor(order[2 * j + 1])])
        )
    return matches


def _ValidProgressions(progressionsOut, size, double):
    if progressionsOut <= 0:
        return 0
    if double:
        perSide = NextPowerOf2(max(1, progressionsOut // 2))
        return min(perSide, size // 2) * 2
    return min(NextPowerOf2(progressionsOut), size // 2)


def _GenerateSingle(seeds, thirdPlace, progressionsOut):
    bracket = Bracket(TYPE_SINGLE_ELIMINATION, seeds)
    size = max(2, NextPowerOf2(len(seeds)))
    progressionsOut = _ValidProgressions(progressionsOut, size, False)
    bracket.progressionsOut = progressionsOut

    round = _FirstRound(
        bracket, SIDE_WINNERS, size, lambda s: SeedSource(s) if s <= len(seeds) else ByeSource()
    )
    semis = None
    while len(round) > 1 and (progressionsOut <= 0 or len(round) > progressionsOut):
        if len(round) == 2:
            semis = round
        round = [
            bracket.NewMatch(
                SIDE_WINNERS, [WinnerSource(round[2 * j].id), WinnerSource(round[2 * j + 1].id)]
            )
            for j in range(len(round) // 2)
        ]

    if thirdPlace and progressionsOut <= 0 and semis is not None:
        bracket.NewMatch(SIDE_THIRD_PLACE, [LoserSource(semis[0].id), LoserSource(semis[1].id)])

    bracket._Build()
    bracket.AssignIdentifiers()
    return bracket


def _GenerateDouble(seeds, grandFinalReset, progressionsOut, losersSeeds):
    bracket = Bracket(TYPE_DOUBLE_ELIMINATION, list(seeds) + list(losersSeeds))
    winnersCount = len(seeds)
    size = max(2, NextPowerOf2(max(winnersCount, len(losersSeeds))))
    progressionsOut = _ValidProgressions(progressionsOut, size, True)
    bracket.progressionsOut = progressionsOut
    perSide = progressionsOut // 2

    # Winners side, round by round
    winners = [
        _FirstRound(
            bracket,
            SIDE_WINNERS,
            size,
            lambda s: SeedSource(s) if s <= winnersCount else ByeSource(),
        )
    ]
    while len(winners[-1]) > 1 and (perSide <= 0 or len(winners[-1]) > perSide):
        last = winners[-1]
        winners.append(
            [
                bracket.NewMatch(
                    SIDE_WINNERS, [WinnerSource(last[2 * j].id), WinnerSource(last[2 * j + 1].id)]
                )
                for j in range(len(last) // 2)
            ]
        )

    def Pair(survivors):
        return Track(
            [
                bracket.NewMatch(SIDE_LOSERS, [survivors[2 * j], survivors[2 * j + 1]])
                for j in range(len(survivors) // 2)
            ]
        )

    def Winners(matches):
        return [WinnerSource(m.id) for m in matches]

    # Seeds that can end up in each match, to keep players apart on the
    # losers side from the players they may have already played. On the
    # losers side, each seed is weighted by the winners round it dropped
    # from: players who dropped later are more likely to still be there.
    possible = {}

    def Possible(source):
        type = source.get("type")
        if type == "seed":
            return {source["seed"]: 1}
        if type in ("winner", "loser"):
            return possible.get(source["match"], {})
        return {}

    def Track(matches, dropRound=None):
        for m in matches:
            merged = {}
            for src in m.sources:
                weights = Possible(src)
                if src.get("type") == "loser" and dropRound is not None:
                    weights = {seed: dropRound for seed in weights}
                for seed, w in weights.items():
                    merged[seed] = max(merged.get(seed, 0), w)
            possible[m.id] = merged
        return matches

    for round in winners:
        Track(round)

    def DropOrder(dropped, survivors):
        """The order to drop the winners side's losers in, facing the
        survivors they're least likely to have played already."""
        n = len(dropped)
        if n <= 1 or n != len(survivors):
            return dropped
        candidates = []
        for mask in range(n):
            permuted = [dropped[j ^ mask] for j in range(n)]
            candidates.append(list(reversed(permuted)))
            candidates.append(permuted)

        def Cost(order):
            total = 0
            for j in range(n):
                theirs = Possible(survivors[j])
                for seed in Possible(order[j]):
                    if seed in theirs:
                        total += 16 ** theirs[seed]
            return total

        return min(candidates, key=Cost)

    # Losers side: players still in it, waiting for their next match
    if losersSeeds:
        offset = winnersCount
        survivors = Winners(
            Track(
                _FirstRound(
                    bracket,
                    SIDE_LOSERS,
                    size,
                    lambda s: SeedSource(offset + s) if s <= len(losersSeeds) else ByeSource(),
                )
            )
        )
        drops = winners
    else:
        survivors = [LoserSource(m.id) for m in winners[0]]
        drops = winners[1:]
        if len(survivors) >= 2:
            survivors = Winners(Track(Pair(survivors), dropRound=1))

    for round in drops:
        dropRound = winners.index(round) + 1
        dropped = [LoserSource(m.id) for m in round]
        while len(survivors) > len(dropped):
            survivors = Winners(Pair(survivors))
        if not survivors:
            survivors = dropped
            continue
        dropped = DropOrder(dropped, survivors)
        survivors = Winners(
            Track(
                [
                    bracket.NewMatch(SIDE_LOSERS, [dropped[j], survivors[j]])
                    for j in range(len(dropped))
                ],
                dropRound=dropRound,
            )
        )

    if progressionsOut <= 0:
        winnersFinal = winners[-1][0]
        losersChampion = survivors[0] if survivors else LoserSource(winnersFinal.id)
        gf = bracket.NewMatch(SIDE_GRAND_FINAL, [WinnerSource(winnersFinal.id), losersChampion])
        gf.isGrandFinal = True
        if grandFinalReset:
            reset = bracket.NewMatch(SIDE_GRAND_FINAL, [SlotSource(gf.id, 0), SlotSource(gf.id, 1)])
            reset.isReset = True

    bracket._Build()
    bracket.AssignIdentifiers()
    return bracket


def FromProviderSets(type, sets, seedCount, entrantIds=None, progressionsOut=0):
    """Builds the bracket from the provider's sets:

    [{"id", "round" (> 0 winners, < 0 losers), "identifier", "name",
      "score": [a, b], "finished", "winnerSlot",
      "slots": [{"prereqType": "seed"|"set"|"bye"|..., "prereqId",
                 "placement": 1 (winner)|2 (loser), "player": 1-based seed,
                 "entrantId"}]}]
    """
    sets = list(sets or [])
    if not sets:
        raise ValueError("The bracket has no sets")

    if type not in BRACKET_TYPES:
        type = TYPE_DOUBLE_ELIMINATION
    bracket = Bracket(type, list(range(1, seedCount + 1)))
    bracket.fromProvider = True
    # Players going on to another phase group: no champion
    bracket.progressionsOut = int(progressionsOut or 0) if type in ELIMINATION_TYPES else 0
    entrantIndex = {str(id): i + 1 for i, id in enumerate(entrantIds or []) if id is not None}
    bracket.entrantIndex = entrantIndex

    byId = {str(s.get("id")): s for s in sets}

    def SlotSourceFor(slot):
        prereqId = slot.get("prereqId")
        player = slot.get("player")
        if not player and slot.get("entrantId") is not None:
            player = entrantIndex.get(str(slot.get("entrantId")))
        if slot.get("prereqType") == "set" and prereqId is not None and str(prereqId) in byId:
            if (slot.get("placement") or 1) == 2:
                return LoserSource(f"p{prereqId}")
            return WinnerSource(f"p{prereqId}")
        if player:
            return SeedSource(int(player))
        if slot.get("prereqType") == "bye":
            return ByeSource()
        if slot.get("prereqType") == "set":
            # Winner of a set we don't have (or a pool slot not paired yet)
            # is still to be decided; its loser never comes here
            if (slot.get("placement") or 1) == 2 and type in ELIMINATION_TYPES:
                return ByeSource()
            return PendingSource()
        return ByeSource() if type in ELIMINATION_TYPES else PendingSource()

    for s in sets:
        round = int(s.get("round") or 0)
        if round == 0:
            raise ValueError(f"Set {s.get('id')} has no round")
        if type in POOL_TYPES:
            side = SIDE_POOL
        else:
            side = SIDE_WINNERS if round > 0 else SIDE_LOSERS
        slots = list(s.get("slots") or [])[:2]
        slots += [{}] * (2 - len(slots))
        m = BracketMatch(f"p{s.get('id')}", side, [SlotSourceFor(slot) for slot in slots])
        m.round = abs(round)
        m.providerRound = abs(round)
        m.identifier = s.get("identifier") or ""
        m.name = s.get("name") or ""
        m.providerId = str(s.get("id"))
        _ApplyProviderResult(m, s)
        bracket.matches[m.id] = m

    if type in POOL_TYPES:
        # Sets against a bye only say who sits out
        for id in list(bracket.matches):
            m = bracket.matches[id]
            if any(src.get("type") == "bye" for src in m.sources):
                for src in m.sources:
                    if src.get("type") == "seed":
                        bracket.byes.setdefault(str(m.round), []).append(int(src.get("seed")))
                del bracket.matches[id]
        rounds = sorted({m.round for m in bracket.matches.values()})
        for m in bracket.matches.values():
            m.round = rounds.index(m.round) + 1
        bracket.byes = {
            str(rounds.index(int(r)) + 1): v for r, v in bracket.byes.items() if int(r) in rounds
        }
        bracket.totalRounds = len(rounds)
    else:
        _MarkGrandFinals(bracket)

    bracket._Build()
    return bracket


def _ApplyProviderResult(m, s):
    score = list(s.get("score") or [None, None])[:2]
    score += [None] * (2 - len(score))
    m.score = [v if v is not None else 0 for v in score]
    m.finished = bool(s.get("finished"))
    m.winnerOverride = s.get("winnerSlot") if s.get("winnerSlot") in (0, 1) else None


def _MarkGrandFinals(bracket):
    """start.gg puts grand finals in the winners side's last round: the grand
    final is the winners side match fed by the losers side, and its reset
    the match fed only by the grand final."""
    matches = bracket.matches
    for m in matches.values():
        if m.side != SIDE_WINNERS:
            continue
        sides = {matches[src["match"]].side for src in m.sources if src.get("match") in matches}
        if SIDE_LOSERS in sides:
            m.isGrandFinal = True
            m.side = SIDE_GRAND_FINAL
    for m in matches.values():
        prereqs = {src.get("match") for src in m.sources if src.get("match") in matches}
        if (
            len(prereqs) == 1
            and matches[next(iter(prereqs))].isGrandFinal
            and all(src.get("type") in ("winner", "loser") for src in m.sources)
        ):
            m.isReset = True
            m.side = SIDE_GRAND_FINAL
            # Keep each player on the side they were on in the grand final
            gf = next(iter(prereqs))
            m.sources = [SlotSource(gf, 0), SlotSource(gf, 1)]
    # Single elimination third place match: both players lost a semi final
    for m in matches.values():
        if (
            m.side == SIDE_WINNERS
            and bracket.type == TYPE_SINGLE_ELIMINATION
            and all(src.get("type") == "loser" for src in m.sources)
        ):
            m.side = SIDE_THIRD_PLACE


def ApplyProviderUpdate(bracket, sets):
    """Refreshes results from the provider. Returns False if the provider
    has sets the bracket doesn't (it changed, so it has to be loaded again)."""
    byProvider = {m.providerId: m for m in bracket.matches.values() if m.providerId}
    entrantIndex = getattr(bracket, "entrantIndex", {})
    for s in sets or []:
        id = str(s.get("id"))
        m = byProvider.get(id)
        if m is None:
            if bracket.IsPool() and any(
                slot.get("prereqType") == "bye" for slot in s.get("slots") or []
            ):
                continue
            return False
        _ApplyProviderResult(m, s)
        if bracket.IsPool():
            # Swiss rounds get their players after the pool was loaded
            for slot, data in enumerate(list(s.get("slots") or [])[:2]):
                player = data.get("player") or entrantIndex.get(str(data.get("entrantId")))
                if player:
                    m.sources[slot] = SeedSource(int(player))
    bracket.Resolve()
    return True


class BracketPhase:
    """One bracket of the tournament built in the bracket widget, e.g. pools
    or the top cut. Its seeds can be players or results of another phase."""

    def __init__(self, id, name="", type=TYPE_DOUBLE_ELIMINATION):
        self.id = str(id)
        self.name = name
        self.type = type
        # One per seed, best first: {"type": "player", "player": id},
        # {"type": "result", "phase": id, "place": n} or None for a bye.
        # Double elimination: seeds starting on the losers side come after
        # the winners side's, see losersSeedCount.
        self.seedSources = []
        self.losersSeedCount = 0
        self.grandFinalReset = True
        self.thirdPlace = False
        self.progressionsOut = 0
        self.swissRounds = 0
        self.bracket: Bracket = None
        # The provider's phase group this was loaded from
        self.providerPhaseGroupId = None

    def WinnersSeedCount(self):
        return len(self.seedSources) - self.losersSeedCount

    def Generate(self, seeds):
        """A new bracket for these seed player ids, losing its results."""
        winners = seeds[: self.WinnersSeedCount()]
        losers = seeds[self.WinnersSeedCount() :] if self.type == TYPE_DOUBLE_ELIMINATION else []
        if self.type != TYPE_DOUBLE_ELIMINATION:
            winners = seeds
        self.bracket = GenerateBracket(
            self.type,
            winners,
            grandFinalReset=self.grandFinalReset,
            thirdPlace=self.thirdPlace,
            progressionsOut=self.progressionsOut,
            losersSeeds=losers,
            swissRounds=self.swissRounds or None,
        )

    def ToDict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "seedSources": self.seedSources,
            "losersSeedCount": self.losersSeedCount,
            "grandFinalReset": self.grandFinalReset,
            "thirdPlace": self.thirdPlace,
            "progressionsOut": self.progressionsOut,
            "swissRounds": self.swissRounds,
            "bracket": self.bracket.ToDict() if self.bracket else None,
            "providerPhaseGroupId": self.providerPhaseGroupId,
        }

    @classmethod
    def FromDict(cls, data):
        phase = cls(
            data.get("id"), data.get("name") or "", data.get("type") or TYPE_DOUBLE_ELIMINATION
        )
        phase.seedSources = list(data.get("seedSources") or [])
        phase.losersSeedCount = int(data.get("losersSeedCount") or 0)
        phase.grandFinalReset = bool(data.get("grandFinalReset", True))
        phase.thirdPlace = bool(data.get("thirdPlace"))
        phase.progressionsOut = int(data.get("progressionsOut") or 0)
        phase.swissRounds = int(data.get("swissRounds") or 0)
        phase.providerPhaseGroupId = data.get("providerPhaseGroupId")
        if data.get("bracket"):
            phase.bracket = Bracket.FromDict(data["bracket"])
        return phase


class BracketTournament:
    """The phases of a tournament built in the bracket widget, linked by
    their seeds: the top cut can take the pools' top players."""

    def __init__(self):
        self.phases: list[BracketPhase] = []
        self._nextId = 1

    def NewPhaseId(self):
        id = f"phase{self._nextId}"
        self._nextId += 1
        return id

    def GetPhase(self, id):
        return next((p for p in self.phases if p.id == str(id)), None)

    def AddPhase(self, phase):
        self.phases.append(phase)

    def RemovePhase(self, id):
        self.phases = [p for p in self.phases if p.id != str(id)]
        # Seeds taken from it are left empty
        for p in self.phases:
            p.seedSources = [
                None
                if (s or {}).get("type") == "result" and (s or {}).get("phase") == str(id)
                else s
                for s in p.seedSources
            ]

    def DependsOn(self, phase, other):
        """The phase takes seeds from `other`, directly or not."""
        seen = set()
        stack = [phase]
        while stack:
            p = stack.pop()
            for s in p.seedSources:
                if (s or {}).get("type") != "result":
                    continue
                source = self.GetPhase(s.get("phase"))
                if source is None or source.id in seen:
                    continue
                if source.id == other.id:
                    return True
                seen.add(source.id)
                stack.append(source)
        return False

    def _PhaseOrder(self):
        order = []
        visiting = set()

        def Visit(p):
            if p in order or p.id in visiting:
                return
            visiting.add(p.id)
            for s in p.seedSources:
                if (s or {}).get("type") == "result":
                    source = self.GetPhase(s.get("phase"))
                    if source is not None:
                        Visit(source)
            visiting.discard(p.id)
            order.append(p)

        for p in self.phases:
            Visit(p)
        return order

    def SeedPlayers(self, phase):
        """The player ids of the phase's seeds, from its seed sources."""
        players = []
        for s in phase.seedSources:
            s = s or {}
            if s.get("type") == "player":
                players.append(int(s.get("player")))
            elif s.get("type") == "result":
                source = self.GetPhase(s.get("phase"))
                place = int(s.get("place") or 0)
                if source is None or source.bracket is None:
                    players.append(PENDING)
                    continue
                results = source.bracket.Results()
                players.append(results[place - 1] if 1 <= place <= len(results) else PENDING)
            else:
                players.append(BYE)
        return players

    def Resolve(self):
        """Fills in every phase's seeds from the phases they come from."""
        for phase in self._PhaseOrder():
            if phase.bracket is None or phase.bracket.fromProvider:
                continue
            seeds = self.SeedPlayers(phase)
            if phase.bracket.seeds != seeds:
                phase.bracket.seeds = seeds
                phase.bracket.Resolve()

    def ToDict(self):
        return {
            "phases": [p.ToDict() for p in self.phases],
            "nextId": self._nextId,
        }

    @classmethod
    def FromDict(cls, data):
        tournament = cls()
        for pd in (data or {}).get("phases") or []:
            try:
                tournament.phases.append(BracketPhase.FromDict(pd))
            except Exception:
                continue
        tournament._nextId = int((data or {}).get("nextId") or len(tournament.phases) + 1)
        tournament.Resolve()
        return tournament


def SnakeSeeding(phaseIds, perPhase):
    """Seed sources taking the top `perPhase` of each phase, in snake order
    (1st of A, 1st of B, 2nd of B, 2nd of A...), so players from the same
    pool are spread out."""
    sources = []
    for place in range(1, perPhase + 1):
        ids = list(phaseIds) if place % 2 == 1 else list(reversed(phaseIds))
        for id in ids:
            sources.append({"type": "result", "phase": str(id), "place": place})
    return sources
