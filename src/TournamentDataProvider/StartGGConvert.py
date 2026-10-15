"""Turns start.gg's answers into HyperDrive's data, for StartGGDataProvider:
round names, players (ProcessEntrantData), a set's games and the older
API's set data, the bracket's sets and slots. Plain functions: what they
need of the loaded game comes as gameAssets (provider.context.games)."""

import traceback
from collections import Counter

from loguru import logger

from ..Helpers import SocialsHelper
from ..Helpers.CountryHelper import CountryHelper
from ..Helpers.DictHelper import deep_get
from ..Helpers.LocaleHelper import LocaleHelper
from .ProviderContext import AppContext


def LeagueSlug(link):
    """ "tournament/<slug>" from a league's start.gg link (any of its pages)
    or slug."""
    parts = [p for p in link.split("start.gg/")[-1].split("?")[0].split("/") if p]
    if parts and parts[0] in ("tournament", "league"):
        parts = parts[1:]
    return f"tournament/{parts[0]}" if parts else ""


def ImageUrl(images, imageType):
    """URL of the first image of that type ("profile", "banner"), or ""."""
    return next(
        (i.get("url") for i in images or [] if i and i.get("type") == imageType and i.get("url")),
        "",
    )


def TranslateRoundName(name: str):
    if name == None:
        return ""

    roundMapping = {
        "Grand Final Reset": "grand_final_reset",
        "Grand Final": "grand_final",
        "Winners Final": "winners_final",
        "Winners Semi-Final": "winners_semi_final",
        "Winners Quarter-Final": "winners_quarter_final",
        "Losers Final": "losers_final",
        "Losers Semi-Final": "losers_semi_final",
        "Losers Quarter-Final": "losers_quarter_final",
        "Final": "single_elim_final",
        "Semi-Final": "single_elim_semi_final",
        "Quarter-Final": "single_elim_quarter_final",
    }

    if name in roundMapping and LocaleHelper.matchNames.get(roundMapping.get(name)):
        return LocaleHelper.matchNames.get(roundMapping.get(name))

    try:
        roundNumber = name.rsplit(" ")[-1]

        if "Winners" in name:
            return LocaleHelper.matchNames.get("winners_round").format(roundNumber)
        elif "Losers" in name:
            return LocaleHelper.matchNames.get("losers_round").format(roundNumber)
        elif name.startswith("Round "):
            return LocaleHelper.matchNames.get("round").format(roundNumber)
    except:
        logger.error(traceback.format_exc())

    return name


def ParseSetGames(_set, entrantIds, gameAssets=None):
    """The set's games reported on start.gg, in slot order: [{"winner":
    slot or None, "stage": codename, "characters": [[slot 0's], [slot
    1's]]}]."""
    gameAssets = gameAssets if gameAssets is not None else AppContext().games
    games = []
    for game in sorted(_set.get("games") or [], key=lambda g: g.get("orderNum") or 0):
        winner = None
        if game.get("winnerId") is not None and str(game.get("winnerId")) in entrantIds:
            winner = entrantIds.index(str(game.get("winnerId")))

        stage = None
        if deep_get(game, "stage.id") is not None:
            found = gameAssets.GetStageFromStartGGId(deep_get(game, "stage.id"))
            if found:
                stage = found[1].get("codename")

        characters = [[], []]
        for selection in game.get("selections") or []:
            entrantId = str(deep_get(selection, "entrant.id"))
            if entrantId not in entrantIds or selection.get("selectionValue") is None:
                continue
            character = gameAssets.GetCharacterFromStartGGId(selection.get("selectionValue"))
            if character:
                characters[entrantIds.index(entrantId)].append(character[0])

        games.append({"winner": winner, "stage": stage, "characters": characters})
    return games


