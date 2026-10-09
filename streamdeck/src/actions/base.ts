import streamDeck, {
	type DialAction,
	type DialDownEvent,
	type DialRotateEvent,
	type DidReceiveSettingsEvent,
	type KeyAction,
	type KeyDownEvent,
	type KeyUpEvent,
	type PropertyInspectorDidAppearEvent,
	type SendToPluginEvent,
	SingletonAction,
	type TouchTapEvent,
	type WillAppearEvent,
	type WillDisappearEvent,
} from "@elgato/streamdeck";
import type { JsonObject, JsonValue } from "@elgato/utils";

import type { Request } from "../hyperdrive/commands.ts";
import { scoreboardNumbers, type State } from "../hyperdrive/state.ts";
import { keyImage, stripImage, type Look, type StripLook } from "../render/key.ts";
import { hyperdrive, t } from "../plugin-context.ts";
import type { Translate } from "../views.ts";

/** How long a key is held for its hold action, in ms */
export const HOLD_MS = 600;

/** Items of a property inspector's select (sdpi-components' datasource) */
export type Item = { label: string; value: string } | { label: string; children: Item[] };

type Instance<T extends JsonObject> = { action: KeyAction<T> | DialAction<T>; settings: T; image?: string };

/** Every HyperDrive action, redrawn when HyperDrive's state changes */
const registered = new Set<HyperDriveAction<JsonObject>>();

export function redrawAll(): void {
	for (const action of registered) {
		action.redraw();
	}
}

/**
 * What every HyperDrive action does: draw its keys and dials from
 * HyperDrive's state, and run commands when pressed. Subclasses say what
 * they look like and what they do.
 */
export abstract class HyperDriveAction<T extends JsonObject> extends SingletonAction<T> {
	readonly #instances = new Map<string, Instance<T>>();
	/** Keys pressed, and their hold timers */
	readonly #pressed = new Map<string, { timer?: NodeJS.Timeout; held: boolean }>();

	constructor() {
		super();
		registered.add(this as unknown as HyperDriveAction<JsonObject>);
	}

	/** The key's image */
	protected abstract key(settings: T, state: State, t: Translate): Look;

	/** The touch strip, for actions that go on dials */
	protected strip(_settings: T, _state: State, _t: Translate): StripLook | undefined {
		return undefined;
	}

	/** The key was pressed (held: for longer than HOLD_MS) */
	protected abstract press(settings: T, held: boolean, action: KeyAction<T>): Promise<void> | void;

	/** Whether holding the key does something else, so the press waits for the release */
	protected holds(_settings: T): boolean {
		return false;
	}

	protected rotate(_settings: T, _ticks: number, _action: DialAction<T>): Promise<void> | void {}
	protected dialPush(_settings: T, _action: DialAction<T>): Promise<void> | void {}
	protected touch(_settings: T, _hold: boolean, _action: DialAction<T>): Promise<void> | void {}

	/** The property inspector's selects: datasource name to items */
	protected items(_name: string, _settings: T): Item[] | Promise<Item[] | undefined> | undefined {
		return undefined;
	}

	/** Runs a HyperDrive command; an alert on the key or dial if it fails. */
	protected async run(action: KeyAction<T> | DialAction<T>, request: Request, showOk = false): Promise<boolean> {
		const result = await hyperdrive.command(request.path, { method: request.method, body: request.body });
		if (!result.ok) {
			streamDeck.logger.warn(`${request.path} failed: ${result.status} ${result.body.slice(0, 200)}`);
			await action.showAlert();
		} else if (showOk && action.isKey()) {
			await action.showOk();
		}
		return result.ok;
	}

	/** Saves new settings for an instance (e.g. picked with a dial) and redraws it. */
	protected async saveSettings(action: KeyAction<T> | DialAction<T>, settings: T): Promise<void> {
		const instance = this.#instances.get(action.id);
		if (instance) {
			instance.settings = settings;
		}
		await action.setSettings(settings);
		await this.#draw(action.id);
	}

	/** Draws every visible key and dial of this action again. */
	redraw(): void {
		for (const id of this.#instances.keys()) {
			void this.#draw(id);
		}
	}

