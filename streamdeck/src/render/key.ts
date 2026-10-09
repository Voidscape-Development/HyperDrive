import { icon, type IconName } from "./icons.ts";
import { BRAND, readableOn, shade, svgDataUrl, text } from "./svg.ts";

export type Look = {
	/** A team color to fill the key with, instead of HyperDrive's */
	color?: string;
	/** Small line at the top */
	top?: string;
	/** The big value (a score, a name) */
	main?: string;
	/** Small line at the bottom */
	bottom?: string;
	/** Drawn big without a main value, small in the corner with one */
	icon?: IconName;
	/** on: lit with a ring, off: dimmed */
	state?: "on" | "off";
	/** HyperDrive isn't connected */
	offline?: boolean;
};

function background(look: Look, width: number, height: number): string {
	if (look.state === "off") {
		return `<rect width="${width}" height="${height}" fill="#1b1b26"/>`;
	}
	if (look.color) {
		return (
			`<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">` +
			`<stop offset="0" stop-color="${shade(look.color, 0.08)}"/><stop offset="1" stop-color="${shade(look.color, -0.35)}"/>` +
			`</linearGradient></defs><rect width="${width}" height="${height}" fill="url(#bg)"/>`
		);
	}
	return (
		`<defs><radialGradient id="bg" cx="0.62" cy="0.3" r="0.95">` +
		`<stop offset="0" stop-color="${BRAND.spaceLight}"/><stop offset="0.55" stop-color="${BRAND.spaceMid}"/>` +
		`<stop offset="1" stop-color="${BRAND.spaceDark}"/></radialGradient></defs>` +
		`<rect width="${width}" height="${height}" fill="url(#bg)"/>`
	);
}

function ring(look: Look, width: number, height: number): string {
	if (look.state !== "on") {
		return "";
	}
	const stroke = look.color ? readableOn(look.color) : BRAND.cyan;
	return `<rect x="4" y="4" width="${width - 8}" height="${height - 8}" rx="14" fill="none" stroke="${stroke}" stroke-width="6"/>`;
}

function offlineBadge(size: number, x: number, y: number): string {
	return (
		`<circle cx="${x + size / 2}" cy="${y + size / 2}" r="${size / 2 + 4}" fill="${BRAND.danger}"/>` +
		icon("offline", x, y, size, "#ffffff")
	);
}

/** A 144x144 key image. */
export function renderKey(look: Look): string {
	const size = 144;
	const fg = look.state === "off" ? "#8b8ba3" : look.color ? readableOn(look.color) : BRAND.text;
	const muted = look.state === "off" || look.color ? fg : BRAND.muted;
	const parts: string[] = [background(look, size, size)];

	if (look.main) {
		if (look.icon) {
			parts.push(icon(look.icon, 10, 10, 22, fg, 0.85));
		}
		parts.push(
			text(look.top ?? "", { x: look.icon ? 82 : 72, y: 24, width: look.icon ? 104 : 128, max: 22, min: 13, color: muted, weight: 600 }),
		);
		parts.push(text(look.main, { x: 72, y: 80, width: 132, max: 68, min: 18, color: fg, weight: 800 }));
		parts.push(text(look.bottom ?? "", { x: 72, y: 124, width: 128, max: 20, min: 12, color: muted, weight: 600 }));
	} else {
		parts.push(text(look.top ?? "", { x: 72, y: 22, width: 128, max: 20, min: 12, color: muted, weight: 600 }));
		if (look.icon) {
			parts.push(icon(look.icon, 44, look.top ? 40 : 30, 56, fg));
		}
		parts.push(text(look.bottom ?? "", { x: 72, y: 120, width: 128, max: 22, min: 12, color: fg, weight: 700 }));
	}
	parts.push(ring(look, size, size));

	let body = parts.join("");
	if (look.offline) {
		body = `<g opacity="0.35">${body}</g>${offlineBadge(26, 108, 10)}`;
	}
	return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">${body}</svg>`;
}

export type StripLook = Look & {
	/** A gauge along the bottom, e.g. stocks left */
	bar?: { value: number; max: number };
};

/** A 200x100 touch strip image, for one dial. */
export function renderStrip(look: StripLook): string {
	const width = 200;
	const height = 100;
	const fg = look.state === "off" ? "#8b8ba3" : look.color ? readableOn(look.color) : BRAND.text;
	const muted = look.state === "off" || look.color ? fg : BRAND.muted;
	const parts: string[] = [background(look, width, height)];

	if (look.icon) {
		parts.push(icon(look.icon, 10, 8, 20, fg, 0.9));
	}
	parts.push(
		text(look.top ?? "", { x: look.icon ? 38 : 12, y: 18, width: look.icon ? 152 : 176, max: 17, min: 11, color: muted, weight: 600, anchor: "start" }),
	);
	parts.push(text(look.main ?? "", { x: 100, y: 54, width: 184, max: 40, min: 14, color: fg, weight: 800 }));
	parts.push(text(look.bottom ?? "", { x: 100, y: look.bar ? 80 : 84, width: 184, max: 16, min: 11, color: muted, weight: 600 }));

	if (look.bar && look.bar.max > 0) {
		const share = Math.max(0, Math.min(1, look.bar.value / look.bar.max));
		parts.push(`<rect x="12" y="92" width="176" height="4" rx="2" fill="${fg}" opacity="0.25"/>`);
		parts.push(`<rect x="12" y="92" width="${(176 * share).toFixed(1)}" height="4" rx="2" fill="${fg}"/>`);
	}
	parts.push(ring(look, width, height));

	let body = parts.join("");
	if (look.offline) {
		body = `<g opacity="0.35">${body}</g>${offlineBadge(20, 170, 10)}`;
	}
	return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">${body}</svg>`;
}

export const keyImage = (look: Look): string => svgDataUrl(renderKey(look));
export const stripImage = (look: StripLook): string => svgDataUrl(renderStrip(look));
