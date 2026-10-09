/**
 * HyperDrive's program state (what the layouts get), and what the actions
 * read from it. The web server sends the whole state on connect
 * (`program_state`), then the changes (`program_state_update`): DeepDiff's
 * flat deltas, applied the same way as layout/include/globals.js does.
 */

// The state is plain JSON from HyperDrive
export type State = Record<string, any>;

export type Delta = {
	path: (string | number)[];
	action: string;
	value?: unknown;
};

export function applyDelta(state: State, delta: Delta): void {
	const path = delta.path;
	if (!Array.isArray(path) || path.length === 0) {
		return;
	}
	let node: State = state;
	for (const key of path.slice(0, -1)) {
		if (node[key] === null || typeof node[key] !== "object") {
			node[key] = {};
		}
		node = node[key];
	}
	const last = path[path.length - 1];
	if (delta.action === "dictionary_item_removed" || delta.action === "iterable_item_removed") {
		delete node[last];
	} else {
		node[last] = delta.value;
	}
}

export function applyDeltas(state: State, deltas: Delta[]): State {
	for (const delta of deltas) {
		applyDelta(state, delta);
	}
	return state;
}

/** The value at a dotted path, e.g. "score.1.team.2.score". */
export function get<T = unknown>(state: State | undefined, path: string): T | undefined {
	let node: unknown = state;
	for (const key of path.split(".")) {
		if (node === null || typeof node !== "object") {
			return undefined;
		}
		node = (node as State)[key];
	}
	return node as T | undefined;
}

function numericKeys(obj: unknown): number[] {
	if (obj === null || typeof obj !== "object") {
		return [];
	}
	return Object.keys(obj)
		.filter((k) => /^\d+$/.test(k))
		.map(Number)
		.sort((a, b) => a - b);
}

function playerNames(players: unknown): string[] {
	if (players === null || typeof players !== "object") {
		return [];
	}
	return numericKeys(players)
		.map((k) => (players as State)[k]?.name)
		.filter((name): name is string => typeof name === "string" && name.trim() !== "");
}

// ---------------------------------------------------------------------------
// Scoreboards

/** The scoreboards HyperDrive has, by number. */
export function scoreboardNumbers(state: State): number[] {
	return numericKeys(state.score);
}

export type TeamInfo = {
	/** The team's name, or its players' names */
	name: string;
	score: number;
	color?: string;
	losers: boolean;
};

/**
 * A scoreboard team. Team 1 is the left side: HyperDrive moves the players
 * when the teams are swapped, like the score up/down links expect.
 */
export function scoreboardTeam(state: State, scoreboard: number, team: number): TeamInfo | undefined {
	const data = get<State>(state, `score.${scoreboard}.team.${team}`);
	if (!data) {
		return undefined;
	}
	const name = (typeof data.teamName === "string" && data.teamName.trim()) || playerNames(data.player).join(" / ");
	return {
		name,
		score: Number(data.score) || 0,
		color: validColor(data.color),
		losers: data.losers === true,
	};
}

export function teamsSwapped(state: State, scoreboard: number): boolean {
	return get(state, `score.${scoreboard}.teamsSwapped`) === true;
}

export function bestOf(state: State, scoreboard: number): number {
	return Number(get(state, `score.${scoreboard}.best_of`)) || 0;
}

/** The set a stream's queue loads next into the scoreboard, as "A vs B". */
export function nextQueuedSet(state: State, scoreboard: number): string | undefined {
	const streams = get<State[]>(state, "stream_queue.streams");
	if (!Array.isArray(streams)) {
		return undefined;
	}
	const stream = streams.find((s) => Number(s?.scoreboard) === scoreboard);
	const sets: State[] = Array.isArray(stream?.sets) ? stream.sets : [];
	const next = sets.find((s) => !s?.onStream);
	if (!next) {
		return undefined;
	}
	const names = [1, 2].map(
		(t) =>
			(typeof next.team?.[t]?.teamName === "string" && next.team[t].teamName.trim()) ||
			playerNames(next.team?.[t]?.player).join(" / ") ||
			"?",
	);
	return `${names[0]} vs ${names[1]}`;
}

// ---------------------------------------------------------------------------
// Crew/Team Battle

