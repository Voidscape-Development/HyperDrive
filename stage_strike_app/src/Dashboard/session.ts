import {useSyncExternalStore} from "react";

/*
 * The dashboard's PIN session. When HyperDrive has a dashboard PIN, the
 * browser trades it for a token (see src/WebDashboard.py) and keeps it, so
 * the PIN is asked once per browser. A request answered 401 means the token
 * is no longer good (the PIN changed): the page locks itself again.
 */

const TOKEN_KEY = "hyperdrive-dashboard-token";

// Storage can be unavailable (private windows, blocked site data)
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

export const getToken = () => token;

export function setToken(value: string) {
    token = value;
    write(TOKEN_KEY, value || null);
    locked = false;
    notify();
}

/** Forgets the token: the PIN is asked again. */
export function lock() {
    token = "";
    write(TOKEN_KEY, null);
    locked = true;
    notify();
}

export function setLocked(value: boolean) {
    locked = value;
    notify();
}

const subscribe = (listener: () => void) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
};

export function useLocked() {
    return useSyncExternalStore(subscribe, () => locked);
}
