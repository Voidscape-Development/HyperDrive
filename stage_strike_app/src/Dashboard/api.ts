import {BASE_URL} from "../env";
import {track} from "../ScoreboardPage/saveStatus";
import {getToken, lock} from "./session";

/*
 * Calls from the dashboard to HyperDrive. /dashboard-api/... is the
 * dashboard's own API (src/WebDashboard.py), which needs the PIN token when
 * a PIN is set. A few changes use the endpoints HyperDrive already had for
 * a Stream Deck or the other web pages.
 *
 * Changes go through track(), so the pages can show whether they were saved.
 */

export class ApiError extends Error {
    status: number;
    code: string;

    constructor(status: number, code: string) {
        super(code || `HTTP ${status}`);
        this.status = status;
        this.code = code;
    }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const headers = new Headers(init?.headers);
    if (getToken()) {
        headers.set("X-Dashboard-Token", getToken());
    }
    const response = await fetch(BASE_URL + path, {...init, headers});
    const text = await response.text();
    if (response.status === 401 && path.startsWith("/dashboard-api/")) {
        lock();
    }
    if (!response.ok) {
        let code = text;
        try {
            code = JSON.parse(text)?.error ?? JSON.parse(text)?.detail ?? text;
        } catch {
            // Plain text
        }
        throw new ApiError(response.status, code);
    }
    try {
        return JSON.parse(text) as T;
    } catch {
        return text as T;
    }
}

export const get = <T>(path: string) => request<T>(path);

const send = <T = string>(method: string, path: string, body?: unknown) => track(request<T>(path, {
    method,
    headers: {"content-type": "application/json"},
    body: body === undefined ? undefined : JSON.stringify(body),
}));

export const post = <T = string>(path: string, body?: unknown) => send<T>("POST", path, body ?? {});
export const del = <T = string>(path: string) => send<T>("DELETE", path);
// The older endpoints that change things on a GET
export const getAction = (path: string) => track(request<string>(path));

const d = (path: string) => `/dashboard-api${path}`;
const seg = (value: string) => encodeURIComponent(value);

// =====================================================
// TYPES
// =====================================================
export interface JobStatus {
    enabled: boolean;
    running: boolean;
    remainingMs: number | null;
}

export interface DashboardStatus {
    tournament: {loaded: boolean; url: string | null; host: string | null; provider: string | null};
    completedSets: JobStatus & {supported: boolean; autoPull: boolean};
    scoreboards: {number: number; name: string}[];
    pinSet: boolean;
}

export interface TournamentEvent {
    name: string;
    url: string;
    numEntrants?: number;
    game?: string;
    startAt?: number;
    state?: string;
    location?: string;
}

export interface TournamentEvents {
    error?: string;
    message?: string;
    provider?: string;
    tournamentName?: string;
    tournamentUrl?: string;
    events?: TournamentEvent[];
    selectedEventUrl?: string;
}

export interface Theme {
    dark: boolean;
    radius: number;
    colors: Record<string, string>;
}

export interface StreamQueueOptions {
    afterSet: "nothing" | "ask" | "load_next";
    autoAdd: boolean;
    autoRefresh: boolean;
    interval: number;
    lastUpdated: number | null;
}

export interface PlayerListOptions {
    slots: number;
    playersPerSlot: number;
    charactersPerPlayer: number;
    showScores: boolean;
}

export interface ResultsText {
    text: string;
    options: Record<string, string | boolean>;
}

export interface TeamBattleOptions {
    mode: "STOCK_POOL" | "FIRST_TO";
    players: number;
    characters: number;
    battleValue: number;
    autoAdvance: boolean;
}

export interface BracketOptions {
    channels: {name: string; phase: string | null; limit: number | null}[];
    phases: {id: string; name: string; type: string; fromProvider: boolean}[];
    sources: {index: number; name: string; groups: {index: number; name: string; bracketType: string}[]}[];
    loaded: boolean;
    fetching: boolean;
    autoUpdate: JobStatus;
}

