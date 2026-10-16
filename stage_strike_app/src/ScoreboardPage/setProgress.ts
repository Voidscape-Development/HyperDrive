import React from "react";
import i18n from "../i18n/config";
import type {HDScoreInfo, HDTeamInfo} from "../backendDataTypes";

/** The name shown for a team: its team name, or else its players' tags. */
export function teamDisplayName(team: HDTeamInfo, teamNumber: number) {
    if (team?.teamName) {
        return team.teamName;
    }
    const tags = Object.keys(team?.player ?? {})
        .sort((a, b) => Number(a) - Number(b))
        .map((k) => team.player[k]?.name)
        .filter(Boolean);
    return tags.length > 0 ? tags.join(" / ") : i18n.t("team_n", {value: teamNumber});
}

export interface SetProgress {
    bestOf: number;
    // Games needed to win the set, null when there's no best of
    firstTo: number | null;
    scores: [number, number];
    // 1 or 2 once a side has won the set
    winner: 1 | 2 | null;
    // The game being played
    game: number;
    // What's at stake in this game
    stakes: "playing" | "match_point" | "final_game" | "over";
    // The side on match point, when stakes is "match_point"
    matchPointTeam: 1 | 2 | null;
}

/** Where the set stands, from the scoreboard's score and best of. */
export function setProgress(score: HDScoreInfo): SetProgress {
    const bestOf = Number(score?.best_of) || 0;
    const firstTo = bestOf > 0 ? Math.floor(bestOf / 2) + 1 : null;
    const scores: [number, number] = [
        Number(score?.team?.["1"]?.score ?? 0),
        Number(score?.team?.["2"]?.score ?? 0),
    ];
    const winner = firstTo === null ? null
        : scores[0] >= firstTo ? 1
        : scores[1] >= firstTo ? 2
        : null;

    let stakes: SetProgress["stakes"] = "playing";
    let matchPointTeam: 1 | 2 | null = null;
    if (winner) {
        stakes = "over";
    } else if (firstTo !== null && firstTo > 1) {
        const onPoint = scores.map((s) => s === firstTo - 1);
        if (onPoint[0] && onPoint[1]) {
            stakes = "final_game";
        } else if (onPoint[0] || onPoint[1]) {
            stakes = "match_point";
            matchPointTeam = onPoint[0] ? 1 : 2;
        }
    }

    return {bestOf, firstTo, scores, winner, game: scores[0] + scores[1] + 1, stakes, matchPointTeam};
}

/** Whether a media query matches, following changes */
export function useMediaQuery(query: string) {
    const subscribe = React.useCallback((onChange: () => void) => {
        const list = window.matchMedia(query);
        list.addEventListener("change", onChange);
        return () => list.removeEventListener("change", onChange);
    }, [query]);
    return React.useSyncExternalStore(subscribe, () => window.matchMedia(query).matches);
}

/** Tailwind's lg breakpoint: the page shows the queue next to the scoreboard */
export const WIDE_SCREEN = "(min-width: 64rem)";
