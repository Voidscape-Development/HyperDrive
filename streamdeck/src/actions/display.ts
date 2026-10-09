import { action, type DialAction, type KeyAction } from "@elgato/streamdeck";

import { display } from "../hyperdrive/commands.ts";
import { displayTargets, formatDisplayTarget, parseDisplayTarget, type State } from "../hyperdrive/state.ts";
import type { Look, StripLook } from "../render/key.ts";
import { displayKey, displayName, displayStrip, stepDisplayTarget, type DisplaySettings, type Translate } from "../views.ts";
import { hyperdrive, t } from "../plugin-context.ts";
import { HyperDriveAction, type Item } from "./base.ts";

/**
 * Shows, hides or toggles a layout folder, a group or everything (Display
 * Controls), lit while it's shown. On a dial: turn to pick what it
 * controls, push or touch to toggle it.
 */
@action({ UUID: "com.voidscape.hyperdrive.display" })
export class DisplayAction extends HyperDriveAction<DisplaySettings> {
	protected key(s: DisplaySettings, state: State, t: Translate): Look {
		return displayKey(t, s, state);
	}

	protected override strip(s: DisplaySettings, state: State, t: Translate): StripLook {
		return displayStrip(t, s, state);
	}

	protected async press(s: DisplaySettings, _held: boolean, key: KeyAction<DisplaySettings>): Promise<void> {
		await this.#apply(s, s.action ?? "toggle", key);
	}

	protected override async rotate(s: DisplaySettings, ticks: number, dial: DialAction<DisplaySettings>): Promise<void> {
		const target = stepDisplayTarget(hyperdrive.state, s.target, ticks);
		if (target && target !== s.target) {
			await this.saveSettings(dial, { ...s, target });
		}
	}

	protected override async dialPush(s: DisplaySettings, dial: DialAction<DisplaySettings>): Promise<void> {
		await this.#apply(s, "toggle", dial);
	}

	protected override async touch(s: DisplaySettings, _hold: boolean, dial: DialAction<DisplaySettings>): Promise<void> {
		await this.#apply(s, "toggle", dial);
	}

	async #apply(
		s: DisplaySettings,
		action: "show" | "hide" | "toggle",
		instance: KeyAction<DisplaySettings> | DialAction<DisplaySettings>,
	): Promise<void> {
		const target = parseDisplayTarget(s.target);
		if (!target) {
			await instance.showAlert();
			return;
		}
		await this.run(instance, display.set(target, action));
	}

	protected override items(name: string, s: DisplaySettings): Item[] | undefined {
		if (name !== "displayTargets") {
			return undefined;
		}
		const targets = displayTargets(hyperdrive.state);
		const current = parseDisplayTarget(s.target);
		// Keep what's picked even when HyperDrive doesn't know it (yet)
		if (current && !targets.some((x) => formatDisplayTarget(x) === s.target)) {
			targets.push(current);
		}
		const item = (x: (typeof targets)[number]) => ({ label: displayName(t, x), value: formatDisplayTarget(x) });
		return [
			item({ kind: "all" }),
			{ label: t("layoutFolders"), children: targets.filter((x) => x.kind === "folder").map(item) },
			{ label: t("groups"), children: targets.filter((x) => x.kind === "group").map(item) },
		];
	}
}
