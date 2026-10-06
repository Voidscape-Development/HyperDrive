import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import "../NoSleep";
import "../App.css";
import "./stageStrike.css";
import {Box, Typography} from "@mui/material";
import i18n from "../i18n/config";
import {languageSettings} from "./languageSettings";
import {BASE_URL} from "../env";
import {NoRulesetError} from "./NoRulesetError";
import {StageCard} from "./StageCard";
import {StageClicked} from "./postActions";
import {RpsDialog} from "./RpsDialog";
import {FooterControls} from "./FooterControls";
import {StagePromptText} from "./StagePromptText";
import {TopBar} from "./TopBar";
import {PlayerPanels} from "./PlayerPanels";
import {ActionBar} from "./ActionBar";
import {CharacterReportDialog, MissingCharacters} from "./CharacterReportDialog";
import {CharacterSelectView} from "../CharacterSelectPage";
import {useCharacters, useScoreboardParam, useStrikeData, useTeamParam} from "./useHdData";
import {
  CanConfirm,
  EMPTY_STATE,
  GetStrikeNumber,
  GetStrikeSteps,
  IsPicking,
  IsStageBanned,
  IsStageStriked,
  PlayerWhoStrikedStage,
  StageName,
} from "./strikeLogic";
import {loadUiSettings, saveUiSettings} from "./uiSettings";

