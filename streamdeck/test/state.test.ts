import { describe, expect, it } from "vitest";

import { bracketFocus as focusLinks, display, scoreboard, stageStrike } from "../src/hyperdrive/commands.ts";
import { parseAddress } from "../src/hyperdrive/connection.ts";
import {
	applyDeltas,
	displayShown,
	displayTargets,
	formatDisplayTarget,
	nextQueuedSet,
	parseDisplayTarget,
	scoreboardNumbers,
	scoreboardTeam,
	teamBattleTeam,
	type State,
} from "../src/hyperdrive/state.ts";

function sampleState(): State {
	return {
		score: {
			"1": {
				best_of: 5,
				teamsSwapped: false,
				team: {
					"1": { score: 2, color: "#e54c4c", teamName: "", player: { "1": { name: "Alice" } } },
					"2": { score: 1, color: "#2e89ff", teamName: "Team B", player: { "1": { name: "Bob" } } },
				},
			},
			"2": { team: {} },
			ruleset: {},
		},
		display: { folders: { scoreboard: true, bracket: false }, groups: { main: true } },
		team_battle: {
			battle_mode: "STOCK_POOL",
			battle_value: 3,
			"team1_spinner-total": 5,
			team: {
				"1": {
					sponsor: "Crew A",
					color: "#ff0000",
					active_player: 2,
					player: {
						"1": { name: "A1", dynamic_spinner: 0, dead: true },
						"2": { name: "A2", dynamic_spinner: 2, active: true },
						"3": { name: "A3", dynamic_spinner: 3 },
					},
				},
			},
		},
		stream_queue: {
			streams: [
				{
					name: "main",
					scoreboard: 1,
					sets: [
						{ onStream: true, team: { "1": { player: { "1": { name: "Alice" } } } } },
						{
							onStream: false,
							team: {
								"1": { teamName: "", player: { "1": { name: "Carol" } } },
								"2": { player: { "1": { name: "Dan" }, "2": { name: "Eve" } } },
							},
						},
					],
				},
			],
		},
	};
}

describe("deltas", () => {
	it("sets, adds and removes keys like the layouts do", () => {
		const state = sampleState();
		applyDeltas(state, [
			{ path: ["score", "1", "team", "1", "score"], action: "values_changed", value: 3 },
			{ path: ["score", "3", "team", "1", "score"], action: "dictionary_item_added", value: 0 },
			{ path: ["display", "groups", "main"], action: "dictionary_item_removed" },
		]);
		expect(state.score["1"].team["1"].score).toBe(3);
		expect(state.score["3"].team["1"].score).toBe(0);
		expect(state.display.groups).toEqual({});
	});

	it("replaces a value that isn't an object on the way", () => {
		const state: State = { a: null };
		applyDeltas(state, [{ path: ["a", "b"], action: "dictionary_item_added", value: 1 }]);
		expect(state).toEqual({ a: { b: 1 } });
	});
});

describe("scoreboard", () => {
	it("lists the numbered scoreboards only", () => {
		expect(scoreboardNumbers(sampleState())).toEqual([1, 2]);
	});

	it("names a team after its team name, or its players", () => {
		const state = sampleState();
		expect(scoreboardTeam(state, 1, 1)).toEqual({ name: "Alice", score: 2, color: "#e54c4c", losers: false });
		expect(scoreboardTeam(state, 1, 2)?.name).toBe("Team B");
		expect(scoreboardTeam(state, 9, 1)).toBeUndefined();
	});

	it("finds the next set of the scoreboard's stream", () => {
		expect(nextQueuedSet(sampleState(), 1)).toBe("Carol vs Dan / Eve");
		expect(nextQueuedSet(sampleState(), 2)).toBeUndefined();
	});
});

describe("team battle", () => {
	it("reads a team, its players and the active one", () => {
		const team = teamBattleTeam(sampleState(), 1)!;
		expect(team.name).toBe("Crew A");
		expect(team.active?.name).toBe("A2");
		expect(team.total).toBe(5);
		expect(team.players.map((p) => p.dead)).toEqual([true, false, false]);
		expect(teamBattleTeam(sampleState(), 2)).toBeUndefined();
	});
});

describe("display controls", () => {
	it("parses and formats targets", () => {
		expect(parseDisplayTarget("folder:scoreboard")).toEqual({ kind: "folder", name: "scoreboard" });
		expect(parseDisplayTarget("group:main stage")).toEqual({ kind: "group", name: "main stage" });
		expect(parseDisplayTarget("all")).toEqual({ kind: "all" });
		expect(parseDisplayTarget("nope")).toBeUndefined();
		expect(formatDisplayTarget({ kind: "group", name: "main" })).toBe("group:main");
	});

	it("knows what's shown", () => {
		const state = sampleState();
		expect(displayShown(state, { kind: "folder", name: "scoreboard" })).toBe(true);
		expect(displayShown(state, { kind: "folder", name: "bracket" })).toBe(false);
		expect(displayShown(state, { kind: "group", name: "MAIN" })).toBe(true);
		expect(displayShown(state, { kind: "group", name: "other" })).toBeUndefined();
		expect(displayShown(state, { kind: "all" })).toBe(false);
		expect(displayTargets(state).map(formatDisplayTarget)).toEqual([
			"all",
			"folder:bracket",
			"folder:scoreboard",
			"group:main",
		]);
	});
});

describe("links", () => {
	it("builds HyperDrive's links", () => {
		expect(scoreboard.scoreUp(2, 1).path).toBe("/scoreboard2-team1-scoreup");
		expect(scoreboard.teamColor(1, 2, "#2E89FF").path).toBe("/scoreboard1-team2-color-2E89FF");
		expect(scoreboard.reset(1, "all").path).toBe("/scoreboard1-clear-all");
		expect(scoreboard.loadNextQueued(3).path).toBe("/stream-queue/load-next?scoreboard=3");
		expect(display.set({ kind: "group", name: "main stage" }, "toggle").path).toBe("/display/group/main%20stage/toggle");
		expect(display.set({ kind: "all" }, "hide").path).toBe("/display/all/hide");
		expect(stageStrike.run(2, "win", 2)).toEqual({
			path: "/stage_strike_match_win",
			method: "POST",
			body: { scoreboardNumber: 2, winner: 1 },
		});
		expect(focusLinks.set("follow", { scoreboard: 2, channel: "Losers cam" }).path).toBe(
			"/bracket-focus/follow?scoreboard=2&channel=Losers+cam",
		);
		expect(focusLinks.set("all").path).toBe("/bracket-focus/all");
	});
});

describe("address", () => {
	it("accepts what people type", () => {
		expect(parseAddress("", "")).toEqual({ host: "localhost", port: 5500 });
		expect(parseAddress("192.168.1.5", "5501")).toEqual({ host: "192.168.1.5", port: 5501 });
		expect(parseAddress("http://stream-pc.local:6000/", 5500)).toEqual({ host: "stream-pc.local", port: 6000 });
		expect(parseAddress("pc", "99999")).toEqual({ host: "pc", port: 5500 });
	});
});
