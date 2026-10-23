import {useSyncExternalStore} from "react";

/*
 * A reporting station's PIN token, and what the station is: its name (shown
 * to the admins with each result) and the start.gg station it stands at, if
 * any. All kept in the browser, so a tablet is set up once.
 */

const TOKEN_KEY = "hyperdrive-station-token";
const CONFIG_KEY = "hyperdrive-station-config";

const read = (key: string) => {
    try {
        return window.localStorage.getItem(key);
    } catch {
        return null;
    }
};

const write = (key: string, value: string | null) => {
    try {
        if (value === null) {
            window.localStorage.removeItem(key);
        } else {
            window.localStorage.setItem(key, value);
        }
    } catch {
        // Kept for this page only
    }
};

let token = read(TOKEN_KEY) ?? "";
// "unknown" until HyperDrive says whether a PIN is needed
let locked: boolean | "unknown" = "unknown";
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((l) => l());
const subscribe = (listener: () => void) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
};

export const getStationToken = () => token;

export function setStationToken(value: string) {
    token = value;
    write(TOKEN_KEY, value || null);
    locked = false;
    notify();
}

/** Forgets the token: the PIN is asked again. */
export function lockStation() {
    token = "";
    write(TOKEN_KEY, null);
    locked = true;
    notify();
}

export function setStationLocked(value: boolean) {
    locked = value;
    notify();
}

export function useStationLocked() {
    return useSyncExternalStore(subscribe, () => locked);
}

// =====================================================
// THE STATION
// =====================================================
export interface StationConfig {
    // Shown to the admins, e.g. "TO desk" or "Station 3"
    name: string;
    // The start.gg station number whose sets are shown first, or null
    number: number | null;
}

function readConfig(): StationConfig {
    let saved: Partial<StationConfig> = {};
    try {
        saved = JSON.parse(read(CONFIG_KEY) ?? "{}") ?? {};
    } catch {
        // Defaults
    }
    // ?station=5 and ?name=... set it up from a link (e.g. a QR code)
    const params = new URLSearchParams(window.location.search);
    const fromLink = Number(params.get("station"));
    const config: StationConfig = {
        name: params.get("name") ?? (typeof saved.name === "string" ? saved.name : ""),
        number: params.has("station") && Number.isFinite(fromLink) && fromLink > 0
            ? fromLink
            : typeof saved.number === "number" ? saved.number : null,
    };
    if (params.has("station") || params.has("name")) {
        write(CONFIG_KEY, JSON.stringify(config));
    }
    return config;
}

let config = readConfig();

export function setStationConfig(value: StationConfig) {
    config = value;
    write(CONFIG_KEY, JSON.stringify(value));
    notify();
}

export function useStationConfig() {
    return useSyncExternalStore(subscribe, () => config);
}
