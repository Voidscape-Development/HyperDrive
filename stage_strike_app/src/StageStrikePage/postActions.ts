import {BASE_URL} from "../env";
import type {CharacterPicks} from "./CharacterReportDialog";
import type {Stage} from "./strikeLogic";

// Every stage strike action is for one scoreboard (?scoreboard=<n>), and
// from a page for one team (&team=<1|2>) or for both teams (no team).
export interface StrikeTarget {
    scoreboard: number;
    team: number | null;
}

function query(target: StrikeTarget) {
    const params = new URLSearchParams({scoreboard: String(target.scoreboard)});
    if (target.team) params.set("team", String(target.team));
    return params.toString();
}

function post(path: string, target: StrikeTarget, body?: unknown) {
    return fetch(
        `${BASE_URL}/${path}?${query(target)}`,
        {
            method: "POST",
            headers: {"content-type": "application/json"},
            body: body === undefined ? undefined : JSON.stringify(body),
        }
    ).catch(console.error);
}

export function ConfirmClicked(target: StrikeTarget) {
    return post("stage_strike_confirm_clicked", target);
}

export function MatchWinner(target: StrikeTarget, id: number) {
    return post("stage_strike_match_win", target, {winner: id});
}

export function SetGentlemans(target: StrikeTarget, value: boolean) {
    return post("stage_strike_set_gentlemans", target, {value: value});
}

export function RestartStageStrike(target: StrikeTarget) {
    return post("stage_strike_reset", target);
}

export function StageClicked(target: StrikeTarget, stage: Stage) {
    return post("stage_strike_stage_clicked", target, stage);
}

export function Undo(target: StrikeTarget) {
    return post("stage_strike_undo", target);
}

export function Redo(target: StrikeTarget) {
    return post("stage_strike_redo", target);
}

export function ReportRpsWin(target: StrikeTarget, winner: number) {
    return post("stage_strike_rps_win", target, {winner: winner});
}

/**
 * Sends the characters picked for the next game. A page for one team only
 * sends its own; HyperDrive puts them on the scoreboard once both teams sent theirs.
 */
export function ReportCharacters(target: StrikeTarget, characters: CharacterPicks) {
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
 */
export function CharacterSelectReport(target: StrikeTarget, characters: CharacterPicks) {
    return fetch(
        `${BASE_URL}/character_select_report?${query(target)}`,
        {
            method: "POST",
            headers: {"content-type": "application/json"},
            body: JSON.stringify({characters}),
        }
    );
}
