import {BASE_URL} from "../env";
import {track} from "./saveStatus";

/*
 * Calls to HyperDrive for the remote scoreboard. Teams are always in on-screen
 * order: team 1 is the left side of the scoreboard, even while the teams
 * are swapped.
 *
 * Every call goes through track() so the header can show whether changes
 * were saved.
 */

const call = (path: string, options?: RequestInit) => track(
    fetch(BASE_URL + path, options).then((resp) => {
        if (!resp.ok) {
            throw new Error(`${path} returned ${resp.status}`);
        }
        return resp.text();
    })
);

const post = (path: string, body: unknown) => call(path, {
    method: 'POST',
    headers: {'content-type': 'application/json'},
    body: JSON.stringify(body),
});

const query = (params: Record<string, unknown>) => new URLSearchParams(
    Object.fromEntries(Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null)
        .map(([k, v]) => [k, String(v)]))
).toString();

type Team = number | string;

export const api = {
    scoreUp: (sb: number, team: Team) => call(`/scoreboard${sb}-team${team}-scoreup`),
    scoreDown: (sb: number, team: Team) => call(`/scoreboard${sb}-team${team}-scoredown`),
    setScores: (sb: number, team1score: number, team2score: number) => post('/score', {scoreboard: sb, team1score, team2score}),

    setInfo: (sb: number, {bestOf, phase, match, players, characters}: {
        bestOf?: number, phase?: string, match?: string, players?: number, characters?: number,
    }) =>
        call(`/scoreboard${sb}-set?` + query({'best-of': bestOf, phase, match, players, characters})),

    teamInfo: (sb: number, team: Team, info: {name?: string, losers?: boolean, color?: string}) => post(`/scoreboard${sb}-team${team}-info`, info),

    updatePlayer: (sb: number, team: Team, player: Team, data: unknown) => post(`/scoreboard${sb}-update-team-${team}-${player}`, data),

    swapTeams: (sb: number) => call(`/scoreboard${sb}-swap-teams`),
    resetScores: (sb: number) => call(`/scoreboard${sb}-reset-scores`),
    clearAll: (sb: number) => call(`/scoreboard${sb}-clear-all`),
    pullStreamSet: (sb: number) => call(`/scoreboard${sb}-pull-stream`),
    loadSet: (sb: number, setId: number) => call(`/scoreboard${sb}-load-set?` + query({set: setId})),
};
