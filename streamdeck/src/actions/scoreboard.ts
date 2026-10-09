import { action, type DialAction, type KeyAction } from "@elgato/streamdeck";

import { scoreboard } from "../hyperdrive/commands.ts";
import type { State } from "../hyperdrive/state.ts";
import type { Look, StripLook } from "../render/key.ts";
import {
	loadSetKey,
	num,
	resetKey,
	scoreKey,
	scoreStrip,
	swapKey,
	teamColorKey,
	teamOf,
	type LoadSetSettings,
	type ResetSettings,
	type ScoreSettings,
	type SwapSettings,
	type TeamColorSettings,
	type Translate,
} from "../views.ts";
import { HyperDriveAction } from "./base.ts";

/** Most a dial turn changes a score by, however fast it's turned */
const MAX_TICKS = 3;

/**
 * A team's score: a press adds a point (or takes one, per its settings),
 * holding does the opposite. On a dial: turn to change it, push to swap
 * the teams, touch to add a point.
 */
@action({ UUID: "com.voidscape.hyperdrive.score" })
export class ScoreAction extends HyperDriveAction<ScoreSettings> {
	protected key(s: ScoreSettings, state: State, t: Translate): Look {
		return scoreKey(t, s, state);
	}

	protected override strip(s: ScoreSettings, state: State, t: Translate): StripLook {
		return scoreStrip(t, s, state);
	}

	protected override holds(s: ScoreSettings): boolean {
		return s.hold !== "none";
	}

	protected async press(s: ScoreSettings, held: boolean, key: KeyAction<ScoreSettings>): Promise<void> {
		const down = (s.direction === "down") !== held;
		const sb = num(s.scoreboard, 1);
		const team = teamOf(s.team);
		await this.run(key, down ? scoreboard.scoreDown(sb, team) : scoreboard.scoreUp(sb, team));
	}

	protected override async rotate(s: ScoreSettings, ticks: number, dial: DialAction<ScoreSettings>): Promise<void> {
		const sb = num(s.scoreboard, 1);
		const team = teamOf(s.team);
		const steps = Math.min(Math.abs(ticks), MAX_TICKS);
		for (let i = 0; i < steps; i++) {
			if (!(await this.run(dial, ticks > 0 ? scoreboard.scoreUp(sb, team) : scoreboard.scoreDown(sb, team)))) {
				break;
			}
		}
	}

	protected override async dialPush(s: ScoreSettings, dial: DialAction<ScoreSettings>): Promise<void> {
		await this.run(dial, scoreboard.swapTeams(num(s.scoreboard, 1)));
	}

	protected override async touch(s: ScoreSettings, _hold: boolean, dial: DialAction<ScoreSettings>): Promise<void> {
		await this.run(dial, scoreboard.scoreUp(num(s.scoreboard, 1), teamOf(s.team)));
	}
}

/** Swaps the scoreboard's teams. */
@action({ UUID: "com.voidscape.hyperdrive.swap-teams" })
export class SwapTeamsAction extends HyperDriveAction<SwapSettings> {
	protected key(s: SwapSettings, state: State, t: Translate): Look {
		return swapKey(t, s, state);
	}

	protected async press(s: SwapSettings, _held: boolean, key: KeyAction<SwapSettings>): Promise<void> {
		await this.run(key, scoreboard.swapTeams(num(s.scoreboard, 1)));
	}
}

/** Resets the scores, the match, the players or everything. Held, unless set otherwise. */
@action({ UUID: "com.voidscape.hyperdrive.reset" })
export class ResetAction extends HyperDriveAction<ResetSettings> {
	protected key(s: ResetSettings, _state: State, t: Translate): Look {
		const look = resetKey(t, s);
		return s.requireHold === false ? look : { ...look, top: t("holdToReset") };
	}

	protected override holds(s: ResetSettings): boolean {
		return s.requireHold !== false;
	}

	protected async press(s: ResetSettings, held: boolean, key: KeyAction<ResetSettings>): Promise<void> {
		if (s.requireHold !== false && !held) {
			// A tap doesn't reset: a hint that it has to be held
			await key.showAlert();
			return;
		}
		await this.run(key, scoreboard.reset(num(s.scoreboard, 1), s.kind ?? "scores"), true);
	}
}

/** Sets a team's color; lit while the team has it. */
@action({ UUID: "com.voidscape.hyperdrive.team-color" })
export class TeamColorAction extends HyperDriveAction<TeamColorSettings> {
	protected key(s: TeamColorSettings, state: State, t: Translate): Look {
		return teamColorKey(t, s, state);
	}

	protected async press(s: TeamColorSettings, _held: boolean, key: KeyAction<TeamColorSettings>): Promise<void> {
		const color = /^#[0-9a-fA-F]{6}$/.test(s.color ?? "") ? s.color! : "#e54c4c";
		await this.run(key, scoreboard.teamColor(num(s.scoreboard, 1), teamOf(s.team), color));
	}
}

/** Loads a set: the next one in the stream queue, the stream's set from start.gg, or opens the set selector. */
@action({ UUID: "com.voidscape.hyperdrive.load-set" })
export class LoadSetAction extends HyperDriveAction<LoadSetSettings> {
	protected key(s: LoadSetSettings, state: State, t: Translate): Look {
		return loadSetKey(t, s, state);
	}

	protected async press(s: LoadSetSettings, _held: boolean, key: KeyAction<LoadSetSettings>): Promise<void> {
		const sb = num(s.scoreboard, 1);
		const request =
			s.source === "stream"
				? scoreboard.pullStreamSet(sb)
				: s.source === "selector"
					? scoreboard.openSetSelector(sb)
					: scoreboard.loadNextQueued(sb);
		await this.run(key, request, true);
	}
}