export type BattlePlayer = {
	/** From 1, as in /team-battle-team<t>-player<p>-active */
	number: number;
	name: string;
	/** Stocks left (Stock Pool) or games won (First To) */
	value: number;
	active: boolean;
	dead: boolean;
};

export type BattleTeam = {
	name: string;
	color?: string;
	players: BattlePlayer[];
	active?: BattlePlayer;
	/** Every player's stocks/games added up */
	total: number;
	mode: "STOCK_POOL" | "FIRST_TO";
	/** Stocks per player (Stock Pool) or games to win (First To) */
	battleValue: number;
};

export function teamBattleTeam(state: State, team: number): BattleTeam | undefined {
	const battle = get<State>(state, "team_battle");
	const data = battle?.team?.[team];
	if (!data) {
		return undefined;
	}
	const players: BattlePlayer[] = numericKeys(data.player).map((n) => {
		const p = data.player[n] ?? {};
		return {
			number: n,
			name: typeof p.name === "string" ? p.name : "",
			value: Number(p.dynamic_spinner) || 0,
			active: p.active === true,
			dead: p.dead === true,
		};
	});
	const activeNumber = Number(data.active_player);
	return {
		name: (typeof data.sponsor === "string" && data.sponsor.trim()) || "",
		color: validColor(data.color),
		players,
		active: players.find((p) => p.number === activeNumber) ?? players.find((p) => p.active),
		total: Number(battle?.[`team${team}_spinner-total`]) || players.reduce((sum, p) => sum + p.value, 0),
		mode: battle?.battle_mode === "FIRST_TO" ? "FIRST_TO" : "STOCK_POOL",
		battleValue: Number(battle?.battle_value) || 0,
	};
}

// ---------------------------------------------------------------------------
// Display Controls

export type DisplayKind = "folder" | "group" | "all";

export type DisplayTarget = { kind: DisplayKind; name?: string };

/** "folder:scoreboard", "group:main" or "all" */
export function parseDisplayTarget(value: string | undefined): DisplayTarget | undefined {
	if (!value) {
		return undefined;
	}
	if (value === "all") {
		return { kind: "all" };
	}
	const match = /^(folder|group):(.+)$/.exec(value);
	return match ? { kind: match[1] as DisplayKind, name: match[2] } : undefined;
}

export function formatDisplayTarget(target: DisplayTarget): string {
	return target.kind === "all" ? "all" : `${target.kind}:${target.name}`;
}

/** Every folder and group Display Controls knows, in order. */
export function displayTargets(state: State): DisplayTarget[] {
	const display = get<State>(state, "display") ?? {};
	const folders = Object.keys(display.folders ?? {}).sort();
	const groups = Object.keys(display.groups ?? {}).sort();
	return [
		{ kind: "all" },
		...folders.map((name): DisplayTarget => ({ kind: "folder", name })),
		...groups.map((name): DisplayTarget => ({ kind: "group", name })),
	];
}

/** Whether a folder, group or everything is shown, or undefined if HyperDrive doesn't know it. */
export function displayShown(state: State, target: DisplayTarget): boolean | undefined {
	const display = get<State>(state, "display");
	if (!display) {
		return undefined;
	}
	if (target.kind === "all") {
		const values = [...Object.values(display.folders ?? {}), ...Object.values(display.groups ?? {})];
		return values.every((v) => v !== false);
	}
	const values = target.kind === "folder" ? display.folders : display.groups;
	const name = target.kind === "group" ? target.name?.toLowerCase() : target.name;
	const value = name === undefined ? undefined : values?.[name];
	return typeof value === "boolean" ? value : undefined;
}

// ---------------------------------------------------------------------------
// Bracket focus

export type BracketFocus = {
	mode?: string;
	label?: string;
	/** player mode: the player's slot */
	player?: string | number;
	scoreboard?: number;
	step?: number;
	steps?: number;
};

export function bracketFocus(state: State, channel: string): BracketFocus | undefined {
	return get<BracketFocus>(state, `bracket.focus.${channel}`);
}

export function bracketChannels(state: State): string[] {
	const focus = get<State>(state, "bracket.focus");
	const channels = Object.keys(focus ?? {});
	return channels.includes("main") ? channels : ["main", ...channels];
}

// ---------------------------------------------------------------------------

function validColor(value: unknown): string | undefined {
	return typeof value === "string" && /^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$/.test(value) ? value : undefined;
}
