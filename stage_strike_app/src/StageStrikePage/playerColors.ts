// Tailwind classes for each strike player (0 or 1), written out in full so
// Tailwind finds them

/** A filled button or badge in the player's color */
export const PLAYER_FILL = [
  "bg-p1 text-zinc-950 hover:bg-p1/90",
  "bg-p2 text-zinc-950 hover:bg-p2/90",
];

/** An outlined button in the player's color */
export const PLAYER_OUTLINE = [
  "border-p1/60 text-p1 hover:bg-p1/10 hover:text-p1",
  "border-p2/60 text-p2 hover:bg-p2/10 hover:text-p2",
];

export const PLAYER_TEXT = ["text-p1", "text-p2"];

export const PLAYER_BG = ["bg-p1", "bg-p2"];

/** The player's color as --color, for the CSS that mixes it */
export const PLAYER_VAR = ["[--color:var(--p1)]", "[--color:var(--p2)]"];
