import {useSyncExternalStore} from "react";

/*
 * Keeps count of the requests sent to HyperDrive so the page can say whether the
 * changes made here have been saved.
 *
 * Status: "idle" (nothing sent yet), "saving", "saved" or "error" (the last
 * request failed).
 */

let pending = 0;
let failed = false;
let used = false;
const listeners = new Set();

const notify = () => listeners.forEach((l) => l());

export function track(promise) {
    pending += 1;
    used = true;
    notify();
    return promise.then(
        (result) => {
            pending -= 1;
            failed = false;
            notify();
            return result;
        },
        (error) => {
            pending -= 1;
            failed = true;
            notify();
            console.error(error);
            throw error;
        }
    );
}

const status = () => (
    pending > 0 ? "saving"
        : failed ? "error"
        : used ? "saved"
        : "idle"
);

const subscribe = (listener) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
};

export function useSaveStatus() {
    return useSyncExternalStore(subscribe, status);
}
