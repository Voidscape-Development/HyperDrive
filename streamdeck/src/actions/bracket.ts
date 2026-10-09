import { action, type DialAction, type KeyAction } from "@elgato/streamdeck";

import { bracketFocus, stageStrike } from "../hyperdrive/commands.ts";
import { bracketChannels, type State } from "../hyperdrive/state.ts";
import type { Look, StripLook } from "../render/key.ts";
import {
	focusKey,
	focusStrip,
	num,
	strikeKey,
	teamOf,
	type FocusSettings,
	type StrikeSettings,
	type Translate,
} from "../views.ts";
import { hyperdrive, t } from "../plugin-context.ts";
import { HyperDriveAction, type Item } from "./base.ts";

/** Stage strike: undo, redo, reset, or a team won rock-paper-scissors or a game. */
@action({ UUID: "com.voidscape.hyperdrive.stage-strike" })
export class StageStrikeAction extends HyperDriveAction<StrikeSettings> {
	protected key(s: StrikeSettings, state: State, t: Translate): Look {
		const look = strikeKey(t, s, state);
		return this.holds(s) ? { ...look, top: t("holdToReset") } : look;
	}

	/** Restarting the set's stage strike is held, unless set otherwise */
	protected override holds(s: StrikeSettings): boolean {
		return s.command === "reset" && s.requireHold !== false;
	}

	protected async press(s: StrikeSettings, held: boolean, key: KeyAction<StrikeSettings>): Promise<void> {
		if (this.holds(s) && !held) {
			await key.showAlert();
			return;
		}
		const command = s.command ?? "undo";
		await this.run(key, stageStrike.run(num(s.scoreboard, 1), command, teamOf(s.team)), command !== "rps" && command !== "win");
	}
}

/**
 * What the bracket focus layout zooms to. On a dial: turn for the next or
 * previous round, push to follow the scoreboard's set, touch for the
 * whole bracket.
 */
@action({ UUID: "com.voidscape.hyperdrive.bracket-focus" })
export class BracketFocusAction extends HyperDriveAction<FocusSettings> {
	protected key(s: FocusSettings, state: State, t: Translate): Look {
		return focusKey(t, s, state);
	}

	protected override strip(s: FocusSettings, state: State, t: Translate): StripLook {
		return focusStrip(t, s, state);
	}

	protected async press(s: FocusSettings, _held: boolean, key: KeyAction<FocusSettings>): Promise<void> {
		await this.run(
			key,
			bracketFocus.set(s.mode ?? "all", {
				channel: s.channel,
				scoreboard: num(s.scoreboard, 1),
				interval: num(s.interval, 0, 0) || undefined,
				player: s.player,
			}),
		);
	}

	protected override async rotate(s: FocusSettings, ticks: number, dial: DialAction<FocusSettings>): Promise<void> {
		await this.run(dial, bracketFocus.set(ticks > 0 ? "next-round" : "previous-round", { channel: s.channel }));
	}

	protected override async dialPush(s: FocusSettings, dial: DialAction<FocusSettings>): Promise<void> {
		await this.run(dial, bracketFocus.set("follow", { channel: s.channel, scoreboard: num(s.scoreboard, 1) }));
	}

	protected override async touch(s: FocusSettings, _hold: boolean, dial: DialAction<FocusSettings>): Promise<void> {
		await this.run(dial, bracketFocus.set("all", { channel: s.channel }));
	}

	protected override async items(name: string, s: FocusSettings): Promise<Item[] | undefined> {
		if (name === "bracketChannels") {
			const channels = bracketChannels(hyperdrive.state);
			if (s.channel && !channels.includes(s.channel)) channels.push(s.channel);
			return channels.map((c) => ({ label: c === "main" ? t("mainChannel") : c, value: c }));
		}
		if (name === "bracketPlayers") {
			type FocusInfo = { players?: { id: string | number; name: string; seed?: number }[] };
			const info = await hyperdrive.fetchJson<FocusInfo>(bracketFocus.state(s.channel).path);
			const players = [...(info?.players ?? [])].sort((a, b) => (a.seed ?? 1e9) - (b.seed ?? 1e9));
			const items: Item[] = players.map((p) => ({ label: p.seed ? `${p.seed}. ${p.name}` : p.name, value: String(p.id) }));
			if (s.player && !items.some((i) => "value" in i && i.value === s.player)) {
				items.unshift({ label: s.player, value: s.player });
			}
			return items;
		}
		return undefined;
	}
}
