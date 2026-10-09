import { action, type DialAction, type KeyAction } from "@elgato/streamdeck";

import { teamBattle } from "../hyperdrive/commands.ts";
import { teamBattleTeam, type State } from "../hyperdrive/state.ts";
import type { Look, StripLook } from "../render/key.ts";
import {
	battlePlayerKey,
	battleResetKey,
	battleScoreKey,
	battleStrip,
	num,
	teamOf,
	type BattlePlayerSettings,
	type BattleResetSettings,
	type BattleScoreSettings,
	type Translate,
} from "../views.ts";
import { hyperdrive, t } from "../plugin-context.ts";
import { HyperDriveAction, type Item } from "./base.ts";

/**
 * A team scores in the Crew/Team Battle: in Stock Pool the other team's
 * active player loses a stock, in First To the team's player wins a game.
 * Holding undoes a point. On a dial: turn to score or undo, push or touch
 * for the team's next player.
 */
@action({ UUID: "com.voidscape.hyperdrive.battle-score" })
export class BattleScoreAction extends HyperDriveAction<BattleScoreSettings> {
	protected key(s: BattleScoreSettings, state: State, t: Translate): Look {
		return battleScoreKey(t, s, state);
	}

	protected override strip(s: BattleScoreSettings, state: State, t: Translate): StripLook {
		return battleStrip(t, s, state);
	}

	protected override holds(s: BattleScoreSettings): boolean {
		return s.hold !== "none";
	}

	protected async press(s: BattleScoreSettings, held: boolean, key: KeyAction<BattleScoreSettings>): Promise<void> {
		const down = (s.direction === "down") !== held;
		const team = teamOf(s.team);
		await this.run(key, down ? teamBattle.scoreDown(team) : teamBattle.scoreUp(team));
	}

	protected override async rotate(s: BattleScoreSettings, ticks: number, dial: DialAction<BattleScoreSettings>): Promise<void> {
		const team = teamOf(s.team);
		// One point per turn: points take stocks, so a fast turn shouldn't take several
		await this.run(dial, ticks > 0 ? teamBattle.scoreUp(team) : teamBattle.scoreDown(team));
	}

	protected override async dialPush(s: BattleScoreSettings, dial: DialAction<BattleScoreSettings>): Promise<void> {
		await this.run(dial, teamBattle.nextPlayer(teamOf(s.team)));
	}

	protected override async touch(s: BattleScoreSettings, _hold: boolean, dial: DialAction<BattleScoreSettings>): Promise<void> {
		await this.run(dial, teamBattle.nextPlayer(teamOf(s.team)));
	}
}

/** Makes the team's next player, or a given player, the active one. */
@action({ UUID: "com.voidscape.hyperdrive.battle-player" })
export class BattlePlayerAction extends HyperDriveAction<BattlePlayerSettings> {
	protected key(s: BattlePlayerSettings, state: State, t: Translate): Look {
		return battlePlayerKey(t, s, state);
	}

	protected async press(s: BattlePlayerSettings, _held: boolean, key: KeyAction<BattlePlayerSettings>): Promise<void> {
		const team = teamOf(s.team);
		await this.run(key, s.mode === "player" ? teamBattle.setActive(team, num(s.player, 1)) : teamBattle.nextPlayer(team));
	}

	protected override items(name: string, s: BattlePlayerSettings): Item[] | undefined {
		if (name !== "battlePlayers") {
			return undefined;
		}
		const players = teamBattleTeam(hyperdrive.state, teamOf(s.team))?.players ?? [];
		const count = Math.max(players.length, num(s.player, 1), 5);
		return Array.from({ length: count }, (_, i) => {
			const name = players[i]?.name;
			const label = t("player", { player: i + 1 });
			return { label: name ? `${label}: ${name}` : label, value: String(i + 1) };
		});
	}
}

/** Resets every player's stocks, or the whole battle. Held, unless set otherwise. */
@action({ UUID: "com.voidscape.hyperdrive.battle-reset" })
export class BattleResetAction extends HyperDriveAction<BattleResetSettings> {
	protected key(s: BattleResetSettings, _state: State, t: Translate): Look {
		const look = battleResetKey(t, s);
		return s.requireHold === false ? look : { ...look, top: t("holdToReset") };
	}

	protected override holds(s: BattleResetSettings): boolean {
		return s.requireHold !== false;
	}

	protected async press(s: BattleResetSettings, held: boolean, key: KeyAction<BattleResetSettings>): Promise<void> {
		if (s.requireHold !== false && !held) {
			await key.showAlert();
			return;
		}
		await this.run(key, s.kind === "all" ? teamBattle.reset() : teamBattle.resetStocks(), true);
	}
}