// =====================================================
// CALLS
// =====================================================
export const dashboard = {
    session: () => get<{pinRequired: boolean; unlocked: boolean}>(d("/session")),
    unlock: (pin: string) => request<{token: string}>(d("/unlock"), {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({pin}),
    }),
    theme: () => get<Theme>(d("/theme")),
    status: () => get<DashboardStatus>(d("/status")),

    tournament: {
        load: (url: string) => post(d("/tournament/load"), {url}),
        events: (url?: string) => get<TournamentEvents>(d("/tournament/events") + (url ? `?url=${seg(url)}` : "")),
        unload: () => post(d("/tournament/unload")),
        repull: () => post(d("/tournament/repull")),
    },
    game: (codename: string, modsActive = false) => post(d("/game"), {codename, mods_active: modsActive}),

    completedSets: {
        auto: (enabled: boolean) => post(d("/completed-sets/auto"), {enabled}),
        pull: () => post(d("/completed-sets/pull")),
    },

    scoreboards: {
        add: () => post<{amount: number}>(d("/scoreboards/add")),
        remove: () => post<{amount: number}>(d("/scoreboards/remove")),
        rename: (n: number, name: string) => post(d(`/scoreboards/${n}/name`), {name}),
        stopTracking: (n: number) => post(d(`/scoreboards/${n}/stop-tracking`)),
    },

    display: {
        set: (kind: "folder" | "group", name: string, action: "show" | "hide" | "toggle") =>
            getAction(`/display/${kind}/${seg(name)}/${action}`),
        all: (action: "show" | "hide") => getAction(`/display/all/${action}`),
        addGroup: (name: string) => post(d("/display/groups"), {name}),
        removeGroup: (name: string) => del(d(`/display/groups/${seg(name)}`)),
        refreshFolders: () => post(d("/display/refresh-folders")),
    },

    streamQueue: {
        options: () => get<StreamQueueOptions>(d("/stream-queue/options")),
        setOptions: (options: Partial<StreamQueueOptions>) => post(d("/stream-queue/options"), options),
        refresh: () => post(d("/stream-queue/refresh")),
        addStream: (name: string) => post(d("/stream-queue/streams"), {name}),
        removeStream: (name: string) => del(d(`/stream-queue/streams/${seg(name)}`)),
        setScoreboard: (stream: string, scoreboard: number | null) =>
            post(d(`/stream-queue/streams/${seg(stream)}/scoreboard`), {scoreboard}),
        edit: (stream: string, action: "move" | "move-to" | "remove" | "reset" | "add-set" | "add-custom" | "load" | "load-next", data: object = {}) =>
            post(d(`/stream-queue/streams/${seg(stream)}/${action}`), data),
    },

    tournamentInfo: {
        set: (fields: Record<string, string | number>) => post(d("/tournament-info"), fields),
        action: (action: "load" | "clear" | "download-icon" | "default-icon") => post(d(`/tournament-info/${action}`)),
    },

    commentary: {
        options: () => get<{commentators: number; characters: number}>(d("/commentary/options")),
        setOptions: (options: {commentators?: number; characters?: number}) => post(d("/commentary/options"), options),
        // The endpoint the Stream Deck plugin uses
        setData: (n: number, data: unknown) => post(`/update-commentary-${n}`, data),
    },

    playerList: {
        options: () => get<PlayerListOptions>(d("/player-list/options")),
        setOptions: (options: Partial<PlayerListOptions>) => post(d("/player-list/options"), options),
        loadStandings: () => post(d("/player-list/load-standings")),
        setSlot: (n: number, data: {name?: string; score?: number}) => post(d(`/player-list/slots/${n}`), data),
        setPlayer: (n: number, player: number, data: unknown) => post(d(`/player-list/slots/${n}/players/${player}`), data),
        results: (mode: "simple" | "template") => get<ResultsText>(d(`/player-list/results?mode=${mode}`)),
        setResultsOptions: (data: {options?: Record<string, string | boolean>; resetTemplates?: boolean}) =>
            post(d("/player-list/results"), data),
    },

    teamBattle: {
        options: () => get<TeamBattleOptions>(d("/team-battle/options")),
        setOptions: (options: Partial<TeamBattleOptions>) => post(d("/team-battle/options"), options),
        setTeam: (team: number, data: {name: string}) => post(d(`/team-battle/teams/${team}`), data),
        setPlayer: (team: number, player: number, data: unknown) => post(d(`/team-battle/teams/${team}/players/${player}`), data),
        // The endpoints the Stream Deck plugin uses
        scoreUp: (team: number) => getAction(`/team-battle-team${team}-scoreup`),
        scoreDown: (team: number) => getAction(`/team-battle-team${team}-scoredown`),
        setActive: (team: number, player: number) => getAction(`/team-battle-team${team}-player${player}-active`),
        resetStocks: () => getAction("/team-battle-reset-stocks"),
        reset: () => getAction("/team-battle-reset"),
    },

    bracket: {
        options: () => get<BracketOptions>(d("/bracket/options")),
        setChannel: (name: string, data: {phase?: string; limit?: number | null}) => post(d(`/bracket/channels/${seg(name)}`), data),
        updateSets: () => post(d("/bracket/update-sets")),
        autoUpdate: (enabled: boolean) => post(d("/bracket/auto-update"), {enabled}),
        load: (phase: number, group: number) => post(d("/bracket/load"), {phase, group}),
    },
};
