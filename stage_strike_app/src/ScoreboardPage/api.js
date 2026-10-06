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

const call = (path, options) => track(
    fetch(BASE_URL + path, options).then((resp) => {
        if (!resp.ok) {
            throw new Error(`${path} returned ${resp.status}`);
        }
        return resp.text();
    })
);

const post = (path, body) => call(path, {
    method: 'POST',
    headers: {'content-type': 'application/json'},
    body: JSON.stringify(body),
});

const query = (params) => new URLSearchParams(
    Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null))
).toString();

export const api = {
    scoreUp: (sb, team) => call(`/scoreboard${sb}-team${team}-scoreup`),
    scoreDown: (sb, team) => call(`/scoreboard${sb}-team${team}-scoredown`),
    setScores: (sb, team1score, team2score) => post('/score', {scoreboard: sb, team1score, team2score}),

    /** @param {{bestOf?: number, phase?: string, match?: string, players?: number, characters?: number}} info */
    setInfo: (sb, {bestOf, phase, match, players, characters}) =>
        call(`/scoreboard${sb}-set?` + query({'best-of': bestOf, phase, match, players, characters})),

    /** @param {{name?: string, losers?: boolean, color?: string}} info */
    teamInfo: (sb, team, info) => post(`/scoreboard${sb}-team${team}-info`, info),

    updatePlayer: (sb, team, player, data) => post(`/scoreboard${sb}-update-team-${team}-${player}`, data),

    swapTeams: (sb) => call(`/scoreboard${sb}-swap-teams`),
    resetScores: (sb) => call(`/scoreboard${sb}-reset-scores`),
    clearAll: (sb) => call(`/scoreboard${sb}-clear-all`),
    pullStreamSet: (sb) => call(`/scoreboard${sb}-pull-stream`),
    loadSet: (sb, setId) => call(`/scoreboard${sb}-load-set?` + query({set: setId})),
};
