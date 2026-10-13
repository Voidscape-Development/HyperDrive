import {BASE_URL} from "../env";
import type {CharacterSelection} from "./useHdData";

export interface CharacterSkin {
  assets?: Record<string, {asset?: string}>;
}

/** A character of the loaded game */
export interface Character {
  en_name: string;
  codename?: string;
  name?: string;
  display_name?: string;
  skins?: CharacterSkin[];
}

/** The loaded game's characters, keyed by en_name */
export type Characters = Record<string, Character>;

/**
 * The character from the character list matching a scoreboard selection.
 * Codenames are matched first, as some skins report another character's en_name.
 */
export function FindCharacter(characters: Characters, selection: CharacterSelection | null | undefined): Character | null {
  if (!selection) return null;
  if (selection.codename) {
    const found = Object.values(characters).find((c) => c.codename === selection.codename);
    if (found) return found;
  }
  return characters[selection.en_name] ?? null;
}

function assetUrl(path: string | undefined) {
  if (!path) return null;
  return `${BASE_URL}/${path.replace(/^\.\//, "")}`;
}

/** URL of a character's icon for a skin, falling back to its first skin */
export function CharacterIcon(character: Character | null, skin = 0) {
  const skins = character?.skins ?? [];
  const skinData = skins[skin] ?? skins[0];
  const assets = skinData?.assets ?? {};
  return assetUrl(
    assets["base_files/icon"]?.asset
    ?? Object.values(assets).find((a) => a?.asset)?.asset
  );
}

export function CharacterName(character: Character | null) {
  return character?.display_name ?? character?.name ?? character?.en_name ?? "";
}
