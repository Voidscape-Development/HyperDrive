/** Small helpers to draw the keys and touch strips as SVG. */

export const FONT = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif";

/** The keys' colors: flat black, with gold for text, icons and what's lit */
export const THEME = {
	background: "#0a0a0a",
	gold: "#d4af37",
	muted: "#8a7a4a",
	offBackground: "#000000",
	off: "#4a4436",
	danger: "#e5484d",
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
		`font-weight="${opts.weight ?? 700}" fill="${opts.color ?? THEME.gold}" text-anchor="${opts.anchor ?? "middle"}" ` +
		`dominant-baseline="central"${opts.opacity !== undefined ? ` opacity="${opts.opacity}"` : ""}>${escapeXml(fit.text)}</text>`
	);
}