def ParseMatchDataOldApi(respTasks, gameAssets):
    entities = respTasks.get("entities", {})
    sets = entities.get("sets", {})
    tasks = entities.get("setTask", [])

    selectedCharMap = {}
    entrant1Id = str(sets.get("entrant1Id"))
    entrant2Id = str(sets.get("entrant2Id"))

    for task in reversed(tasks):
        if task.get("action") in ["setup_character", "setup_strike", "setup_ban"]:
            selectedCharMap = task.get("metadata", {}).get("charSelections", {})
            if len(selectedCharMap) > 0:
                break
        elif task.get("action") in ["report"]:
            allSelections = task.get("metadata", {}).get("report", {}).get("selections", [])

            if isinstance(allSelections, list):
                for selection in allSelections:
                    if selection.get("selectionType") == "character":
                        selectedCharMap[str(selection.get("entrantId"))] = [
                            selection.get("selectionValue")
                        ]
                if len(selectedCharMap) > 0:
                    break

    logger.debug(f"selectedCharMap: {selectedCharMap}")
    selectedChars = [[], []]

    for char in selectedCharMap.items():
        if str(char[0]) == entrant1Id:
            selectedChars[0] = char[1]
        if str(char[0]) == entrant2Id:
            selectedChars[1] = char[1]

    latestWinner = None

    for task in reversed(tasks):
        if len(task.get("metadata", [])) == 0:
            continue
        if task.get("active"):
            continue
        if task.get("metadata", {}).get("report", {}).get("winnerId", None) is not None:
            latestWinner = int(task.get("metadata", {}).get("report", {}).get("winnerId"))
            break

    lastWinnerSlot = None

    if latestWinner:
        if str(latestWinner) == entrant1Id:
            lastWinnerSlot = 0
        if str(latestWinner) == entrant2Id:
            lastWinnerSlot = 1

    allStages = None
    strikedStages = None
    strikedBy = [[], []]
    selectedStage = None
    dsrStages = None
    currPlayer = 0
    dsr = False
    mdsr = False

    for task in reversed(tasks):
        if task.get("action") in [
            "setup_strike",
            "setup_stage",
            "setup_character",
            "setup_ban",
            "report",
        ]:
            if len(task.get("metadata", [])) == 0:
                continue

            base = task.get("metadata", {})

            if task.get("action") == "report":
                base = base.get("report", {})

            if base.get("strikeStages", None) is not None:
                allStages = base.get("strikeStages")
            elif base.get("banStages", None) is not None:
                allStages = base.get("banStages")

            if base.get("strikeList", None) is not None:
                strikedStages = base.get("strikeList")
            elif base.get("banList", None) is not None:
                strikedStages = base.get("banList")

            if base.get("stageSelection", None) is not None:
                selectedStage = base.get("stageSelection")
            elif base.get("stageId", None) is not None:
                selectedStage = base.get("stageId")

            # Stages previously won in
            stageWins = [[], []]
            if base.get("stageWins"):
                for entrantId, stageCodes in base.get("stageWins").items():
                    stages = []

                    for stageCode in stageCodes:
                        stages.append(
                            gameAssets.GetStageFromStartGGId(int(stageCode))[1].get("codename")
                        )

                    if str(entrantId) == entrant1Id:
                        stageWins[0] = stages
                    if str(entrantId) == entrant2Id:
                        stageWins[1] = stages

            if base.get("useMDSR"):
                mdsr = True
            if base.get("useDSR"):
                dsr = True

            if base.get("strikeList"):
                for stage_code, entrant in base.get("strikeList").items():
                    stage = gameAssets.GetStageFromStartGGId(int(stage_code))

                    if stage:
                        codename = stage[1].get("codename")

                        if str(entrant) == entrant1Id:
                            strikedBy[0].append(codename)
                        if str(entrant) == entrant2Id:
                            strikedBy[1].append(codename)
            else:
                banPlayer = 0

                if str(latestWinner) == entrant1Id:
                    banPlayer = 0
                if str(latestWinner) == entrant2Id:
                    banPlayer = 1

                if base.get("banList", None) is not None:
                    for stage_code in base.get("banList"):
                        if stage_code == None:
                            continue
                        stage = gameAssets.GetStageFromStartGGId(int(stage_code))
                        if stage:
                            codename = stage[1].get("codename")
                            strikedBy[banPlayer].append(codename)

            if latestWinner:
                lastLoserSlot = 0

                if str(latestWinner) == entrant1Id:
                    lastLoserSlot = 1
                if str(latestWinner) == entrant2Id:
                    lastLoserSlot = 0

                currPlayer = lastLoserSlot
            elif base.get("turn"):
                for entrant, value in base.get("turn").items():
                    if str(entrant) == entrant1Id and value == True:
                        currPlayer = 1
                    if str(entrant) == entrant2Id and value == True:
                        currPlayer = 0

            if allStages == None and strikedStages == None and selectedStage == None:
                continue

            if allStages == None:
                continue

            break

    try:
        allStagesFinal = []
        for st in allStages:
            stage = gameAssets.GetStageFromStartGGId(st)
            if stage:
                allStagesFinal.append(stage[1])

        striked = []
        if strikedStages is not None:
            for stage in strikedStages:
                stage = gameAssets.GetStageFromStartGGId(stage)
                if stage:
                    striked.append(stage[1].get("codename"))

        selected = ""
        if selectedStage is not None:
            selectedStage = gameAssets.GetStageFromStartGGId(int(selectedStage))
            if selectedStage:
                selected = selectedStage[1].get("codename")

        stageStrikeState = {
            "strikedBy": strikedBy,
            "strikedStages": [striked],
            "stagesWon": stageWins,
            "selectedStage": selected,
            "currPlayer": currPlayer,
            "lastWinner": lastWinnerSlot,
            "currGame": sets.get("entrant1Score", 0) + sets.get("entrant2Score", 0),
        }

        rulesetState = {
            "neutralStages": allStagesFinal,
            "useDSR": dsr,
            "useMDSR": mdsr,
        }
    except:
        logger.info("No Stage Strike Info Found")
        allStages = None
        strikedStages = None
        strikedBy = [[], []]
        selectedStage = None
        dsrStages = None
        currPlayer = 0
        stageStrikeState = {}
        rulesetState = {}

    entrants = [[], []]

    for i, entrantChars in enumerate(selectedChars):
        for char in entrantChars:
            entrants[i].append({"mains": [gameAssets.GetCharacterFromStartGGId(char)[0], 0]})

    # If we don't have mains from the selection data, fallback to the characterIds attribute
    for i in [0, 1]:
        if len(entrants[i]) == 0:
            characterIds = deep_get(sets, f"entrant{i + 1}CharacterIds", []) or []

            for char in characterIds:
                try:
                    entrants[i] = [
                        {
                            "mains": [
                                gameAssets.GetCharacterFromStartGGId(char)[0],
                                0,
                            ]
                        }
                    ]
                except:
                    logger.error(traceback.format_exc())

    team1losers = False
    team2losers = False

    if sets.get("isGF", False):
        if "Reset" not in sets.get("fullRoundText", ""):
            team1losers = False
            team2losers = True
        else:
            team1losers = True
            team2losers = True

    logger.info("Team 1 Score - OLD API: " + str(sets.get("entrant1Score", 0)))
    logger.info("Team 2 Score - OLD API: " + str(sets.get("entrant2Score", 0)))

    return {
        "stage_strike": stageStrikeState,
        "ruleset": rulesetState,
        "strikedBy": strikedBy,
        "entrants": entrants,
        "team1score": sets.get("entrant1Score", 0),
        "team2score": sets.get("entrant2Score", 0),
        "bestOf": sets.get("bestOf", None),
        "roundDivision": sets.get("roundDivision", None),
        "team1losers": team1losers,
        "team2losers": team2losers,
        "currPlayer": currPlayer,
        "winnerProgression": sets.get("wProgressingName", None),
        "loserProgression": sets.get("lProgressingName", None),
    }


