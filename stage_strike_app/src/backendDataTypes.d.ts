export interface HDCountryInfo {
    code: string;
    display_name: string;
    en_name: string;
}

export interface HDPlayerInfo {
    id?: [number, number];
    city?: string;
    state?: HDCountryInfo;
    country?: HDCountryInfo;
    online_avatar?: string;
    name: string;
    mergedName: string;
    mergedOnlyName: string;
    real_name: string;
    seed: number;
    pronoun?: string;
    sponsor_logo?: string;
    team?: string;
    twitter?: string;
    character: HDCharacterSelections;
}

export interface HDTeamInfo {
    score: number;
    teamName: string;
    player: Record<number, HDPlayerInfo>;
    losers: boolean;
    color: string;
}

export interface HDScoreInfo {
    best_of: number;
    best_of_text: string;
    match: string;
    phase: string;
    set_id: number;
    station?: string;
    team: Record<number, HDTeamInfo>;
}

export interface HDCharacterBase {
    codename: string;
    display_name: string;
    en_name: string;
    name: string;
}

export interface HDCharacterSelection extends HDCharacterBase {
    skin: number; // This is -1 if unset.
}

export type HDCharacterSelections = Record<number, HDCharacterSelection>;

export interface HDCharacterDb {
    [codename: string]: HDCharacterDbEntry;
}

export interface HDCharacterDbEntry extends HDCharacterBase {
    skins: HDCharacterSkin[];
}

export interface HDCharacterSkin {
    assets: HDCharacterSkinAssets;
}

export interface HDCharacterSkinAssets {
    art?: HDCharacterSkinAsset;
    "base_files/icon"?: HDCharacterSkinAsset;
    costume?: HDCharacterSkinAsset;
    css?: HDCharacterSkinAsset;
    full?: HDCharacterSkinAsset;
    profile?: HDCharacterSkinAsset;
}

export interface HDCharacterSkinAsset {
    asset: string; // Path to the asset
    average_size?: Point2D;
    image_size?: Point2D;
    rescaling_factor?: number;
    type?: string[];
    uncropped_edge?: string[];
}

export interface Point2D {
    x: number;
    y: number;
}

export type HDCharacters = Record<string, HDCharacterSelection>;

export interface HDSetEntrant {
    gamerTag: string;
    prefix?: string;
    name?: string;
    id: number[];
}

export interface HDSet {
    bracket_type: string;
    entrants: [HDSetEntrant, HDSetEntrant];
    id: number;
    isOnline?: boolean;
    isPools: boolean;
    p1_name: string;
    p1_seed?: number;
    p2_name: string;
    p2_seed?: number;
    round: string;
    round_name: string;
    station?: string;
    stream?: string;
    team1score: number;
    team2score: number;
    tournament_phase?: string;
}

export interface HDPlayerDbEntry {
    country_code: string;
    custom_textbox: string;
    prefixed_tag: string;
    gamerTag: string;
    mains?: HDMainsMap;
    name: string;
    prefix: string;
    pronoun: string;
    twitter: string;
}

export type HDCountryCode = string;

export interface HDCountryDb {
    [country_code: HDCountryCode]: HDCountryInfo
}

export type HDMainsMap = Record<string, HDMain[]>;

export type HDMain = [string, number, string];

export type HDPlayerDb = Record<string, HDPlayerDbEntry>;

export interface HDState {
    score: {
        [scoreboard: number]: HDScoreInfo;
        ruleset: object;
    };
    game?: {
        name: string;
        smashgg_id: number;
        logo?: string;
        codename?: string;
    };
    tournamentInfo: {
        tournamentName?: string;
        address?: string;
        eventName?: string;
        shortLink?: string;
        endAt?: string;
        startAt?: string;
        eventEndAt?: string;
        eventStartAt?: string;
        initial_load?: boolean;
        numEntrants?: number;
    };
}

export interface HDGamesDb {
    [codename: string]: HDGameInfo
}

export interface HDGameInfo{
    challonge_game_id: number,
    has_stages: boolean
    has_variants: boolean
    locale: null | object
    name: string
    smashgg_game_id: number
    codename: string // This one isn't in the backend responses, I add it from the key.
}

export interface Delta {
    action: DeltaOpType;
    path: (string | number)[];
    type: string;
    value: any;
}

export type DeltaOpType =
     "type_changes"
   | "values_changed"
   | "dictionary_item_added"
   | "dictionary_item_removed"
   | "iterable_item_added"
   | "iterable_item_removed"
   | "attribute_added"
   | "attribute_removed"
   | "set_item_added"
   | "set_item_removed"
   | "repetition_change";
