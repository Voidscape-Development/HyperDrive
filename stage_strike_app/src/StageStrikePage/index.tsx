import {type ReactNode, useEffect, useMemo, useRef, useState} from "react";
import "../NoSleep";
import "./stageStrike.css";
import i18n from "../i18n/config";
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
  type Stage,
} from "./strikeLogic";
import {Page} from "@/components/Page";

export default function StageStrikePage() {
  const {scoreboard, setScoreboard, locked} = useScoreboardParam();
  // With ?team=<1|2> the page is one team's: it strikes on its turn only and
  // picks only its own characters
  const team = useTeamParam();
  const target = useMemo(() => ({scoreboard, team}), [scoreboard, team]);
  const {data, scoreboards, connected, missing, refresh} = useStrikeData(scoreboard, locked ? null : setScoreboard);
  const characters = useCharacters(data?.game);
  const [charactersOpen, setCharactersOpen] = useState(false);

  const ruleset = data?.ruleset;
  const state = useMemo(() => ({...EMPTY_STATE, ...(data?.state ?? {})}), [data]);
  const bestOf = data?.best_of;
  const playerNames = [data?.p1 || i18n.t("p1"), data?.p2 || i18n.t("p2")];
  // The strike player (0 or 1) of this page's team, -1 for both teams
  const myPlayer = team ? (data?.teams ?? []).findIndex((t) => t?.team === team) : -1;
  const teamMode = myPlayer !== -1;
  const myTurn = !teamMode || state.currPlayer === myPlayer;
  const characterSelect = state.characterSelect ?? {active: false, submitted: {}};

  useEffect(() => {
    document.title = `${i18n.t("title")} · ${scoreboards.find((s) => s.number === scoreboard)?.name ?? scoreboard}`;
  }, [scoreboard, scoreboards]);

  // Once a game's winner is reported, asks for the next game's characters,
  // unless this page already sent them or HyperDrive's settings say not to
  const waitingForMe = characterSelect.active && (teamMode
    ? !characterSelect.submitted?.[String(team)]
    : !(characterSelect.submitted?.["1"] && characterSelect.submitted?.["2"]));
  const lastAskedGame = useRef(null);
  const askCharacters = data?.ask_characters ?? true;
  useEffect(() => {
    if (!askCharacters || !waitingForMe) return;
    const key = `${scoreboard}-${characterSelect.game}`;
    if (lastAskedGame.current !== key) {
      lastAskedGame.current = key;
      refresh();
      setCharactersOpen(true);
    }
  }, [askCharacters, waitingForMe, characterSelect.game, scoreboard, refresh]);

  const openCharacters = () => {
    // Players or the character count may have changed in HyperDrive since
    refresh();
    setCharactersOpen(true);
  };

  const topBar = (
    <TopBar
      scoreboard={scoreboard}
      scoreboards={scoreboards}
      onScoreboardChange={locked ? null : setScoreboard}
      teamName={teamMode ? playerNames[myPlayer] : null}
      teamPlayer={myPlayer}
      connected={connected}
    />
  );

  if (!data) {
    return <Page>
      {topBar}
      <NoRulesetError loading connected={connected} missingScoreboard={missing ? scoreboard : null} />
    </Page>;
  }

  // No ruleset, so no stages to strike: only the characters are picked
  if (!ruleset || !ruleset.neutralStages || ruleset.neutralStages.length === 0) {
    return <Page>
      {topBar}
      <CharacterSelectView
        data={data}
        scoreboard={scoreboard}
        team={team}
        characters={characters}
        refresh={refresh}
        notice={i18n.t("no_ruleset_characters_only")}
      />
    </Page>;
  }

  const stageList = (stages: Stage[]) => stages.map((stage) => {
    const striker = PlayerWhoStrikedStage(state, stage.codename);
    const isSelected = state.selectedStage === stage.codename;
    // The picked stage only shows as struck or banned for a gentleman's
    // pick, which may pick any stage
    const showRestrictions = !isSelected || state.gentlemans;
    return <StageCard
      key={stage.codename ?? stage.en_name}
      stageName={StageName(stage)}
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

  return <Page>
    {topBar}

    <main className="mx-auto w-full max-w-[1500px] flex-1 overflow-auto px-4 pt-3 pb-4">
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

      <div>
        {showCounterpicks && <SectionTitle>{i18n.t("starters")}</SectionTitle>}
        <StageGrid>{stageList(ruleset.neutralStages)}</StageGrid>
        {showCounterpicks && <>
          <SectionTitle>{i18n.t("counterpicks")}</SectionTitle>
          <StageGrid>{stageList(ruleset.counterpickStages)}</StageGrid>
        </>}
      </div>
    </main>

    <footer className="flex shrink-0 flex-col gap-2 border-t bg-background/90 px-4 pt-2.5 pb-[calc(10px+env(safe-area-inset-bottom))] backdrop-blur">
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
    </footer>

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
  </Page>;
}

function SectionTitle({children}: {children: ReactNode}) {
  return <h2 className="mt-3 mb-1.5 text-center text-xs font-medium tracking-[0.12em] text-muted-foreground uppercase">
    {children}
  </h2>;
}

function StageGrid({children}: {children: ReactNode}) {
  // Few stages stay centered instead of stretching
  return <div className="grid grid-cols-[repeat(auto-fill,minmax(min(45%,200px),1fr))] gap-3 sm:grid-cols-[repeat(auto-fit,minmax(200px,280px))] sm:justify-center">
    {children}
  </div>;
}
