import {useState} from "react";
import i18n from "../i18n/config";
import {BASE_URL} from "../env";
import type {CharacterMap, CharacterRef, Person, Team} from "./types";
import {Tooltip, TooltipContent, TooltipTrigger} from "@/components/ui/tooltip";
import {cn} from "@/lib/utils";

/** URL of a file HyperDrive serves, from the path the state has (./user_data/...) */
export function assetUrl(path: string | null | undefined): string | null {
    if (!path) return null;
    if (/^https?:\/\//.test(path)) return path;
    return `${BASE_URL}/${path.replace(/^\.\//, "")}`;
}

export function characterName(character: CharacterRef | null | undefined) {
    return character?.display_name || character?.name || character?.en_name || "";
}

function characterIconUrl(character: CharacterRef | null | undefined) {
    const assets = character?.assets ?? {};
    return assetUrl(
        assets["base_files/icon"]?.asset
        ?? Object.values(assets).find((a) => a?.asset)?.asset
    );
}

/** The characters set, in order */
export function characterList(characters: CharacterMap | null | undefined): CharacterRef[] {
    return Object.entries(characters ?? {})
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([, c]) => c)
        .filter((c): c is CharacterRef => !!c && !!characterName(c));
}

/** A character's icon, with its name as a tooltip (or beside it, with showName) */
export function CharacterIcon({character, showName, className}: {
    character: CharacterRef;
    showName?: boolean;
    className?: string;
}) {
    const [errored, setErrored] = useState(false);
    const url = characterIconUrl(character);
    const name = characterName(character);
    const icon = url && !errored
        ? <img src={url} alt={name} className={cn("size-6 shrink-0 object-contain", className)} onError={() => setErrored(true)}/>
        : <span className={cn("rounded bg-muted px-1 text-xs", showName && "hidden")}>{name}</span>;

    if (showName) {
        return <span className="inline-flex items-center gap-1.5">{icon}<span>{name}</span></span>;
    }
    return <Tooltip>
        <TooltipTrigger asChild><span className="inline-flex">{icon}</span></TooltipTrigger>
        <TooltipContent>{name}</TooltipContent>
    </Tooltip>;
}

export function CharacterIcons({characters, className}: {characters: CharacterMap | null | undefined; className?: string}) {
    const list = characterList(characters);
    if (list.length === 0) return null;
    return <span className={cn("inline-flex flex-wrap items-center gap-0.5", className)}>
        {list.map((c, i) => <CharacterIcon key={i} character={c}/>)}
    </span>;
}

/** The players of a team, in order */
export function teamPlayers(team: Team | null | undefined): Person[] {
    return Object.entries(team?.player ?? {})
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([, p]) => p)
        .filter((p) => !!p);
}

/** "Sponsor | Tag" */
export function personName(person: Person | null | undefined) {
    if (!person?.name) return "";
    return person.team ? `${person.team} | ${person.name}` : person.name;
}

/** A team's name, or its players' names */
export function teamName(team: Team | null | undefined) {
    const players = teamPlayers(team).filter((p) => p.name);
    if (players.length === 1) return personName(players[0]);
    if (team?.teamName) return team.teamName;
    return players.map((p) => p.name).join(" / ");
}

/** The values of an object keyed "1", "2"... in order */
export function numbered<T>(values: Record<string, T> | null | undefined): T[] {
    return Object.entries(values ?? {})
        .filter(([k]) => /^\d+$/.test(k))
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([, v]) => v);
}

export function toNumber(value: unknown): number | null {
    const n = Number(value);
    return value === null || value === undefined || value === "" || Number.isNaN(n) ? null : n;
}

/** 1st, 2nd, 3rd... */
export function ordinal(n: number | null | undefined) {
    if (n === null || n === undefined) return "";
    const tens = n % 100;
    const suffix = tens >= 11 && tens <= 13 ? "th" : ({1: "st", 2: "nd", 3: "rd"}[n % 10] ?? "th");
    return `${n}${suffix}`;
}

/** A set score, "DQ" for -1 */
export function scoreText(score: unknown) {
    const n = toNumber(score);
    if (n === null) return "–";
    return n < 0 ? i18n.t("dq") : String(n);
}

/** When a set should start: "Now", "~15 min", "~1 h 05" */
export function etaText(minutes: number | null | undefined) {
    if (minutes === null || minutes === undefined) return null;
    if (minutes <= 0) return i18n.t("eta_now");
    if (minutes < 60) return i18n.t("eta_minutes", {value: minutes});
    return i18n.t("eta_hours", {hours: Math.floor(minutes / 60), minutes: String(minutes % 60).padStart(2, "0")});
}

export function clockTime(epochSeconds: number | null | undefined) {
    if (!epochSeconds) return null;
    return new Date(epochSeconds * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
}

/** A social media icon, from layout/icons. They're one color, so they're masks taking the text color. */
export function SocialIcon({platform, className}: {platform: string; className?: string}) {
    const url = `${BASE_URL}/layout/icons/${platform}.svg`;
    return <span
        aria-hidden
        className={cn("inline-block size-3.5 shrink-0 bg-current", className)}
        style={{maskImage: `url("${url}")`, WebkitMaskImage: `url("${url}")`, maskSize: "contain", WebkitMaskSize: "contain", maskRepeat: "no-repeat", WebkitMaskRepeat: "no-repeat", maskPosition: "center", WebkitMaskPosition: "center"}}
    />;
}

/** A section title inside a card */
export function SectionTitle({children, action}: {children: React.ReactNode; action?: React.ReactNode}) {
    return <div className="flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">{children}</h3>
        {action}
    </div>;
}

export function Empty({children}: {children: React.ReactNode}) {
    return <p className="text-sm text-muted-foreground">{children}</p>;
}
