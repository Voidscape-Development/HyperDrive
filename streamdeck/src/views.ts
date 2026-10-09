/**
 * What each action shows, from its settings and HyperDrive's state. Kept
 * apart from the actions (and the SDK) so it can be tested on its own.
 */

import type { IconName } from "./render/icons.ts";
import type { Look, StripLook } from "./render/key.ts";
import * as hd from "./hyperdrive/state.ts";
import type { State } from "./hyperdrive/state.ts";
import type { FocusMode, ResetKind, StrikeCommand } from "./hyperdrive/commands.ts";

/** Translates a key of en.json's Localization, with {name} placeholders. */
export type Translate = (key: string, values?: Record<string, string | number>) => string;

// ---------------------------------------------------------------------------
// Settings, as saved by the property inspectors (selects save strings)

export type ScoreSettings = { scoreboard?: string; team?: string; direction?: "up" | "down"; hold?: "opposite" | "none" };
export type SwapSettings = { scoreboard?: string };
export type ResetSettings = { scoreboard?: string; kind?: ResetKind; requireHold?: boolean };
export type TeamColorSettings = { scoreboard?: string; team?: string; color?: string };
export type LoadSetSettings = { scoreboard?: string; source?: "queue" | "stream" | "selector" };
export type DisplaySettings = { target?: string; action?: "toggle" | "show" | "hide" };
export type BattleScoreSettings = { team?: string; direction?: "up" | "down"; hold?: "opposite" | "none" };
export type BattlePlayerSettings = { team?: string; mode?: "next" | "player"; player?: string };
export type BattleResetSettings = { kind?: "stocks" | "all"; requireHold?: boolean };
export type StrikeSettings = { scoreboard?: string; command?: StrikeCommand; team?: string; requireHold?: boolean };
export type FocusSettings = { channel?: string; mode?: FocusMode; scoreboard?: string; interval?: string; player?: string };

export function num(value: unknown, fallback: number, min = 1): number {
	const n = Number(value);
	return Number.isInteger(n) && n >= min ? n : fallback;
}

export const teamOf = (value: unknown): 1 | 2 => (String(value) === "2" ? 2 : 1);

/** "Team 1", or its name */
function teamLabel(t: Translate, name: string | undefined, team: number): string {
	return name || t("team", { team });
}

// ---------------------------------------------------------------------------
// Scoreboard

export function scoreKey(t: Translate, s: ScoreSettings, state: State): Look {
	const sb = num(s.scoreboard, 1);
	const team = teamOf(s.team);
	const info = hd.scoreboardTeam(state, sb, team);
	return {
		color: info?.color,
		icon: s.direction === "down" ? "minus" : "plus",
		top: teamLabel(t, info?.name, team),
		main: String(info?.score ?? 0),
		bottom: info?.losers ? t("losers") : sb > 1 ? t("scoreboardShort", { scoreboard: sb }) : "",
	};
}

export function scoreStrip(t: Translate, s: ScoreSettings, state: State): StripLook {
	const sb = num(s.scoreboard, 1);
	const team = teamOf(s.team);
	const info = hd.scoreboardTeam(state, sb, team);
	const bestOf = hd.bestOf(state, sb);
	const where = `${t("scoreboardShort", { scoreboard: sb })} · ${t("team", { team })}`;
	return {
		color: info?.color,
		icon: "users",
		top: info?.name || t("team", { team }),
		main: String(info?.score ?? 0),
		bottom: bestOf ? `${where} · ${t("bestOf", { bestOf })}` : where,
	};
}

export function swapKey(t: Translate, s: SwapSettings, state: State): Look {
	const sb = num(s.scoreboard, 1);
	const names = [1, 2].map((team) => teamLabel(t, hd.scoreboardTeam(state, sb, team)?.name, team));
	return {
		icon: "swap",
		top: `${names[0]} · ${names[1]}`,
		bottom: t("swapTeams"),
	};
}

const RESET_LABELS: Record<ResetKind, string> = {
	scores: "resetScores",
	match: "resetMatch",
	players: "resetPlayers",
	all: "clearAll",
};

export function resetKey(t: Translate, s: ResetSettings): Look {
	const sb = num(s.scoreboard, 1);
	return {
		icon: "reset",
		top: t("scoreboard", { scoreboard: sb }),
		bottom: t(RESET_LABELS[s.kind ?? "scores"] ?? "resetScores"),
	};
}

export function teamColorKey(t: Translate, s: TeamColorSettings, state: State): Look {
	const sb = num(s.scoreboard, 1);
	const team = teamOf(s.team);
	const color = validColor(s.color) ?? "#e54c4c";
	const current = hd.scoreboardTeam(state, sb, team)?.color;
	return {
		color,
		icon: "color",
		bottom: t("team", { team }),
		state: current?.toLowerCase() === color.toLowerCase() ? "on" : undefined,
	};
}

