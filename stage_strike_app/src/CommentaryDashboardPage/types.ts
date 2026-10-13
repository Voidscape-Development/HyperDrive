/**
 * The parts of HyperDrive's program state the commentary dashboard reads,
 * as described in docs/layout-data.md.
 */
import type {HDCountryInfo} from "../backendDataTypes";

export interface AssetRef {
    asset?: string;
}

/** A character as the state sends it: on a player, in a game or in a set's stats */
export interface CharacterRef {
    name?: string;
    display_name?: string;
    en_name?: string;
    codename?: string;
    skin?: number;
    assets?: Record<string, AssetRef | undefined>;
}

/** Characters by number, "1", "2"... */
export type CharacterMap = Record<string, CharacterRef | null | undefined>;

/** A person: a scoreboard player, a stream queue player or a commentator */
export interface Person {
    id?: unknown;
    name?: string;
    team?: string;
    real_name?: string;
    pronoun?: string;
    country?: HDCountryInfo & AssetRef;
    state?: {code?: string; name?: string} & AssetRef;
    city?: string;
    seed?: number;
    twitter?: string;
    socials?: Record<string, string>;
    online_avatar?: string;
    avatar?: string | null;
    character?: CharacterMap;
    custom?: Record<string, unknown>;
    custom_textbox?: string;
    wins?: number;
    losses?: number;
}

export interface Team {
    teamName?: string;
    score?: number;
    color?: string;
    losers?: boolean;
    seed?: number;
    player?: Record<string, Person>;
}

/** A set of a player's last sets in the event (score.N.last_sets.T) */
export interface LastSet {
    phase_id?: string;
    phase_name?: string;
    round_name?: string;
    player_score?: number | string;
    player_seed?: number;
    oponent_score?: number | string;
    oponent_seed?: number;
    oponent_team?: string;
    oponent_name?: string;
    player_char?: {character?: CharacterMap};
    oponent_char?: {character?: CharacterMap};
}

/** One of a player's past events (score.N.history_sets.T) */
export interface HistorySet {
    placement?: number;
    event_name?: string;
    tournament_name?: string;
    tournament_picture?: string | null;
    entrants?: number;
    seed?: number;
    spr?: number | null;
    event_date_month?: string;
    event_date_day?: string;
    event_date_year?: string;
}

/** A set between the two players (score.N.recent_sets.sets), from team 1's side */
export interface HeadToHeadSet {
    id?: unknown;
    tournament?: string;
    event?: string;
    online?: boolean;
    score?: [number, number];
    timestamp?: number;
    winner?: 0 | 1 | null;
    round?: string;
    phase_name?: string;
    phase_id?: string;
    p1_char?: {character?: CharacterMap};
    p2_char?: {character?: CharacterMap};
}

export interface SetGame {
    game?: number;
    winner?: 0 | 1 | 2 | null;
    stage?: string;
    stageData?: {name?: string; display_name?: string; en_name?: string} | null;
    characterData?: Record<string, (CharacterRef | null)[]>;
    scoreAfter?: Record<string, number> | null;
    current?: boolean;
}

export interface Scoreboard {
    phase?: string;
    match?: string;
    best_of?: number | string;
    best_of_text?: string;
    set_id?: unknown;
    station?: string | number;
    team?: Record<string, Team>;
    games?: Record<string, SetGame>;
    upset_factor?: number;
    recent_sets?: {state?: "loading" | "done"; sets?: HeadToHeadSet[]};
    last_sets?: Record<string, Record<string, LastSet> | undefined>;
    history_sets?: Record<string, Record<string, HistorySet> | undefined>;
}

export interface QueueSet {
    id?: unknown;
    queueKey: string;
    source?: "startgg" | "added" | "custom";
    position?: number;
    onStream?: boolean;
    match?: string;
    phase?: string;
    best_of_text?: string;
    station?: string | number;
    state?: number;
    eta?: number | null;
    eta_minutes?: number | null;
    team?: Record<string, Team>;
}

export interface QueueStream {
    name: string;
    manual?: boolean;
    scoreboard?: number | null;
    sets: QueueSet[];
}

export interface CompletedSetPlayer {
    sponsor?: string;
    gamertag?: string;
}

export interface CompletedSet {
    phase_name?: string;
    phase_id?: string;
    round_name?: string;
    winner_score?: number;
    loser_score?: number;
    winner_seed?: number;
    loser_seed?: number;
    winner_team?: Record<string, CompletedSetPlayer>;
    loser_team?: Record<string, CompletedSetPlayer>;
    winner_team_name?: string;
    loser_team_name?: string;
    upset_factor?: number;
}

export interface BracketSlot {
    id?: number;
    seed?: number;
    name?: string;
    bye?: boolean;
    pending?: boolean;
    source?: string;
}

export interface BracketSet {
    id: string;
    identifier?: string;
    side?: string;
    roundName?: string;
    players?: BracketSlot[];
    completed?: boolean;
    nextWin?: {set: string; slot: number} | null;
    nextLose?: {set: string; slot: number} | null;
    loserPlacement?: number | null;
    isGrandFinal?: boolean;
    isReset?: boolean;
    resetNeeded?: boolean;
    startggId?: unknown;
}

export interface Bracket {
    type?: string;
    name?: string;
    progressionsOut?: number;
    sets?: Record<string, BracketSet>;
}

export interface BracketChannel {
    bracket?: Bracket;
    phase?: string;
    phaseGroup?: string;
}

/** What the dashboard reads of the program state */
export interface DashboardState {
    score?: Record<string, Scoreboard>;
    stream_queue?: {
        streams?: QueueStream[];
        currentStream?: string;
        average_set_minutes?: number | null;
    };
    completed_sets?: Record<string, CompletedSet>;
    bracket?: {
        bracket?: Bracket;
        channels?: Record<string, BracketChannel>;
        phase?: string;
        phaseGroup?: string;
    };
    game?: {codename?: string; name?: string};
    tournamentInfo?: {
        tournamentName?: string;
        eventName?: string;
        numEntrants?: number;
        logo?: string;
    };
}

/** What /commentary-preview answers for a set's players */
export interface PreviewPlayer {
    avatar?: string | null;
    custom?: Record<string, unknown>;
    last_sets?: LastSet[] | null;
    history_sets?: HistorySet[] | null;
}

export interface PreviewResponse {
    stats: boolean;
    teams: PreviewPlayer[][];
    recent_sets: HeadToHeadSet[] | null;
}
