/**
 * Line icons on a 24x24 grid, drawn with a round 2px stroke and no fill.
 */
export const ICONS = {
	plus: "M12 5v14M5 12h14",
	minus: "M5 12h14",
	swap: "M4 8h14M14 4l4 4-4 4M20 16H6M10 12l-4 4 4 4",
	reset: "M3 12a9 9 0 1 0 3-6.7M3 4v5h5",
	color: "M12 3c4 5 6 8 6 11a6 6 0 0 1-12 0c0-3 2-6 6-11z",
	load: "M12 4v11M7 10l5 5 5-5M5 20h14",
	queue: "M9 6h11M9 12h11M9 18h11M4 6h1M4 12h1M4 18h1",
	window: "M3 5h18v14H3zM3 9h18",
	eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
	eyeOff: "M2 12s4-7 10-7c2 0 3.8.8 5.3 1.8M22 12s-4 7-10 7c-2 0-3.8-.8-5.3-1.8M4 4l16 16",
	layers: "M12 3l9 5-9 5-9-5zM3 13l9 5 9-5",
	folder: "M3 6h6l2 2h10v11H3z",
	tag: "M3 3h8l10 10-8 8L3 11zM7.5 6.5h.01",
	user: "M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM4 21c0-4 4-6 8-6s8 2 8 6",
	users: "M9 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM2 21c0-4 3-6 7-6s7 2 7 6M16 4a4 4 0 0 1 0 8M19 15c2 1 3 3 3 6",
	next: "M5 5l10 7-10 7zM19 5v14",
	undo: "M9 14L4 9l5-5M4 9h10a6 6 0 0 1 0 12h-3",
	redo: "M15 14l5-5-5-5M20 9H10a6 6 0 0 0 0 12h3",
	trophy: "M8 4h8v5a4 4 0 0 1-8 0zM8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 13v4M8 21h8M10 17h4",
	scissors: "M6 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM6 15a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM20 4L8.1 15.9M14.5 14.5L20 20M8.1 8.1L12 12",
	bracket: "M3 5h5v6h5M3 17h5v-6M13 11h8",
	focus: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-5-5",
	play: "M7 5l12 7-12 7z",
	left: "M15 6l-6 6 6 6",
	right: "M9 6l6 6-6 6",
	expand: "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5",
	follow: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
	stocks: "M12 21s-8-5-8-11a5 5 0 0 1 8-3 5 5 0 0 1 8 3c0 6-8 11-8 11z",
	offline: "M2 2l20 20M9 2v5M15 2v5M6 7h12v4a6 6 0 0 1-9.6 4.8M12 17v5",
} as const;

export type IconName = keyof typeof ICONS;

/** An icon placed at (x, y), size pixels wide. */
export function icon(name: IconName, x: number, y: number, size: number, color: string, opacity = 1): string {
	const scale = size / 24;
	return (
		`<g transform="translate(${x} ${y}) scale(${scale})" fill="none" stroke="${color}" stroke-width="2" ` +
		`stroke-linecap="round" stroke-linejoin="round" opacity="${opacity}"><path d="${ICONS[name]}"/></g>`
	);
}
