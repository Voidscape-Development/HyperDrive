import {BASE_URL} from "../env";
import {ApiError} from "../Dashboard/api";
import {getToken, lock} from "../Dashboard/session";
import {getStationToken, lockStation} from "./stationSession";

/*
 * Calls from the reporting pages to HyperDrive (src/WebReporting.py):
 * /dashboard-api/reporting/... for the admin pages, behind the dashboard's
 * PIN, and /reporting-api/... for the players' reporting stations, behind
 * the station PIN. A station inside the dashboard uses the dashboard's.
 */

/** An error HyperDrive answered, with its message for people */
export class ReportingError extends ApiError {
    detail: string;

    constructor(status: number, code: string, detail: string) {
        super(status, code);
        this.detail = detail;
    }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const headers = new Headers(init?.headers);
    if (getToken()) {
        headers.set("X-Dashboard-Token", getToken());
    }
    if (getStationToken()) {
        headers.set("X-Station-Token", getStationToken());
    }
    let response: Response;
    try {
        response = await fetch(BASE_URL + path, {...init, headers});
    } catch {
        throw new ReportingError(0, "OFFLINE", "HyperDrive didn't answer. Is it running?");
    }
    const text = await response.text();
    let json: any = null;
    try {
        json = JSON.parse(text);
    } catch {
        // Plain text
    }
    if (response.status === 401) {
        if (path.startsWith("/dashboard-api/")) {
            lock();
        } else {
            lockStation();
        }
    }
    if (!response.ok) {
        const code = json?.error ?? json?.detail ?? text;
        throw new ReportingError(response.status, code, json?.message ?? errorText(code));
    }
    return (json ?? text) as T;
}

const errorText = (code: string) => ({
    PIN_REQUIRED: "Enter the dashboard PIN",
    STATION_PIN_REQUIRED: "Enter the station PIN",
} as Record<string, string>)[code] ?? `HyperDrive refused (${code})`;

/** What to tell people when a call failed */
export const errorMessage = (e: unknown) =>
    e instanceof ReportingError ? e.detail : e instanceof Error ? e.message : String(e);

const get = <T>(path: string) => request<T>(path);
const post = <T>(path: string, body: unknown = {}) => request<T>(path, {
    method: "POST",
    headers: {"content-type": "application/json"},
    body: JSON.stringify(body),
});

// =====================================================
// TYPES
// =====================================================
/** start.gg's set states */
export const NOT_STARTED = 1;
export const IN_PROGRESS = 2;
export const COMPLETED = 3;
export const CALLED = 6;

export interface Entrant {
    id: string | null;
    name: string;
}

export interface ReportingSet {
    id: string;
    identifier: string;
    round?: number | null;
    roundText: string;
    phase: string;
    phaseId?: string | null;
    phaseGroup: string;
    phaseGroupId?: string | null;
    state: number;
    bestOf: number | null;
    entrants: Entrant[];
    scores?: (number | null)[];
    winnerId?: string | null;
    station: {id: string; number: number | null} | null;
    stream: {id: string; name: string} | null;
    startedAt?: number | null;
    completedAt?: number | null;
    updatedAt?: number | null;
    pending: number;
}

/** A game: team 1 is the set's first player, team 2 the second */
export interface Game {
    winner: 1 | 2 | null;
    stage: string | null;
    characters: {"1"?: string[]; "2"?: string[]};
}

export interface Station {
    id: string;
    number: number | null;
    stream: string;
}

export interface Stream {
    id: string;
    name: string;
}

export interface SetsData {
    sets: ReportingSet[];
    stations: Station[];
    streams: Stream[];
    updatedAt: number | null;
    error: string;
    eventSlug: string;
    hasToken: boolean;
    refreshSecs: number;
}

export type Conflict = "completed" | "entrants_changed" | "duplicate" | "updated" | "missing";

export interface Submission {
    id: string;
    setId: string;
    set: ReportingSet;
    games: Game[];
    originalGames?: Game[];
    score: [number, number];
    winner: 1 | 2 | null;
    station: string;
    stationNumber: number | null;
    submitter: string;
    address: string;
    createdAt: number;
    status: "pending" | "approved" | "rejected" | "superseded";
    resolvedAt: number | null;
    resolvedBy: string;
    message: string;
    // Pending ones: the set as start.gg has it now, and what may be wrong
    current?: ReportingSet | null;
    conflicts?: Conflict[];
}

export interface LogEntry {
    time: number;
    action: string;
    setId: string | null;
    setName: string;
    round: string;
    by: string;
    submitter: string;
    ok: boolean;
    message: string;
    score: [number, number] | (number | null)[] | null;
}

export type SetAction = "call" | "start" | "reset" | "report" | "update" | "dq" | "assign-station" | "assign-stream";

export interface StationSets {
    sets: ReportingSet[];
    stations: Station[];
    updatedAt: number | null;
    error: string;
    refreshSecs: number;
}

export interface StationSubmit {
    setId: string;
    games: Game[];
    station?: string;
    stationNumber?: number | null;
    submitter?: string;
}

// =====================================================
// CALLS
// =====================================================
const a = (path: string) => `/dashboard-api/reporting${path}`;
const seg = encodeURIComponent;

export const reportingAdmin = {
    sets: (refresh = false) => get<SetsData>(a(`/sets${refresh ? "?refresh=1" : ""}`)),
    set: (id: string) => get<ReportingSet & {games: Game[]}>(a(`/sets/${seg(id)}`)),
    action: (id: string, action: SetAction, data: object = {}) =>
        post<{ok: boolean; set: ReportingSet}>(a(`/sets/${seg(id)}/${action}`), data),
    submissions: (status: "pending" | "all" = "pending") =>
        get<{submissions: Submission[]}>(a(`/submissions?status=${status}`)),
    approve: (id: string, data: {games?: Game[]; force?: boolean} = {}) =>
        post<{ok: boolean; set: ReportingSet}>(a(`/submissions/${seg(id)}/approve`), data),
    reject: (id: string, reason = "") => post<{ok: boolean}>(a(`/submissions/${seg(id)}/reject`), {reason}),
    log: () => get<{log: LogEntry[]}>(a("/log")),
};

/** The reporting station's calls: on its own page, or inside the dashboard */
export interface StationApi {
    sets: () => Promise<StationSets>;
    submit: (data: StationSubmit) => Promise<{ok: boolean; id: string; score: [number, number]}>;
}

export const stationApi: StationApi = {
    sets: () => get<StationSets>("/reporting-api/sets"),
    submit: (data) => post("/reporting-api/submissions", data),
};

export const dashboardStationApi: StationApi = {
    sets: () => get<StationSets>(a("/station/sets")),
    submit: (data) => post(a("/station/submissions"), data),
};

export const stationSession = {
    session: () => get<{pinRequired: boolean; unlocked: boolean; enabled: boolean}>("/reporting-api/session"),
    unlock: (pin: string) => post<{token: string}>("/reporting-api/unlock", {pin}),
};
