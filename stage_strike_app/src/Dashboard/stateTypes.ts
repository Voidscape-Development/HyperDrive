import {useSelector} from "react-redux";
import type {ReduxState} from "../redux/store";
import type {HDCharacterSelections, HDPlayerInfo, HDState} from "../backendDataTypes";

/*
 * The parts of HyperDrive's program state the dashboard reads that the
 * other pages don't. See docs/layout-data.md for what each holds.
 */

export interface DisplayState {
    folders: Record<string, boolean>;
    groups: Record<string, boolean>;
}

export interface QueueSet {
    id?: number | string;
    queueKey: string;
    source: string;
    position: number;
    onStream: boolean;
    eta?: number | null;
    eta_minutes?: number | null;
    match?: string;
    phase?: string;
    station?: string | number | null;
    state?: number;
    p1_name?: string;
    p2_name?: string;
    team?: Record<string, {teamName?: string; player?: Record<string, {name?: string; mergedName?: string}>}>;
    [key: string]: unknown;
}

export interface StreamQueueState {
    streams: {name: string; manual: boolean; scoreboard: number | null; sets: QueueSet[]}[];
    lastUpdated: number | null;
    average_set_minutes: number | null;
}

export interface CompletedSet {
    round_name: string;
    phase_name: string;
    winner_score: number;
    loser_score: number;
    winner_team_name?: string;
    loser_team_name?: string;
    winner_team: Record<string, {gamertag?: string; sponsor?: string}>;
    loser_team: Record<string, {gamertag?: string; sponsor?: string}>;
    upset_factor?: number;
}

export interface BracketSet {
    playerId?: (number | null)[];
    score?: (number | null)[];
    finished?: boolean;
    name?: string;
    round?: number;
    [key: string]: unknown;
}

export interface BracketExport {
    name?: string;
    type?: string;
    sets?: Record<string, BracketSet>;
    sides?: Record<string, string[][]>;
    [key: string]: unknown;
}

export interface BracketState {
    bracket?: BracketExport;
    channels?: Record<string, {bracket?: BracketExport; phase?: string}>;
    players?: {slot?: Record<string, PlayerListSlot>};
    phase?: string;
}

export interface PlayerListSlot {
    name?: string;
    score?: number;
    player?: Record<string, HDPlayerInfo>;
}

export interface TeamBattlePlayer extends HDPlayerInfo {
    dead?: boolean;
    active?: boolean;
    dynamicSpinner?: string | number;
    character: HDCharacterSelections;
}

export interface TeamBattleState {
    battle_mode?: string;
    battle_value?: number;
    limited?: boolean;
    plays?: number;
    phase?: string;
    match?: string;
    team?: Record<string, {color?: string; sponsor?: string; active_player?: number; player?: Record<string, TeamBattlePlayer>}>;
    [key: string]: unknown;
}

export interface DashboardState extends HDState {
    game?: HDState["game"] & {has_modded_content?: boolean; mods_active?: boolean};
    display?: DisplayState;
    stream_queue?: StreamQueueState;
    completed_sets?: Record<string, CompletedSet>;
    commentary?: Record<string, HDPlayerInfo>;
    player_list?: {slot?: Record<string, PlayerListSlot>};
    team_battle?: TeamBattleState;
    bracket?: BracketState;
}

/** Part of the program state, as it changes */
export function useHd<T>(pick: (state: DashboardState) => T): T {
    return useSelector((s: ReduxState) => pick(s.hdState.hdState as DashboardState));
}

/** The program state has arrived from HyperDrive */
export function useHdReady() {
    return useSelector((s: ReduxState) => !s.hdState.initializing);
}