export function loadSetKey(t: Translate, s: LoadSetSettings, state: State): Look {
	const sb = num(s.scoreboard, 1);
	switch (s.source) {
		case "stream":
			return { icon: "load", top: t("scoreboardShort", { scoreboard: sb }), bottom: t("loadStreamSet") };
		case "selector":
			return { icon: "window", top: t("scoreboardShort", { scoreboard: sb }), bottom: t("pickSet") };
		default: {
			const next = hd.nextQueuedSet(state, sb);
			return next
				? { icon: "queue", top: t("next"), main: next, bottom: t("loadNext") }
				: { icon: "queue", top: t("scoreboardShort", { scoreboard: sb }), bottom: t("queueEmpty") };
		}
	}
}

// ---------------------------------------------------------------------------
// Display Controls

export function displayName(t: Translate, target: hd.DisplayTarget | undefined): string {
	if (!target) return t("pickLayout");
	return target.kind === "all" ? t("everything") : (target.name ?? "");
}

function displayState(t: Translate, target: hd.DisplayTarget | undefined, state: State) {
	const shown = target ? hd.displayShown(state, target) : undefined;
	return {
		shown,
		icon: (shown === false ? "eyeOff" : target?.kind === "all" ? "layers" : "eye") as IconName,
		label: shown === undefined ? t("unknown") : shown ? t("shown") : t("hidden"),
		look: (shown === undefined ? undefined : shown ? "on" : "off") as Look["state"],
	};
}

export function displayKey(t: Translate, s: DisplaySettings, state: State): Look {
	const target = hd.parseDisplayTarget(s.target);
	const d = displayState(t, target, state);
	const action = s.action ?? "toggle";
	return {
		icon: action === "toggle" ? d.icon : action === "show" ? "eye" : "eyeOff",
		top: displayName(t, target),
		bottom: action === "toggle" ? d.label : `${t(action)} · ${d.label}`,
		state: d.look,
	};
}

export function displayStrip(t: Translate, s: DisplaySettings, state: State): StripLook {
	const target = hd.parseDisplayTarget(s.target);
	const d = displayState(t, target, state);
	return {
		icon: d.icon,
		top: t("displayControls"),
		main: displayName(t, target),
		bottom: d.label,
		state: d.look,
	};
}

/** The target after (or before) the current one, for the dial. */
export function stepDisplayTarget(state: State, current: string | undefined, ticks: number): string | undefined {
	const targets = hd.displayTargets(state).map(hd.formatDisplayTarget);
	if (targets.length === 0) return current;
	const index = current ? targets.indexOf(current) : -1;
	const next = (((index < 0 ? 0 : index + ticks) % targets.length) + targets.length) % targets.length;
	return targets[next];
}

// ---------------------------------------------------------------------------
// Crew/Team Battle

function battleValue(t: Translate, team: hd.BattleTeam, value: number): string {
	return team.mode === "FIRST_TO" ? t("wins", { count: value }) : t("stocks", { count: value });
}

export function battleScoreKey(t: Translate, s: BattleScoreSettings, state: State): Look {
	const teamNumber = teamOf(s.team);
	const team = hd.teamBattleTeam(state, teamNumber);
	if (!team) {
		return { icon: s.direction === "down" ? "minus" : "plus", top: t("team", { team: teamNumber }), bottom: t("noTeamBattle") };
	}
	const active = team.active;
	return {
		color: team.color,
		icon: s.direction === "down" ? "minus" : "plus",
		top: teamLabel(t, team.name, teamNumber),
		main: active ? active.name || t("player", { player: active.number }) : undefined,
		bottom: active ? battleValue(t, team, active.value) : t("noPlayer"),
	};
}

export function battleStrip(t: Translate, s: BattleScoreSettings, state: State): StripLook {
	const teamNumber = teamOf(s.team);
	const team = hd.teamBattleTeam(state, teamNumber);
	if (!team) {
		return { icon: "users", top: t("team", { team: teamNumber }), main: t("noTeamBattle") };
	}
	const active = team.active;
	const max = team.mode === "STOCK_POOL" ? team.battleValue : 0;
	return {
		color: team.color,
		icon: team.mode === "FIRST_TO" ? "trophy" : "stocks",
		top: teamLabel(t, team.name, teamNumber),
		main: active ? active.name || t("player", { player: active.number }) : t("noPlayer"),
		bottom: active
			? max
				? t("stocksOf", { count: active.value, max })
				: battleValue(t, team, active.value)
			: "",
		bar: active && max ? { value: active.value, max } : undefined,
	};
}

