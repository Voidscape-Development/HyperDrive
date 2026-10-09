/**
 * The web server's links the actions use (see src/WebServer.py, or
 * /api/docs on a running HyperDrive). Teams are 1 (left) or 2 (right).
 */

import type { DisplayTarget } from "./state.ts";

export type Request = { path: string; method?: "GET" | "POST"; body?: unknown };

const enc = encodeURIComponent;

export type ResetKind = "scores" | "match" | "players" | "all";

export const scoreboard = {
	scoreUp: (sb: number, team: number): Request => ({ path: `/scoreboard${sb}-team${team}-scoreup` }),
	scoreDown: (sb: number, team: number): Request => ({ path: `/scoreboard${sb}-team${team}-scoredown` }),
	swapTeams: (sb: number): Request => ({ path: `/scoreboard${sb}-swap-teams` }),
	/** "#rrggbb" */
	teamColor: (sb: number, team: number, color: string): Request => ({
		path: `/scoreboard${sb}-team${team}-color-${color.replace(/^#/, "")}`,
	}),
	reset: (sb: number, kind: ResetKind): Request => ({
		path: `/scoreboard${sb}-${{ scores: "reset-scores", match: "reset-match", players: "reset-players", all: "clear-all" }[kind]}`,
	}),
	/** The set on stream from start.gg */
	pullStreamSet: (sb: number): Request => ({ path: `/scoreboard${sb}-pull-stream` }),
	/** The next set of the stream queue showing on this scoreboard */
	loadNextQueued: (sb: number): Request => ({ path: `/stream-queue/load-next?scoreboard=${sb}` }),
	/** Opens the set selection window in HyperDrive */
	openSetSelector: (sb: number): Request => ({ path: `/scoreboard${sb}-open-set` }),
};

export const display = {
	set: (target: DisplayTarget, action: "show" | "hide" | "toggle"): Request => ({
		path:
			target.kind === "all"
				? `/display/all/${action}`
				: `/display/${target.kind}/${enc(target.name ?? "")}/${action}`,
	}),
};

export const teamBattle = {
	scoreUp: (team: number): Request => ({ path: `/team-battle-team${team}-scoreup` }),
	scoreDown: (team: number): Request => ({ path: `/team-battle-team${team}-scoredown` }),
	nextPlayer: (team: number): Request => ({ path: `/team-battle-team${team}-next-player` }),
	/** player: from 1 */
	setActive: (team: number, player: number): Request => ({ path: `/team-battle-team${team}-player${player}-active` }),
	resetStocks: (): Request => ({ path: "/team-battle-reset-stocks" }),
	reset: (): Request => ({ path: "/team-battle-reset" }),
};

export type StrikeCommand = "undo" | "redo" | "reset" | "rps" | "win";

export const stageStrike = {
	/** team: the winner, for "rps" and "win" */
	run: (sb: number, command: StrikeCommand, team?: number): Request => {
		const body: Record<string, unknown> = { scoreboardNumber: sb };
		if (command === "rps" || command === "win") {
			// The stage strike's players are 0 (left) and 1 (right)
			body.winner = (team ?? 1) - 1;
		}
		const path = {
			undo: "/stage_strike_undo",
			redo: "/stage_strike_redo",
			reset: "/stage_strike_reset",
			rps: "/stage_strike_rps_win",
			win: "/stage_strike_match_win",
		}[command];
		return { path, method: "POST", body };
	},
};

export type FocusMode = "all" | "next-round" | "previous-round" | "follow" | "tour" | "player";

export const bracketFocus = {
	set: (
		mode: FocusMode,
		options: { channel?: string; scoreboard?: number; interval?: number; player?: string } = {},
	): Request => {
		const params = new URLSearchParams();
		if (mode === "follow") params.set("scoreboard", String(options.scoreboard ?? 1));
		if (mode === "tour" && options.interval) params.set("interval", String(options.interval));
		if (mode === "player" && options.player) params.set("id", options.player);
		if (options.channel && options.channel !== "main") params.set("channel", options.channel);
		const query = params.toString();
		return { path: `/bracket-focus/${mode}${query ? `?${query}` : ""}` };
	},
	/** What can be picked: the rounds, sets and players */
	state: (channel?: string): Request => ({
		path: `/bracket-focus${channel && channel !== "main" ? `?channel=${enc(channel)}` : ""}`,
	}),
};