export default function StageStrikePage() {
  const [scoreboard, setScoreboard] = useScoreboardParam();
  // With ?team=<1|2> the page is one team's: it strikes on its turn only and
  // picks only its own characters
  const team = useTeamParam();
  const target = useMemo(() => ({scoreboard, team}), [scoreboard, team]);
  const {data, scoreboards, connected, refresh} = useStrikeData(scoreboard, setScoreboard);
  const characters = useCharacters(data?.game);
  const [, forceUpdate] = useState(0);
  const [charactersOpen, setCharactersOpen] = useState(false);
  const [uiSettings, setUiSettings] = useState(loadUiSettings);

  useEffect(() => {
    const listener = () => forceUpdate((n) => n + 1);
    i18n.on("languageChanged", listener);
    return () => i18n.off("languageChanged", listener);
  }, []);

  const ruleset = data?.ruleset;
  const state = useMemo(() => ({...EMPTY_STATE, ...(data?.state ?? {})}), [data]);
  const bestOf = data?.best_of;
  const playerNames = [data?.p1 || i18n.t("p1"), data?.p2 || i18n.t("p2")];
  const playerLanguages = [languageFromCountry(data?.p1_country), languageFromCountry(data?.p2_country)];
  // The strike player (0 or 1) of this page's team, -1 for both teams
  const myPlayer = team ? (data?.teams ?? []).findIndex((t) => t?.team === team) : -1;
  const teamMode = myPlayer !== -1;
  const myTurn = !teamMode || state.currPlayer === myPlayer;
  const characterSelect = state.characterSelect ?? {active: false, submitted: {}};

  // Shared steps (before RPS, once the stage is picked) use the page's
  // language, the strikes use the player whose turn it is
  const stepLanguage = (state.selectedStage !== null || state.currPlayer === -1)
    ? languageSettings.language
    : playerLanguages[state.currPlayer] || languageSettings.language;

  useEffect(() => {
    if (languageSettings.usePlayerLanguage) i18n.changeLanguage(stepLanguage);
  }, [stepLanguage]);

  useEffect(() => {
    document.title = `${i18n.t("title")} · ${scoreboards.find((s) => s.number === scoreboard)?.name ?? scoreboard}`;
  }, [scoreboard, scoreboards]);

  // Once a game's winner is reported, asks for the next game's characters,
  // unless this page already sent them
  const waitingForMe = characterSelect.active && (teamMode
    ? !characterSelect.submitted?.[String(team)]
    : !(characterSelect.submitted?.["1"] && characterSelect.submitted?.["2"]));
  const lastAskedGame = useRef(null);
  useEffect(() => {
    if (!uiSettings.askCharacters || !waitingForMe) return;
    const key = `${scoreboard}-${characterSelect.game}`;
    if (lastAskedGame.current !== key) {
      lastAskedGame.current = key;
      refresh();
      setCharactersOpen(true);
    }
  }, [uiSettings.askCharacters, waitingForMe, characterSelect.game, scoreboard, refresh]);

  const changeUiSettings = useCallback((changes) => {
    setUiSettings((prev) => saveUiSettings({...prev, ...changes}));
  }, []);

  const openCharacters = () => {
    // Players or the character count may have changed in HyperDrive since
    refresh();
    setCharactersOpen(true);
  };

  const topBar = (
    <TopBar
      scoreboard={scoreboard}
      scoreboards={scoreboards}
      onScoreboardChange={setScoreboard}
      teamName={teamMode ? playerNames[myPlayer] : null}
      teamPlayer={myPlayer}
      connected={connected}
      playerLanguages={playerLanguages}
      currPlayer={state.currPlayer}
      selectedStage={state.selectedStage}
      uiSettings={uiSettings}
      onUiSettingsChange={changeUiSettings}
    />
  );

  if (!data) {
    return <Box className="ss-page">
      {topBar}
      <NoRulesetError loading connected={connected} />
    </Box>;
  }

  // No ruleset, so no stages to strike: only the characters are picked
  if (!ruleset || !ruleset.neutralStages || ruleset.neutralStages.length === 0) {
    return <Box className="ss-page">
      {topBar}
      <CharacterSelectView
        data={data}
        scoreboard={scoreboard}
        team={team}
        characters={characters}
        refresh={refresh}
        notice={i18n.t("no_ruleset_characters_only")}
      />
    </Box>;
  }

  const stageList = (stages) => stages.map((stage) => {
    const striker = PlayerWhoStrikedStage(state, stage.codename);
    const isSelected = state.selectedStage === stage.codename;
    // The picked stage only shows as struck or banned for a gentleman's
    // pick, which may pick any stage
    const showRestrictions = !isSelected || state.gentlemans;
    return <StageCard
      key={stage.codename ?? stage.en_name}
      stageName={StageName(stage, stepLanguage)}
      stageImage={`${BASE_URL}/${stage.path}`}
      isSelected={isSelected}
      onClick={() => StageClicked(target, stage)}
      disabled={!myTurn}
      isStriked={showRestrictions && IsStageStriked(state, stage.codename)}
      isBanned={showRestrictions && IsStageBanned(ruleset, state, stage.codename)}
      isGentlemanEnabled={state.gentlemans}
      // Game 1's stage is the one left, nobody picked it
      selectedBy={state.gentlemans || state.currGame === 0 ? null : playerNames[state.currPlayer]}
      selectedByPlayer={state.currPlayer}
      strikedBy={striker !== -1 ? playerNames[striker] : null}
      strikedByPlayer={striker}
    />;
  });

  const showCounterpicks = state.currGame > 0 && (ruleset.counterpickStages ?? []).length > 0;
  const missingCharacters = MissingCharacters(data.teams, data.characters_per_player);

  return <Box className="ss-page">
    {topBar}

    <Box className="ss-content">
      <PlayerPanels
        playerNames={playerNames}
        teams={data.teams}
        characters={characters}
        wins={[state.stagesWon?.[0]?.length ?? 0, state.stagesWon?.[1]?.length ?? 0]}
        currPlayer={state.selectedStage ? -1 : state.currPlayer}
        myPlayer={myPlayer}
        characterSelect={characterSelect}
        currGame={state.currGame}
        bestOf={bestOf}
        phase={data.phase}
        match={data.match}
      />

      {state.currPlayer !== -1 &&
        <StagePromptText
          selectedStage={state.selectedStage}
          isGentlemans={state.gentlemans}
          isPicking={IsPicking(ruleset, state)}
          strikeNumber={GetStrikeNumber(ruleset, state, bestOf)}
          strikesDone={(state.strikedStages?.[state.currStep] ?? []).length}
          currentPlayer={state.currPlayer}
          currentPlayerName={playerNames[state.currPlayer]}
          steps={GetStrikeSteps(ruleset, state, bestOf)}
          playerNames={playerNames}
          waiting={!myTurn}
        />
      }

      <Box className="ss-stages">
        {showCounterpicks &&
          <Typography className="ss-section-title" variant="overline">{i18n.t("starters")}</Typography>
        }
        <Box className="ss-stage-grid">
          {stageList(ruleset.neutralStages)}
        </Box>
        {showCounterpicks && <>
          <Typography className="ss-section-title" variant="overline">{i18n.t("counterpicks")}</Typography>
          <Box className="ss-stage-grid">
            {stageList(ruleset.counterpickStages)}
          </Box>
        </>}
      </Box>
    </Box>

    <Box className="ss-bottom">
      <ActionBar
        target={target}
        canConfirm={myTurn && CanConfirm(ruleset, state, bestOf)}
        selectedStage={state.selectedStage}
        playerNames={playerNames}
        teams={data.teams}
        myPlayer={myPlayer}
        pendingWinner={state.pendingWinner}
      />
      <FooterControls
        target={target}
        teamMode={teamMode}
        // It clears the game's strikes, so only on the team's own turn
        canToggleGentlemans={myTurn}
        // A team's page only undoes and redoes its own team's actions
        canUndo={state.canUndo && (!teamMode || state.lastActor === team)}
        canRedo={state.canRedo && (!teamMode || state.nextActor === team)}
        isGentlemans={state.gentlemans}
        onCharacters={openCharacters}
        missingCharacters={missingCharacters || waitingForMe}
      />
    </Box>

    {state.currPlayer === -1 &&
      <RpsDialog target={target} playerNames={playerNames} />
    }

    <CharacterReportDialog
      open={charactersOpen}
      onClose={() => setCharactersOpen(false)}
      target={target}
      myPlayer={myPlayer}
      characterSelect={characterSelect}
      game={data.game}
      teams={data.teams}
      charactersPerPlayer={data.characters_per_player}
      playerNames={playerNames}
      characters={characters}
    />
  </Box>;
}

// Maps ISO 3166-1 alpha-2 country codes to the language codes used in stage locales.
// i18next needs hyphenated codes (zh-CN); StageName converts them for stage locales.
const COUNTRY_LANGUAGE = {
  JP: "ja",
  KR: "ko",
  CN: "zh-CN",
  TW: "zh-TW", HK: "zh-TW", MO: "zh-TW",
  FR: "fr",    BE: "fr", CH: "fr", LU: "fr", MC: "fr",
  ES: "es",    MX: "es", AR: "es", CL: "es", CO: "es", PE: "es",
               VE: "es", EC: "es", BO: "es", PY: "es", UY: "es",
               GT: "es", HN: "es", SV: "es", NI: "es", CR: "es",
               PA: "es", DO: "es", CU: "es", PR: "es",
  BR: "pt-BR",
  PT: "pt-PT", AO: "pt-PT", MZ: "pt-PT", CV: "pt-PT", GW: "pt-PT", ST: "pt-PT", TL: "pt-PT",
  IT: "it",
  DE: "de",
  NL: "nl",    SR: "nl",
  RU: "ru",
};

function languageFromCountry(countryCode) {
  return COUNTRY_LANGUAGE[countryCode] ?? "en";
}
