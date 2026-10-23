import React from "react";
import {errorMessage, ReportingError, type ReportingSet} from "./api";

/*
 * Sets loaded from HyperDrive and asked for again every refreshSecs (what
 * HyperDrive answers, from Settings > Web Reporting) while the page is
 * visible. A set changed from the page shows its change right away.
 */
export function usePolledSets<T extends {sets: ReportingSet[]; refreshSecs?: number}>(load: (refresh: boolean) => Promise<T>) {
    const [data, setData] = React.useState<T | null>(null);
    const [error, setError] = React.useState<{code: string; message: string} | null>(null);
    const [loading, setLoading] = React.useState(false);
    const loadRef = React.useRef(load);
    loadRef.current = load;

    const reload = React.useCallback((refresh = false) => {
        setLoading(true);
        return loadRef.current(refresh)
            .then((next) => {
                setData(next);
                setError(null);
            })
            .catch((e) => setError({code: e instanceof ReportingError ? e.code : "", message: errorMessage(e)}))
            .finally(() => setLoading(false));
    }, []);

    const refreshSecs = data?.refreshSecs ?? 30;
    React.useEffect(() => {
        reload();
    }, [reload]);
    React.useEffect(() => {
        const id = setInterval(() => {
            if (document.visibilityState === "visible") {
                reload();
            }
        }, Math.max(5, refreshSecs) * 1000);
        const onVisible = () => document.visibilityState === "visible" && reload();
        document.addEventListener("visibilitychange", onVisible);
        return () => {
            clearInterval(id);
            document.removeEventListener("visibilitychange", onVisible);
        };
    }, [reload, refreshSecs]);

    /** A set changed from here */
    const applySet = React.useCallback((set: ReportingSet) => {
        setData((was) => was && {
            ...was,
            sets: was.sets.map((s) => (s.id === set.id ? {...s, ...set, pending: set.pending ?? s.pending} : s)),
        });
    }, []);

    return {data, error, loading, reload, applySet};
}
