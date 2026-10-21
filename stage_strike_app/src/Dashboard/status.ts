import React, {useSyncExternalStore} from "react";
import {dashboard, type DashboardStatus, type JobStatus} from "./api";

/*
 * What HyperDrive is doing that isn't in the program state: whether a
 * tournament is loaded, the completed sets' pulls, the scoreboards' names.
 * Asked for every few seconds while a page shows it, and asked again right
 * away after a change (refreshStatus).
 */

const POLL_MS = 3000;

let status: DashboardStatus | null = null;
// When status was received, for the countdowns
let receivedAt = 0;
const listeners = new Set<() => void>();
let timer: ReturnType<typeof setInterval> | null = null;

const notify = () => listeners.forEach((l) => l());

export function refreshStatus() {
    return dashboard.status().then((next) => {
        status = next;
        receivedAt = Date.now();
        notify();
    }).catch(() => {});
}

const subscribe = (listener: () => void) => {
    listeners.add(listener);
    if (!timer) {
        refreshStatus();
        timer = setInterval(() => {
            if (document.visibilityState === "visible") {
                refreshStatus();
            }
        }, POLL_MS);
    }
    return () => {
        listeners.delete(listener);
        if (listeners.size === 0 && timer) {
            clearInterval(timer);
            timer = null;
        }
    };
};

export function useStatus() {
    return useSyncExternalStore(subscribe, () => status);
}

/** Seconds until a job runs again, counting down between polls */
export function useCountdown(job: JobStatus | undefined) {
    const [, tick] = React.useReducer((n: number) => n + 1, 0);
    React.useEffect(() => {
        const id = setInterval(tick, 1000);
        return () => clearInterval(id);
    }, []);
    if (!job?.enabled || job.running || job.remainingMs == null) {
        return null;
    }
    return Math.max(0, Math.round((job.remainingMs - (Date.now() - receivedAt)) / 1000));
}
