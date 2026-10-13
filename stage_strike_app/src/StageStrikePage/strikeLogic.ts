// The stage strike rules, mirroring StageStrikeLogic.py, to show what
// HyperDrive will accept before asking it.

import type {CharacterSelect, PendingWinner} from "./useHdData";

/** A stage of the ruleset */
export interface Stage {
  codename?: string;
  en_name?: string;
  name?: string;
  path?: string;
  locale?: Record<string, string>;
}

export interface Ruleset {
  neutralStages?: Stage[];
  counterpickStages?: Stage[];
  strikeOrder?: number[];
  banCount?: number;
  banByMaxGames?: Record<string, number>;
  useDSR?: boolean;
  useMDSR?: boolean;
}

/** The scoreboard's strike, as StageStrikeLogic.py keeps it */
export interface StrikeState {
  currGame: number;
  currPlayer: number;
  currStep: number;
  strikedStages: string[][];
  strikedBy: string[][];
  stagesWon: string[][];
  stagesPicked: string[];
  selectedStage: string | null;
  lastWinner: number;
  gentlemans: boolean;
  canUndo: boolean;
  canRedo: boolean;
  pendingWinner: PendingWinner | null;
  // The team (1 or 2) whose action undo and redo would undo or redo
  lastActor: number | null;
  nextActor: number | null;
  characterSelect?: CharacterSelect;
}

export interface StrikeStep {
  player: number;
  count: number;
  kind: "ban" | "pick";
  done: boolean;
  current: boolean;
}

export const EMPTY_STATE: StrikeState = {
  currGame: 0,
  currPlayer: -1,
  currStep: 0,
  strikedStages: [[]],
  strikedBy: [[], []],
  stagesWon: [[], []],
  stagesPicked: [],
  selectedStage: null,
  lastWinner: -1,
  gentlemans: false,
  canUndo: false,
  canRedo: false,
  pendingWinner: null,
  lastActor: null,
  nextActor: null,
};

export function IsStageStriked(state: StrikeState, stage: string, previously = false) {
  const rounds = Object.values(state.strikedStages ?? []);
  for (let i = 0; i < rounds.length; i += 1) {
    if (previously && i === rounds.length - 1) continue;
    if ((rounds[i] ?? []).includes(stage)) return true;
  }
  return false;
}

export function GetBannedStages(ruleset: Ruleset, state: StrikeState): string[] {
  if (ruleset?.useDSR) {
    return state.stagesPicked ?? [];
  }
  if (ruleset?.useMDSR && state.lastWinner !== -1) {
    return state.stagesWon?.[(state.lastWinner + 1) % 2] ?? [];
  }
  return [];
}

export function IsStageBanned(ruleset: Ruleset, state: StrikeState, stage: string) {
  return GetBannedStages(ruleset, state).includes(stage);
}

export function GetStrikeNumber(ruleset: Ruleset, state: StrikeState, bestOf: number): number {
  if (!ruleset) return 0;
  if (state.currGame === 0) {
    return ruleset.strikeOrder?.[state.currStep] ?? 0;
  }
  if (ruleset.banCount) {
    return ruleset.banCount;
  }
  if (ruleset.banByMaxGames && String(bestOf) in ruleset.banByMaxGames) {
    return ruleset.banByMaxGames[String(bestOf)];
  }
  return 0;
}

export function CanConfirm(ruleset: Ruleset, state: StrikeState, bestOf: number) {
  const striked = state.strikedStages?.[state.currStep];
  if (state.currPlayer === -1 || state.selectedStage || !striked || IsPicking(ruleset, state)) {
    return false;
  }
  return striked.length === GetStrikeNumber(ruleset, state, bestOf);
}

/** Whether the current player picks a stage instead of striking */
export function IsPicking(ruleset: Ruleset, state: StrikeState) {
  if (state.gentlemans) return true;
  if (state.currGame > 0) return state.currStep > 0;
  // Game 1's stage is the one left once the strikes are done. A ruleset
  // striking too few leaves more than one, then the next player picks.
  return state.currStep >= (ruleset?.strikeOrder ?? []).length;
}

/** 0 or 1 for the player who struck the stage this game, -1 if none */
export function PlayerWhoStrikedStage(state: StrikeState, stage: string) {
  if ((state.strikedBy?.[0] ?? []).includes(stage)) return 0;
  if ((state.strikedBy?.[1] ?? []).includes(stage)) return 1;
  return -1;
}

/**
 * The steps of the current game's striking, for a progress indicator
 */
export function GetStrikeSteps(ruleset: Ruleset, state: StrikeState, bestOf: number): StrikeStep[] {
  if (!ruleset || state.currPlayer === -1 || state.gentlemans) return [];

  const steps: StrikeStep[] = [];
  if (state.currGame === 0) {
    // Players alternate, starting with the RPS winner
    const first = state.lastWinner !== -1 ? state.lastWinner : state.currPlayer;
    (ruleset.strikeOrder ?? []).forEach((count, i) => {
      steps.push({
        player: (first + i) % 2,
        count,
        kind: "ban",
        done: i < state.currStep,
        current: i === state.currStep && !state.selectedStage,
      });
    });
  } else {
    const bans = GetStrikeNumber(ruleset, state, bestOf);
    const winner = state.lastWinner;
    if (bans > 0) {
      steps.push({
        player: winner,
        count: bans,
        kind: "ban",
        done: state.currStep > 0,
        current: state.currStep === 0,
      });
    }
    steps.push({
      player: (winner + 1) % 2,
      count: 1,
      kind: "pick",
      done: !!state.selectedStage,
      current: state.currStep > 0 && !state.selectedStage,
    });
  }
  return steps;
}

export function StageName(stage: Stage, language: string) {
  if (stage.locale && language) {
    const langKey = language.replace("-", "_");
    if (Object.prototype.hasOwnProperty.call(stage.locale, langKey)) return stage.locale[langKey];
    const short = language.split(/[-_]/)[0];
    if (Object.prototype.hasOwnProperty.call(stage.locale, short)) return stage.locale[short];
  }
  return stage.en_name ?? stage.name ?? stage.codename;
}
