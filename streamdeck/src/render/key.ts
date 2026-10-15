import { icon, type IconName } from "./icons.ts";
import { svgDataUrl, text, THEME } from "./svg.ts";

export type Look = {
	/** A team color, shown as a thin bar along the edge */
	color?: string;
	/** A color shown as a big dot, e.g. the color a key sets */
	swatch?: string;
	/** Small line at the top */
	top?: string;
	/** The big value (a score, a name) */
	main?: string;
	/** Small line at the bottom */
	bottom?: string;
	/** Drawn big without a main value, small in the corner with one */
	icon?: IconName;
	/** on: lit with a gold ring, off: dimmed */
	state?: "on" | "off";
	/** HyperDrive isn't connected */
	offline?: boolean;
};

// ---------------------------------------------------------------------------
// Parts of an image

function colors(look: Look): { fg: string; muted: string } {
	return look.state === "off" ? { fg: THEME.off, muted: THEME.off } : { fg: THEME.gold, muted: THEME.muted };
}

function background(look: Look, width: number, height: number): string {
	return `<rect width="${width}" height="${height}" fill="${look.state === "off" ? THEME.offBackground : THEME.background}"/>`;
}

/** The team color: a bar along the bottom of a key, the left of a strip */
function accent(look: Look, width: number, height: number, side: "bottom" | "left"): string {
	if (!look.color || look.state === "off") {
		return "";
	}
	return side === "bottom"
		? `<rect x="0" y="${height - 6}" width="${width}" height="6" fill="${look.color}"/>`
		: `<rect x="0" y="0" width="6" height="${height}" fill="${look.color}"/>`;
}

function ring(look: Look, width: number, height: number): string {
	if (look.state !== "on") {
		return "";
	}
	return `<rect x="3" y="3" width="${width - 6}" height="${height - 6}" rx="14" fill="none" stroke="${THEME.gold}" stroke-width="4"/>`;
}

function offlineBadge(size: number, x: number, y: number): string {
	return (
		`<circle cx="${x + size / 2}" cy="${y + size / 2}" r="${size / 2 + 4}" fill="${THEME.danger}"/>` +
		icon("offline", x, y, size, "#ffffff")
	);
}

// ---------------------------------------------------------------------------
// Keys

/** A 144x144 key image. */
export function renderKey(look: Look): string {
	const size = 144;
	const { fg, muted } = colors(look);
	const parts: string[] = [background(look, size, size)];

	if (look.main) {
		if (look.icon) {
			parts.push(icon(look.icon, 12, 12, 20, fg));
		}
		parts.push(
			text(look.top ?? "", { x: look.icon ? 82 : 72, y: 22, width: look.icon ? 100 : 124, max: 20, min: 12, color: muted, weight: 600 }),
		);
		parts.push(text(look.main, { x: 72, y: 78, width: 128, max: 64, min: 18, color: fg, weight: 700 }));
		parts.push(text(look.bottom ?? "", { x: 72, y: 120, width: 124, max: 18, min: 11, color: muted, weight: 600 }));
	} else {
		parts.push(text(look.top ?? "", { x: 72, y: 22, width: 124, max: 18, min: 11, color: muted, weight: 600 }));
		const y = look.top ? 42 : 34;
		if (look.swatch) {
			parts.push(`<circle cx="72" cy="${y + 26}" r="24" fill="${look.swatch}" stroke="${fg}" stroke-width="2"/>`);
		} else if (look.icon) {
			parts.push(icon(look.icon, 46, y, 52, fg));
		}
		parts.push(text(look.bottom ?? "", { x: 72, y: 118, width: 124, max: 20, min: 11, color: fg, weight: 600 }));
	}
	parts.push(accent(look, size, size, "bottom"));
	parts.push(ring(look, size, size));

	let body = parts.join("");
	if (look.offline) {
		body = `<g opacity="0.35">${body}</g>${offlineBadge(26, 108, 10)}`;
	}
	return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">${body}</svg>`;
}

// ---------------------------------------------------------------------------
// Touch strips

export type StripLook = Look & {
	/** A gauge along the bottom, e.g. stocks left */
	bar?: { value: number; max: number };
};

/** A 200x100 touch strip image, for one dial. */
export function renderStrip(look: StripLook): string {
	const width = 200;
	const height = 100;
	const { fg, muted } = colors(look);
	const parts: string[] = [background(look, width, height)];

	if (look.swatch) {
		parts.push(`<circle cx="22" cy="18" r="9" fill="${look.swatch}" stroke="${fg}" stroke-width="1.5"/>`);
	} else if (look.icon) {
		parts.push(icon(look.icon, 14, 8, 18, fg));
	}
	const hasIcon = Boolean(look.icon || look.swatch);
	parts.push(
		text(look.top ?? "", { x: hasIcon ? 40 : 14, y: 18, width: hasIcon ? 150 : 176, max: 16, min: 11, color: muted, weight: 600, anchor: "start" }),
	);
	parts.push(text(look.main ?? "", { x: 100, y: 54, width: 180, max: 38, min: 14, color: fg, weight: 700 }));
	parts.push(text(look.bottom ?? "", { x: 100, y: look.bar ? 80 : 84, width: 184, max: 16, min: 11, color: muted, weight: 600 }));

	if (look.bar && look.bar.max > 0) {
		const share = Math.max(0, Math.min(1, look.bar.value / look.bar.max));
		parts.push(`<rect x="12" y="92" width="176" height="4" rx="2" fill="${muted}" opacity="0.4"/>`);
		parts.push(`<rect x="12" y="92" width="${(176 * share).toFixed(1)}" height="4" rx="2" fill="${fg}"/>`);
	}
	parts.push(accent(look, width, height, "left"));
	parts.push(ring(look, width, height));

	let body = parts.join("");
	if (look.offline) {
		body = `<g opacity="0.35">${body}</g>${offlineBadge(20, 170, 10)}`;
	}
	return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">${body}</svg>`;
}

// ---------------------------------------------------------------------------
// Data URLs

export const keyImage = (look: Look): string => svgDataUrl(renderKey(look));
export const stripImage = (look: StripLook): string => svgDataUrl(renderStrip(look));
