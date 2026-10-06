import {BASE_URL} from "../env";

// Every stage strike action is for one scoreboard (?scoreboard=<n>), and
// from a page for one team (&team=<1|2>) or for both teams (no team).
// target is {scoreboard, team}.

function query(target) {
    const params = new URLSearchParams({scoreboard: String(target.scoreboard)});
    if (target.team) params.set("team", String(target.team));
    return params.toString();
}

function post(path, target, body) {
    return fetch(
        `${BASE_URL}/${path}?${query(target)}`,
        {
            method: "POST",
            headers: {"content-type": "application/json"},
            body: body === undefined ? undefined : JSON.stringify(body),
        }
    ).catch(console.error);
}

export function ConfirmClicked(target) {
    return post("stage_strike_confirm_clicked", target);
}

export function MatchWinner(target, id) {
    return post("stage_strike_match_win", target, {winner: id});
}

export function SetGentlemans(target, value) {
    return post("stage_strike_set_gentlemans", target, {value: value});
}

export function RestartStageStrike(target) {
    return post("stage_strike_reset", target);
}

export function StageClicked(target, /** object */ stage) {
    return post("stage_strike_stage_clicked", target, stage);
}

export function Undo(target) {
    return post("stage_strike_undo", target);
}

export function Redo(target) {
    return post("stage_strike_redo", target);
}

export function ReportRpsWin(target, /** number */ winner) {
    return post("stage_strike_rps_win", target, {winner: winner});
}

/**
 * Sends the characters picked for the next game. A page for one team only
 * sends its own; HyperDrive puts them on the scoreboard once both teams sent theirs.
 * @param {{scoreboard: number, team: number|null}} target
 * @param {Object<string, Object<string, Array<[string, number]>>>} characters
 *   {team: {player: [[character en_name, skin], ...]}}
 */
export function ReportCharacters(target, characters) {
    return fetch(
        `${BASE_URL}/stage_strike_report_characters?${query(target)}`,
        {
            method: "POST",
            headers: {"content-type": "application/json"},
            body: JSON.stringify({characters}),
        }
    );
}

/**
 * Sends the characters picked on the character select page. Like
 * ReportCharacters, but each team picks once per score: HyperDrive answers 409
 * until the score changes.
 * @param {{scoreboard: number, team: number|null}} target
 * @param {Object<string, Object<string, Array<[string, number]>>>} characters
 */
export function CharacterSelectReport(target, characters) {
    return fetch(
        `${BASE_URL}/character_select_report?${query(target)}`,
        {
            method: "POST",
            headers: {"content-type": "application/json"},
            body: JSON.stringify({characters}),
        }
    );
}
