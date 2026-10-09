/**
 * Writes the plugin's images: the action list icons, the keys' images until
 * the plugin draws them, and the category icon. Run with `npm run images`
 * after changing an icon (Node.js 22.18 or newer, which runs TypeScript).
 *
 * The marketplace icon (imgs/plugin/marketplace*.png) is HyperDrive's logo,
 * assets/icons/icon.svg, at 144 and 288 pixels.
 */

import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import { ICONS, type IconName } from "../src/render/icons.ts";
import { renderKey, type Look } from "../src/render/key.ts";

const root = path.join(import.meta.dirname, "..", "com.voidscape.hyperdrive.sdPlugin", "imgs");

/** The action list's icons: white lines, as Stream Deck wants them */
function listIcon(name: IconName): string {
	return (
		`<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" ` +
		`stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="${ICONS[name]}"/></svg>\n`
	);
}

const actions: Record<string, { icon: IconName; key: Look }> = {
	score: { icon: "plus", key: { color: "#e54c4c", icon: "plus", top: "Team 1", main: "0" } },
	"swap-teams": { icon: "swap", key: { icon: "swap", bottom: "Swap teams" } },
	reset: { icon: "reset", key: { icon: "reset", top: "Hold to reset", bottom: "Reset scores" } },
	"team-color": { icon: "color", key: { color: "#e54c4c", icon: "color", bottom: "Team 1" } },
	"load-set": { icon: "queue", key: { icon: "queue", bottom: "Load next" } },
	display: { icon: "eye", key: { icon: "eye", bottom: "Display" } },
	"battle-score": { icon: "stocks", key: { icon: "plus", top: "Team 1", main: "—" } },
	"battle-player": { icon: "next", key: { icon: "next", bottom: "Next player" } },
	"battle-reset": { icon: "reset", key: { icon: "reset", top: "Hold to reset", bottom: "Reset stocks" } },
	"stage-strike": { icon: "scissors", key: { icon: "undo", bottom: "Undo" } },
	"bracket-focus": { icon: "bracket", key: { icon: "expand", top: "Bracket", bottom: "Whole bracket" } },
};

mkdirSync(path.join(root, "actions"), { recursive: true });
mkdirSync(path.join(root, "keys"), { recursive: true });
mkdirSync(path.join(root, "plugin"), { recursive: true });

for (const [name, { icon, key }] of Object.entries(actions)) {
	writeFileSync(path.join(root, "actions", `${name}.svg`), listIcon(icon));
	writeFileSync(path.join(root, "keys", `${name}.svg`), renderKey(key) + "\n");
}

// The category icon: HyperDrive's ring with warp lines, in white
writeFileSync(
	path.join(root, "plugin", "category.svg"),
	`<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28" fill="none" stroke="#ffffff" stroke-linecap="round">` +
		`<circle cx="14" cy="14" r="11" stroke-width="2"/>` +
		`<path d="M10 9v10M18 9v10M10 14h8" stroke-width="2.4"/>` +
		`<path d="M2 21h5M21 7h5" stroke-width="1.6" opacity="0.7"/></svg>\n`,
);

console.log(`Images written to ${root}`);