export function battlePlayerKey(t: Translate, s: BattlePlayerSettings, state: State): Look {
	const teamNumber = teamOf(s.team);
	const team = hd.teamBattleTeam(state, teamNumber);
	if (s.mode !== "player") {
		return {
			color: team?.color,
			icon: "next",
			top: teamLabel(t, team?.name, teamNumber),
			main: team?.active ? team.active.name || t("player", { player: team.active.number }) : undefined,
			bottom: t("nextPlayer"),
		};
	}
	const number = num(s.player, 1);
	const player = team?.players.find((p) => p.number === number);
	return {
		color: player?.dead ? undefined : team?.color,
		icon: "user",
		top: teamLabel(t, team?.name, teamNumber),
		main: player?.name || t("player", { player: number }),
		bottom: player ? (player.dead ? t("eliminated") : battleValue(t, team!, player.value)) : "",
		state: player?.dead ? "off" : player?.active || team?.active?.number === number ? "on" : undefined,
	};
}

export function battleResetKey(t: Translate, s: BattleResetSettings): Look {
	return { icon: "reset", top: t("teamBattle"), bottom: s.kind === "all" ? t("resetBattle") : t("resetStocks") };
}

// ---------------------------------------------------------------------------
// Stage strike

const STRIKE: Record<StrikeCommand, { icon: IconName; label: string }> = {
	undo: { icon: "undo", label: "undoStrike" },
	redo: { icon: "redo", label: "redoStrike" },
	reset: { icon: "reset", label: "resetStrike" },
	rps: { icon: "scissors", label: "rpsWinner" },
	win: { icon: "trophy", label: "wonGame" },
};

export function strikeKey(t: Translate, s: StrikeSettings, state: State): Look {
	const sb = num(s.scoreboard, 1);
	const command = s.command && s.command in STRIKE ? s.command : "undo";
	const { icon, label } = STRIKE[command];
	if (command === "rps" || command === "win") {
		const team = teamOf(s.team);
		const info = hd.scoreboardTeam(state, sb, team);
		return { color: info?.color, icon, top: teamLabel(t, info?.name, team), bottom: t(label) };
	}
	return { icon, top: t("scoreboardShort", { scoreboard: sb }), bottom: t(label) };
}

// ---------------------------------------------------------------------------
// Bracket focus

const FOCUS: Record<FocusMode, { icon: IconName; label: string }> = {
	all: { icon: "expand", label: "focusAll" },
	"next-round": { icon: "right", label: "nextRound" },
	"previous-round": { icon: "left", label: "previousRound" },
	follow: { icon: "follow", label: "followSet" },
	tour: { icon: "play", label: "tour" },
	player: { icon: "user", label: "playerRun" },
};

export function focusKey(t: Translate, s: FocusSettings, state: State): Look {
	const channel = s.channel || "main";
	const mode = s.mode && s.mode in FOCUS ? s.mode : "all";
	const focus = hd.bracketFocus(state, channel);
	const { icon, label } = FOCUS[mode];
	let active: boolean | undefined;
	if (focus && (mode === "all" || mode === "tour")) {
		active = focus.mode === mode;
	} else if (focus && mode === "follow") {
		active = focus.mode === "follow" && Number(focus.scoreboard) === num(s.scoreboard, 1);
	} else if (focus && mode === "player") {
		active = focus.mode === "player" && String(focus.player) === String(s.player);
	}
	return {
		icon,
		top: mode === "next-round" || mode === "previous-round" ? focus?.label || channelLabel(t, channel) : channelLabel(t, channel),
		bottom: mode === "follow" ? t("followScoreboard", { scoreboard: num(s.scoreboard, 1) }) : t(label),
		state: active ? "on" : undefined,
	};
}

export function focusStrip(t: Translate, s: FocusSettings, state: State): StripLook {
	const channel = s.channel || "main";
	const focus = hd.bracketFocus(state, channel);
	const mode = (focus?.mode && focus.mode in FOCUS ? focus.mode : "all") as FocusMode;
	const modeLabel = t(FOCUS[mode].label);
	const main = !focus ? t("noBracket") : focus.label || modeLabel;
	const bottom =
		mode === "tour" && focus?.steps ? t("tourStep", { step: (focus.step ?? 0) + 1, steps: focus.steps }) : main === modeLabel ? "" : modeLabel;
	return { icon: "bracket", top: channelLabel(t, channel), main, bottom };
}

function channelLabel(t: Translate, channel: string): string {
	return channel === "main" ? t("bracket") : `${t("bracket")} · ${channel}`;
}

function validColor(value: unknown): string | undefined {
	return typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value) ? value : undefined;
}