def SetWinnerSlot(s):
    # Slot of the set's winner, if start.gg has one
    if s.get("winnerId") is None:
        return None
    for slotIndex, slot in enumerate(s.get("slots") or []):
        entrantId = deep_get(slot, "entrant.id")
        if entrantId is not None and str(entrantId) == str(s.get("winnerId")):
            return slotIndex
    return None


def BuildGraphSets(seeds, sets):
    # The phase group's sets in the bracket model's format
    # (BracketModel.FromProviderSets), with players as their 1-based
    # entrant index (by seed)
    seedIndex = {}
    entrantIndex = {}
    for i, seed in enumerate(seeds):
        if seed.get("id") is not None:
            seedIndex[str(seed.get("id"))] = i + 1
        entrantId = deep_get(seed, "entrant.id")
        if entrantId is not None:
            entrantIndex[str(entrantId)] = i + 1

    graphSets = []
    for s in sets:
        slots = []

        for slotIndex, slot in enumerate(s.get("slots") or []):
            seedId = deep_get(slot, "seed.id")
            if seedId is None and slot.get("prereqType") == "seed":
                # A seed slot's prereq is the seed itself
                seedId = slot.get("prereqId")
            entrantId = deep_get(slot, "entrant.id")

            player = seedIndex.get(str(seedId)) if seedId is not None else None
            if player is None and entrantId is not None:
                player = entrantIndex.get(str(entrantId))

            slots.append(
                {
                    "prereqType": slot.get("prereqType"),
                    "prereqId": str(slot.get("prereqId"))
                    if slot.get("prereqId") is not None
                    else None,
                    "placement": slot.get("prereqPlacement"),
                    "player": player,
                    "entrantId": str(entrantId) if entrantId is not None else None,
                }
            )

        graphSets.append(
            {
                "id": str(s.get("id")),
                "round": int(s.get("round") or 0),
                "identifier": s.get("identifier"),
                "name": s.get("fullRoundText"),
                "score": [s.get("entrant1Score"), s.get("entrant2Score")],
                "finished": s.get("state", 0) == 3,
                "winnerSlot": SetWinnerSlot(s),
                "slots": slots,
            }
        )

    return graphSets


