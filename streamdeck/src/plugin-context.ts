import streamDeck from "@elgato/streamdeck";

import { HyperDriveConnection } from "./hyperdrive/connection.ts";
import type { Translate } from "./views.ts";

/** The plugin's connection to HyperDrive, shared by every action. */
export const hyperdrive = new HyperDriveConnection();

/** Plugin-wide settings, set from any action's property inspector. */
export type GlobalSettings = { host?: string; port?: string | number };

/** Translates a key of en.json's "Localization", filling in {placeholders}. */
export const t: Translate = (key, values) => {
	let text = streamDeck.i18n.t(key);
	if (values) {
		for (const [name, value] of Object.entries(values)) {
			text = text.replaceAll(`{${name}}`, String(value));
		}
	}
	return text;
};
