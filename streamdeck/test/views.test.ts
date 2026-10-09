import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import type { State } from "../src/hyperdrive/state.ts";
import { renderKey, renderStrip } from "../src/render/key.ts";
import { fitText } from "../src/render/svg.ts";
import * as views from "../src/views.ts";

const locale = JSON.parse(readFileSync(new URL("../com.voidscape.hyperdrive.sdPlugin/en.json", import.meta.url), "utf8"));

/** Translates like the plugin does, and fails on keys en.json doesn't have */
const t: views.Translate = (key, values) => {
	const text = key.split(".").reduce((node, k) => node?.[k], locale.Localization);
	if (typeof text !== "string") {
		throw new Error(`Missing translation: ${key}`);
	}
	return Object.entries(values ?? {}).reduce((s, [k, v]) => s.replaceAll(`{${k}}`, String(v)), text);
};

const state: State = {
	score: {
		"1": {
			best_of: 3,
			team: {
				"1": { score: 1, color: "#e54c4c", player: { "1": { name: "Alice" } } },
				"2": { score: 0, color: "#2e89ff", teamName: "Team B" },
			},
		},
	},
	display: { folders: { scoreboard: false }, groups: {} },
	team_battle: {
		battle_mode: "STOCK_POOL",
		battle_value: 3,
		team: { "1": { sponsor: "Crew", active_player: 1, player: { "1": { name: "", dynamic_spinner: 2 } } } },
	},
	bracket: { focus: { main: { mode: "all", label: "" } } },
};

describe("views", () => {
	it("draws a team's score in its color", () => {
		expect(views.scoreKey(t, { team: "1" }, state)).toMatchObject({ color: "#e54c4c", top: "Alice", main: "1", icon: "plus" });
		expect(views.scoreKey(t, { team: "2", direction: "down" }, state)).toMatchObject({ top: "Team B", main: "0", icon: "minus" });
		expect(views.scoreStrip(t, { team: "1" }, state)).toMatchObject({ top: "Alice", main: "1", bottom: "SB1 · Team 1 · Best of 3" });
	});

	it("lights a team color key while the team has it", () => {
		expect(views.teamColorKey(t, { team: "1", color: "#E54C4C" }, state).state).toBe("on");
		expect(views.teamColorKey(t, { team: "1", color: "#000000" }, state).state).toBeUndefined();
	});

	it("shows whether a layout is shown", () => {
		expect(views.displayKey(t, { target: "folder:scoreboard" }, state)).toMatchObject({ state: "off", bottom: "Hidden", icon: "eyeOff" });
		expect(views.displayKey(t, { target: "group:nope" }, state)).toMatchObject({ state: undefined, bottom: "Unknown" });
		expect(views.displayKey(t, {}, state).top).toBe("Pick a layout");
	});

	it("steps through the layouts on a dial", () => {
		expect(views.stepDisplayTarget(state, "all", 1)).toBe("folder:scoreboard");
		expect(views.stepDisplayTarget(state, "all", -1)).toBe("folder:scoreboard");
		expect(views.stepDisplayTarget(state, undefined, 1)).toBe("all");
	});

	it("names an unnamed team battle player by number", () => {
		expect(views.battleScoreKey(t, { team: "1" }, state)).toMatchObject({ top: "Crew", main: "Player 1", bottom: "2 stocks" });
		expect(views.battleStrip(t, { team: "1" }, state).bar).toEqual({ value: 2, max: 3 });
		expect(views.battleScoreKey(t, { team: "2" }, state).bottom).toBe("No team battle");
	});

	it("doesn't repeat the bracket focus mode", () => {
		expect(views.focusStrip(t, {}, state)).toMatchObject({ main: "Whole bracket", bottom: "" });
		expect(views.focusKey(t, { mode: "all" }, state).state).toBe("on");
		expect(views.focusKey(t, { mode: "follow", scoreboard: "1" }, state).state).toBeUndefined();
	});

	it("has every translation it uses", () => {
		const all: views.Translate = (key, values) => t(key, values);
		for (const kind of ["scores", "match", "players", "all"] as const) views.resetKey(all, { kind });
		for (const command of ["undo", "redo", "reset", "rps", "win"] as const) views.strikeKey(all, { command }, state);
		for (const mode of ["all", "next-round", "previous-round", "follow", "tour", "player"] as const) {
			views.focusKey(all, { mode }, state);
		}
		for (const source of ["queue", "stream", "selector"] as const) views.loadSetKey(all, { source }, state);
		for (const action of ["toggle", "show", "hide"] as const) views.displayKey(all, { target: "all", action }, state);
		views.battlePlayerKey(all, { mode: "player", player: "3" }, state);
		views.battleResetKey(all, { kind: "all" });
		views.swapKey(all, {}, state);
		for (const status of ["connected", "connecting", "disconnected"]) t(`status.${status}`, { url: "x" });
	});
});

describe("rendering", () => {
	it("shrinks long text, then cuts it", () => {
		expect(fitText("12", 132, 68, 18).size).toBe(68);
		const long = fitText("A very long player name indeed", 128, 22, 13);
		expect(long.size).toBe(13);
		expect(long.text.endsWith("…")).toBe(true);
	});

	it("escapes names in the SVG", () => {
		const svg = renderKey({ top: `<script>&"`, main: "1" });
		expect(svg).toContain("&lt;script&gt;&amp;&quot;");
		expect(svg).not.toContain("<script>");
	});

	it("marks offline images", () => {
		expect(renderKey({ main: "1", offline: true })).toContain('opacity="0.35"');
		expect(renderStrip({ main: "1" })).toMatch(/^<svg[^>]+width="200" height="100"/);
	});
});