def RecentSetPlayer1Slot(_set, pid1, pid2):
    # The slot player 1 is in if the set is the two players facing each
    # other one on one, otherwise None
    players = []
    for slot in _set.get("slots") or []:
        participants = deep_get(slot, "entrant.participants") or []
        if len(participants) != 1:
            return None
        players.append(str(deep_get(participants[0], "player.id")))

    if len(players) != 2 or set(players) != {pid1, pid2}:
        return None

    return players.index(pid1)


def ProcessEntrantData(entrant, setData=[], gameAssets=None):
    gameAssets = gameAssets if gameAssets is not None else AppContext().games
    player = entrant.get("player")
    user = entrant.get("user")

    playerData = {}

    if player:
        playerData["prefix"] = player.get("prefix")
        playerData["gamerTag"] = player.get("gamerTag")
        playerData["name"] = player.get("name")

        # Main character
        playerSelections = Counter()

        sets = []

        if not setData:
            sets = deep_get(player, "sets.nodes", [])
        else:
            sets = setData

        playerId = player.get("id")

        if len(sets) > 0:
            for _set in sets:
                games = _set.get("games", [])
                if games and len(games) > 0:
                    for game in games:
                        selections = game.get("selections", [])
                        if selections:
                            for selection in selections:
                                participants = selection.get("entrant", {}).get("participants", [])
                                if len(participants) > 0:
                                    participantId = (
                                        participants[0].get("player", {}).get("id", None)
                                    )
                                    if participantId and participantId == playerId:
                                        playerSelections[selection.get("selectionValue")] += 1

        mains = playerSelections.most_common()

        if len(mains) > 0:
            playerData["startggMains"] = mains

    if user:
        playerData["id"] = [player.get("id"), user.get("id")]

        if user.get("slug"):
            playerData["startgg_user_slug"] = user.get("slug")

        ParseUserSocials(user, playerData)

        if user.get("genderPronoun"):
            playerData["pronoun"] = user.get("genderPronoun")

        if len(user.get("images", [])) > 0:
            playerData["avatar"] = user.get("images")[0].get("url")

        if user.get("location"):
            # Country to country code
            if user.get("location").get("country"):
                for country in CountryHelper.countries.values():
                    if user.get("location").get("country") == country.get("en_name"):
                        playerData["country_code"] = country.get("code")
                        break

            # State -- direct
            if user.get("location").get("state"):
                stateCode = user.get("location").get("state")
                if stateCode:
                    playerData["state_code"] = user.get("location").get("state")
            # State -- from city
            elif user.get("location").get("city"):
                stateCode = CountryHelper.FindState(
                    playerData.get("country_code", None),
                    user.get("location", {}).get("city", None),
                )
                if stateCode:
                    playerData["state_code"] = stateCode

        if playerData.get("startggMains"):
            if gameAssets.selectedGame:
                gameCodename = gameAssets.selectedGame.get("codename")

                mains = []

                for sggmain in playerData.get("startggMains"):
                    main = gameAssets.GetCharacterFromStartGGId(sggmain[0])
                    if main:
                        mains.append([main[0]])

                playerData["mains"] = {gameCodename: mains}
            else:
                playerData["mains"] = {}
    if "id" not in playerData:
        playerData["id"] = [player.get("id"), 0]

    return playerData


def ParseUserSocials(user, playerData):
    """Sets playerData's socials (and twitter) from the start.gg user's
    linked accounts. Only the accounts the user has are set, so ones
    typed in by hand are kept when merged with the local DB."""
    socials = SocialsHelper.FromStartGG(user.get("authorizations"))
    if socials:
        playerData["socials"] = socials
        if socials.get("twitter"):
            playerData["twitter"] = socials["twitter"]


def LocationCodes(location):
    """(country_code, state_code) of a start.gg user location, the state
    found from the city when it isn't given."""
    if not location:
        return None, None
    countryCode = next(
        (
            country.get("code")
            for country in CountryHelper.countries.values()
            if location.get("country") and location.get("country") == country.get("en_name")
        ),
        None,
    )
    stateCode = location.get("state")
    if not stateCode and location.get("city"):
        stateCode = CountryHelper.FindState(countryCode, location.get("city"))
    return countryCode, stateCode or None
