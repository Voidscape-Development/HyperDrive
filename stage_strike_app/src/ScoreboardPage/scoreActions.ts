import {toast} from "sonner";
import i18n from "../i18n/config";
import {api} from "./api";
import {setProgress, teamDisplayName} from "./setProgress";
import type {HDScoreInfo} from "../backendDataTypes";

// One toast for all score changes, so only the latest can be undone
const TOAST_ID = "scoreboard-undo";

function undoable(message: string, undo: () => Promise<unknown>) {
    toast(message, {
        id: TOAST_ID,
        duration: 6000,
        action: {
            label: i18n.t("undo"),
            onClick: () => {
                undo().catch(() => {});
            },
        },
    });
}

/**
 * The score changes made from the scoreboard page. Each one says what it did
 * in a toast that can undo it, so a big tap target can't cost a point.
 */
export function scoreActions(scoreboardNumber: number, score: HDScoreInfo) {
    const scores = [Number(score?.team?.["1"]?.score ?? 0), Number(score?.team?.["2"]?.score ?? 0)];
    const name = (team: 1 | 2) => teamDisplayName(score?.team?.[team], team);

    return {
        add: (team: 1 | 2) => {
            // Nothing more to score once the set is won
            if (setProgress(score).winner) {
                return Promise.resolve();
            }
            return api.scoreUp(scoreboardNumber, team).then(() => {
                undoable(i18n.t("point_to", {team: name(team)}),
                    () => api.scoreDown(scoreboardNumber, team));
            }).catch(() => {});
        },

        take: (team: 1 | 2) => {
            if (scores[team - 1] <= 0) {
                return Promise.resolve();
            }
            return api.scoreDown(scoreboardNumber, team).then(() => {
                undoable(i18n.t("point_taken", {team: name(team)}),
                    () => api.scoreUp(scoreboardNumber, team));
            }).catch(() => {});
        },

        reset: () => {
            const [was1, was2] = scores;
            return api.resetScores(scoreboardNumber).then(() => {
                undoable(i18n.t("score_was_reset"), () => api.setScores(scoreboardNumber, was1, was2));
            }).catch(() => {});
        },

        swap: () => api.swapTeams(scoreboardNumber).then(() => {
            undoable(i18n.t("sides_swapped"), () => api.swapTeams(scoreboardNumber));
        }).catch(() => {}),
    };
}
