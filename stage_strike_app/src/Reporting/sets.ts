import {CALLED, COMPLETED, IN_PROGRESS, NOT_STARTED, type Game, type ReportingSet} from "./api";

/*
 * Showing sets and their games the same way on every reporting page.
 */

export const STATE_INFO: Record<number, {label: string; className: string}> = {
    [NOT_STARTED]: {label: "Not started", className: "text-muted-foreground"},
    [CALLED]: {label: "Called", className: "text-sky-400"},
    [IN_PROGRESS]: {label: "In progress", className: "text-live"},
    [COMPLETED]: {label: "Completed", className: "text-muted-foreground"},
};

export const stateInfo = (state: number) => STATE_INFO[state] ?? STATE_INFO[NOT_STARTED];

export const entrantName = (set: ReportingSet, team: 1 | 2) =>
    set.entrants[team - 1]?.name || (set.entrants[team - 1]?.id ? "?" : "To be decided");

export const setTitle = (set: ReportingSet) => `${entrantName(set, 1)} vs ${entrantName(set, 2)}`;

/** "Pools A1 · Winners Round 1 · Set C" */
export function setPlace(set: ReportingSet) {
    const pool = [set.phase, set.phaseGroup && set.phaseGroup !== "1" ? set.phaseGroup : ""].filter(Boolean).join(" ");
    return [pool, set.roundText, set.identifier ? `Set ${set.identifier}` : ""].filter(Boolean).join(" · ");
}

export const isReady = (set: ReportingSet) => set.entrants.every((e) => e.id);

/** The set's score on start.gg, e.g. "2 – 1", or "" */
export function startggScore(set: ReportingSet) {
    const [a, b] = set.scores ?? [];
    if (a == null && b == null) {
        if (set.state === COMPLETED && set.winnerId) {
            return set.winnerId === set.entrants[0]?.id ? "W – DQ" : "DQ – W";
        }
        return "";
    }
    return `${a ?? 0} – ${b ?? 0}`;
}

export const winnerTeam = (set: ReportingSet): 1 | 2 | null =>
    !set.winnerId ? null : set.winnerId === set.entrants[0]?.id ? 1 : set.winnerId === set.entrants[1]?.id ? 2 : null;

/** Wins needed to take the set, from start.gg's best of (3 if unknown) */
export const winsNeeded = (bestOf: number | null | undefined) => Math.ceil((bestOf && bestOf > 0 ? bestOf : 3) / 2);

export function gamesScore(games: Game[]): [number, number] {
    const score: [number, number] = [0, 0];
    for (const g of games) {
        if (g.winner === 1 || g.winner === 2) {
            score[g.winner - 1] += 1;
        }
    }
    return score;
}

export function gamesWinner(games: Game[]): 1 | 2 | null {
    const [a, b] = gamesScore(games);
    return a === b ? null : a > b ? 1 : 2;
}

export const emptyGame = (): Game => ({winner: null, stage: null, characters: {}});

/** Games played, without the empty ones at the end */
export function playedGames(games: Game[]): Game[] {
    const result = [...games];
    while (result.length && result[result.length - 1].winner == null) {
        result.pop();
    }
    return result;
}

/**
 * Games for a final score, e.g. 2–1: the teams take turns until the loser's
 * wins run out, so the set's winner takes the last game. Characters and
 * stages already set on those games are kept.
 */
export function gamesForScore(score: [number, number], previous: Game[] = []): Game[] {
    const winner: 1 | 2 = score[0] >= score[1] ? 1 : 2;
    const loser: 1 | 2 = winner === 1 ? 2 : 1;
    const winners: (1 | 2)[] = [];
    for (let i = 0; i < score[loser - 1]; i++) {
        winners.push(winner, loser);
    }
    while (winners.filter((w) => w === winner).length < score[winner - 1]) {
        winners.push(winner);
    }
    return winners.map((w, i) => ({...(previous[i] ?? emptyGame()), winner: w}));
}

/** Scores a set can end on, for a best of: 2–0, 2–1, 1–2, 0–2 for a best of 3 */
export function finalScores(bestOf: number | null | undefined): [number, number][] {
    const needed = winsNeeded(bestOf);
    const scores: [number, number][] = [];
    for (let l = 0; l < needed; l++) {
        scores.push([needed, l]);
    }
    for (let l = needed - 1; l >= 0; l--) {
        scores.push([l, needed]);
    }
    return scores;
}

export function timeAgo(seconds: number | null | undefined) {
    if (!seconds) {
        return "";
    }
    const ago = Math.max(0, Math.round(Date.now() / 1000 - seconds));
    if (ago < 60) {
        return "just now";
    }
    if (ago < 3600) {
        return `${Math.round(ago / 60)} min ago`;
    }
    if (ago < 86400) {
        return `${Math.round(ago / 3600)} h ago`;
    }
    return new Date(seconds * 1000).toLocaleDateString();
}

export const clockTime = (seconds: number) =>
    new Date(seconds * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});

/** Matches a search: a player's name, a set's identifier ("C", "A1 C") or a station number */
export function matchesSearch(set: ReportingSet, search: string) {
    const q = search.trim().toLowerCase();
    if (!q) {
        return true;
    }
    if (set.entrants.some((e) => e.name.toLowerCase().includes(q))) {
        return true;
    }
    const code = q.replace(/^set\s+/, "").replace(/\s+/g, "");
    const id = set.identifier.toLowerCase();
    return Boolean(id) && (code === id || code === `${set.phaseGroup.toLowerCase()}${id}`);
}
