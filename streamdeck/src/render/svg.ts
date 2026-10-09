/** Small helpers to draw the keys and touch strips as SVG. */

export const FONT = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif";

/** HyperDrive's colors, from assets/icons/icon.svg */
export const BRAND = {
	spaceLight: "#4c2fd6",
	spaceMid: "#22176e",
	spaceDark: "#0b0b2b",
	cyan: "#22d3ee",
	violet: "#8b5cf6",
	pink: "#ec4899",
	text: "#ffffff",
	muted: "#a5b4fc",
	off: "#3f3f55",
	danger: "#f43f5e",
};

export function escapeXml(text: string): string {
	return text.replace(/[<>&"']/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&apos;" })[c]!);
}

/** An image Stream Deck takes: setImage and pixmap feedback both accept it. */
export function svgDataUrl(svg: string): string {
	return `data:image/svg+xml;base64,${Buffer.from(svg, "utf8").toString("base64")}`;
}

// Rough average glyph width of a bold sans-serif, as a share of the font size
const CHAR_WIDTH = 0.6;

/**
 * The font size that fits text in a width, between min and max. Text that
 * doesn't fit at min is cut with an ellipsis.
 */
export function fitText(text: string, width: number, max: number, min: number): { text: string; size: number } {
	const length = Math.max([...text].length, 1);
	const size = Math.floor(Math.min(max, width / (length * CHAR_WIDTH)));
	if (size >= min) {
		return { text, size };
	}
	const chars = Math.max(Math.floor(width / (min * CHAR_WIDTH)) - 1, 1);
	return { text: [...text].slice(0, chars).join("") + "…", size: min };
}

export function text(
	value: string,
	opts: {
		x: number;
		y: number;
		width: number;
		max: number;
		min: number;
		color?: string;
		weight?: number;
		anchor?: "start" | "middle" | "end";
		opacity?: number;
	},
): string {
	if (!value) {
		return "";
	}
	const fit = fitText(value, opts.width, opts.max, opts.min);
	return (
		`<text x="${opts.x}" y="${opts.y}" font-family="${FONT}" font-size="${fit.size}" ` +
		`font-weight="${opts.weight ?? 700}" fill="${opts.color ?? BRAND.text}" text-anchor="${opts.anchor ?? "middle"}" ` +
		`dominant-baseline="central"${opts.opacity !== undefined ? ` opacity="${opts.opacity}"` : ""}>${escapeXml(fit.text)}</text>`
	);
}

function channels(hex: string): [number, number, number] {
	const h = hex.replace("#", "").slice(0, 6);
	return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)) as [number, number, number];
}

/** Mixes a color with black (amount < 0) or white (amount > 0). */
export function shade(hex: string, amount: number): string {
	const target = amount < 0 ? 0 : 255;
	const a = Math.abs(amount);
	return (
		"#" +
		channels(hex)
			.map((c) => Math.round(c + (target - c) * a))
			.map((c) => c.toString(16).padStart(2, "0"))
			.join("")
	);
}

/** White or near-black, whichever reads better on the color. */
export function readableOn(hex: string): string {
	const [r, g, b] = channels(hex).map((c) => {
		const s = c / 255;
		return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
	});
	const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
	return luminance > 0.4 ? "#111122" : "#ffffff";
}