	async #draw(id: string): Promise<void> {
		const instance = this.#instances.get(id);
		if (!instance) {
			return;
		}
		const offline = hyperdrive.status !== "connected";
		try {
			if (instance.action.isDial()) {
				const look = this.strip(instance.settings, hyperdrive.state, t) ?? this.key(instance.settings, hyperdrive.state, t);
				const image = stripImage({ ...look, offline });
				if (image !== instance.image) {
					instance.image = image;
					await instance.action.setFeedback({ canvas: image });
				}
			} else {
				const image = keyImage({ ...this.key(instance.settings, hyperdrive.state, t), offline });
				if (image !== instance.image) {
					instance.image = image;
					await instance.action.setImage(image);
				}
			}
		} catch (e) {
			streamDeck.logger.error(`Couldn't draw ${this.manifestId}`, e);
		}
	}

	// -------------------------------------------------------------------
	// Stream Deck events

	override async onWillAppear(ev: WillAppearEvent<T>): Promise<void> {
		this.#instances.set(ev.action.id, { action: ev.action, settings: ev.payload.settings });
		await this.#draw(ev.action.id);
	}

	override onWillDisappear(ev: WillDisappearEvent<T>): void {
		this.#instances.delete(ev.action.id);
		const pressed = this.#pressed.get(ev.action.id);
		clearTimeout(pressed?.timer);
		this.#pressed.delete(ev.action.id);
	}

	override async onDidReceiveSettings(ev: DidReceiveSettingsEvent<T>): Promise<void> {
		this.#instances.set(ev.action.id, { action: ev.action, settings: ev.payload.settings });
		await this.#draw(ev.action.id);
	}

	override async onKeyDown(ev: KeyDownEvent<T>): Promise<void> {
		const settings = ev.payload.settings;
		// Multi actions don't wait for the key to be released
		if (!this.holds(settings) || ev.payload.isInMultiAction) {
			await this.press(settings, false, ev.action);
			return;
		}
		const pressed: { timer?: NodeJS.Timeout; held: boolean } = { held: false };
		// Held long enough: act right away, without waiting for the release
		pressed.timer = setTimeout(() => {
			pressed.held = true;
			void this.press(settings, true, ev.action);
		}, HOLD_MS);
		this.#pressed.set(ev.action.id, pressed);
	}

	override async onKeyUp(ev: KeyUpEvent<T>): Promise<void> {
		const pressed = this.#pressed.get(ev.action.id);
		if (!pressed) {
			return;
		}
		this.#pressed.delete(ev.action.id);
		clearTimeout(pressed.timer);
		if (!pressed.held) {
			await this.press(ev.payload.settings, false, ev.action);
		}
	}

	override async onDialRotate(ev: DialRotateEvent<T>): Promise<void> {
		await this.rotate(ev.payload.settings, ev.payload.ticks, ev.action);
	}

	override async onDialDown(ev: DialDownEvent<T>): Promise<void> {
		await this.dialPush(ev.payload.settings, ev.action);
	}

	override async onTouchTap(ev: TouchTapEvent<T>): Promise<void> {
		await this.touch(ev.payload.settings, ev.payload.hold, ev.action);
	}

	override async onPropertyInspectorDidAppear(_ev: PropertyInspectorDidAppearEvent<T>): Promise<void> {
		await sendStatus();
	}

	override async onSendToPlugin(ev: SendToPluginEvent<JsonValue, T>): Promise<void> {
		const payload = ev.payload as { event?: string } | null;
		const event = payload?.event;
		if (!event) {
			return;
		}
		if (event === "status") {
			await sendStatus();
			return;
		}
		const settings = await ev.action.getSettings();
		const items = (await this.items(event, settings)) ?? commonItems(event, settings);
		if (items) {
			await streamDeck.ui.sendToPropertyInspector({ event, items });
		}
	}
}

/** Selects every property inspector can have. */
function commonItems(name: string, settings: JsonObject): Item[] | undefined {
	if (name === "scoreboards") {
		const numbers = scoreboardNumbers(hyperdrive.state);
		const current = Number(settings.scoreboard) || 1;
		const all = [...new Set([...(numbers.length ? numbers : [1, 2, 3, 4]), current])].sort((a, b) => a - b);
		return all.map((n) => ({ label: t("scoreboard", { scoreboard: n }), value: String(n) }));
	}
	return undefined;
}

/** Tells an open property inspector whether HyperDrive is connected. */
export async function sendStatus(): Promise<void> {
	if (!streamDeck.ui.action) {
		return;
	}
	await streamDeck.ui.sendToPropertyInspector({
		event: "status",
		status: hyperdrive.status,
		url: hyperdrive.url,
		message: t(`status.${hyperdrive.status}`, { url: hyperdrive.url }),
	});
}
