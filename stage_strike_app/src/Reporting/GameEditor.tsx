import React from "react";
import {useSelector} from "react-redux";
import {Plus, X} from "lucide-react";
import type {ReduxState} from "../redux/store";
import type {HDCharacterDbEntry} from "../backendDataTypes";
import {characterIcon} from "../ScoreboardPage/CharSelector";
import type {Game, ReportingSet} from "./api";
import {emptyGame, entrantName, finalScores, gamesForScore, gamesScore, gamesWinner, winsNeeded} from "./sets";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {cn} from "@/lib/utils";

/*
 * A set's games: who won each one, and optionally with which characters and
 * on which stage. Used by the players' station, the Admin page's report
 * dialog and the Approval page's edit.
 */

interface StageInfo {
    codename: string;
    name?: string;
    display_name?: string;
}

function useGameAssets() {
    const characters = useSelector((s: ReduxState) => s.hdCharacters.characters) as Record<string, HDCharacterDbEntry>;
    const game = useSelector((s: ReduxState) => (s.hdState.hdState as any)?.game);
    const stages: StageInfo[] = Object.values(game?.stages ?? {}) as StageInfo[];
    stages.sort((a, b) => stageName(a).localeCompare(stageName(b)));
    return {characters, stages: game?.has_stages ? stages : []};
}

const stageName = (stage: StageInfo | undefined) => stage?.display_name || stage?.name || stage?.codename || "";

/** A character, picked from a searchable grid */
function CharacterPicker({value, label, onChange, large}: {
    value: string | undefined;
    label: string;
    onChange: (value: string | null) => void;
    large?: boolean;
}) {
    const {characters} = useGameAssets();
    const [open, setOpen] = React.useState(false);
    const [search, setSearch] = React.useState("");
    const list = Object.values(characters)
        .filter((c) => c.en_name && c.display_name?.toLowerCase().includes(search.trim().toLowerCase()))
        .sort((a, b) => (a.display_name ?? "").localeCompare(b.display_name ?? ""));
    const current = value ? characters[value] : undefined;
    const icon = characterIcon(current);

    return (
        <Popover open={open} onOpenChange={(o) => {
            setOpen(o);
            setSearch("");
        }}>
            <PopoverTrigger asChild>
                <button
                    type="button"
                    aria-label={`${label}: ${current?.display_name ?? "no character"}`}
                    title={label}
                    className={cn(
                        "flex min-w-0 cursor-pointer items-center gap-1.5 rounded-lg border bg-background px-2 text-left text-xs outline-none hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50",
                        large ? "h-11" : "h-9",
                        !current && "border-dashed text-muted-foreground",
                    )}
                >
                    {icon ? <img alt="" src={icon} className="size-6 shrink-0 object-contain"/> : <span className="size-6 shrink-0 rounded bg-muted"/>}
                    <span className="truncate">{current?.display_name ?? "Character"}</span>
                </button>
            </PopoverTrigger>
            <PopoverContent className="w-80 p-2" align="start">
                <Input autoFocus placeholder="Search characters" aria-label="Search characters" value={search} onChange={(e) => setSearch(e.target.value)} className="mb-2"/>
                <div className="grid max-h-72 grid-cols-5 gap-1 overflow-y-auto">
                    {list.map((c) => {
                        const src = characterIcon(c);
                        return (
                            <button
                                key={c.en_name}
                                type="button"
                                title={c.display_name}
                                aria-label={c.display_name}
                                onClick={() => {
                                    onChange(c.en_name);
                                    setOpen(false);
                                }}
                                className={cn(
                                    "flex aspect-square cursor-pointer flex-col items-center justify-center gap-0.5 rounded-md border p-0.5 text-[9px] leading-tight outline-none hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50",
                                    c.en_name === value ? "border-brand bg-accent" : "border-transparent",
                                )}
                            >
                                {src ? <img alt="" src={src} className="size-8 object-contain"/> : <span className="line-clamp-2 text-center">{c.display_name}</span>}
                            </button>
                        );
                    })}
                </div>
                {list.length === 0 && <p className="p-3 text-center text-sm text-muted-foreground">No character found</p>}
                {value && (
                    <Button variant="ghost" size="sm" className="mt-2 w-full" onClick={() => {
                        onChange(null);
                        setOpen(false);
                    }}>
                        <X/>No character
                    </Button>
                )}
            </PopoverContent>
        </Popover>
    );
}

interface GameEditorProps {
    set: ReportingSet;
    games: Game[];
    onChange: (games: Game[]) => void;
    /** Bigger buttons, for the players' station */
    large?: boolean;
}

export function GameEditor({set, games, onChange, large}: GameEditorProps) {
    const {characters, stages} = useGameAssets();
    const hasCharacters = Object.keys(characters).length > 0;
    const needed = winsNeeded(set.bestOf);
    const [score1, score2] = gamesScore(games);
    const winner = gamesWinner(games);
    const decided = Math.max(score1, score2) >= needed;
    // The games shown: at least a best of's worth, and one more while undecided
    const shown = Math.max(games.length, Math.min(needed * 2 - 1, games.length + (decided ? 0 : 1)), 1);
    const rows = Array.from({length: shown}, (_, i) => games[i] ?? emptyGame());

    const update = (index: number, change: (game: Game) => Game) => {
        const next = [...rows];
        next[index] = change(next[index]);
        onChange(trim(next));
    };

    const setWinner = (index: number, team: 1 | 2) => update(index, (game) => {
        if (game.winner === team) {
            return {...game, winner: null};
        }
        // The characters of the game before, when none are set yet
        const before = rows[index - 1];
        const characters = {...game.characters};
        for (const t of ["1", "2"] as const) {
            if (!characters[t]?.length && before?.characters[t]?.length) {
                characters[t] = [...before.characters[t]!];
            }
        }
        return {...game, winner: team, characters};
    });

    const setCharacter = (index: number, team: "1" | "2", value: string | null) => update(index, (game) => {
        const list = [...(game.characters[team] ?? [])];
        if (value) {
            list[0] = value;
        } else {
            list.splice(0, 1);
        }
        return {...game, characters: {...game.characters, [team]: list}};
    });

    const teamButton = (index: number, game: Game, team: 1 | 2) => {
        const won = game.winner === team;
        return (
            <button
                type="button"
                aria-pressed={won}
                onClick={() => setWinner(index, team)}
                className={cn(
                    "flex min-w-0 flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-lg border px-2 font-semibold outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                    large ? "h-12 text-sm" : "h-9 text-[13px]",
                    won ? "border-brand bg-brand-soft text-foreground" : "text-muted-foreground hover:bg-accent",
                )}
            >
                <span className="truncate">{entrantName(set, team)}</span>
                {won && <span className="shrink-0 text-[11px] font-bold text-brand-text uppercase">won</span>}
            </button>
        );
    };

    return (
        <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
                <span className="text-xs font-semibold text-muted-foreground">Final score</span>
                <div className="flex flex-wrap gap-1.5">
                    {finalScores(set.bestOf).map(([a, b]) => {
                        const current = score1 === a && score2 === b;
                        return (
                            <Button
                                key={`${a}-${b}`}
                                type="button"
                                variant={current ? "default" : "outline"}
                                size={large ? "lg" : "sm"}
                                className="tabular-nums"
                                onClick={() => onChange(gamesForScore([a, b], games))}
                            >
                                {a} – {b}
                            </Button>
                        );
                    })}
                </div>
                <span className="text-xs text-muted-foreground">
                    {entrantName(set, 1)} first. Or set each game's winner below.
                </span>
            </div>

            <ol className="flex flex-col gap-2">
                {rows.map((game, i) => (
                    <li key={i} className={cn("flex flex-col gap-2 rounded-xl border p-2.5", game.winner == null && "border-dashed")}>
                        <div className="flex items-center gap-2">
                            <span className="w-14 shrink-0 text-xs font-semibold text-muted-foreground">Game {i + 1}</span>
                            {teamButton(i, game, 1)}
                            {teamButton(i, game, 2)}
                            {decided && i === rows.length - 1 && (
                                <Button type="button" variant="ghost" size="icon-sm" aria-label={`Remove game ${i + 1}`} title="Remove this game"
                                    onClick={() => onChange(trim(rows.slice(0, i)))}>
                                    <X/>
                                </Button>
                            )}
                        </div>
                        {(hasCharacters || stages.length > 0) && (
                            <div className="flex flex-wrap items-center gap-2 pl-16">
                                {hasCharacters && (["1", "2"] as const).map((team) => (
                                    <div key={team} className="min-w-0 flex-1 basis-32">
                                        <CharacterPicker
                                            large={large}
                                            label={`${entrantName(set, Number(team) as 1 | 2)}'s character in game ${i + 1}`}
                                            value={game.characters[team]?.[0]}
                                            onChange={(value) => setCharacter(i, team, value)}
                                        />
                                    </div>
                                ))}
                                {stages.length > 0 && (
                                    <Select value={game.stage ?? "none"} onValueChange={(v) => update(i, (g) => ({...g, stage: v === "none" ? null : v}))}>
                                        <SelectTrigger aria-label={`Stage of game ${i + 1}`} className={cn("min-w-0 flex-1 basis-32", large && "h-11")}>
                                            <SelectValue/>
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="none">No stage</SelectItem>
                                            {stages.map((s) => <SelectItem key={s.codename} value={s.codename}>{stageName(s)}</SelectItem>)}
                                        </SelectContent>
                                    </Select>
                                )}
                            </div>
                        )}
                    </li>
                ))}
            </ol>

            {decided && rows.length < 15 && (
                <Button type="button" variant="ghost" size="sm" className="self-start" onClick={() => onChange([...trim(rows), emptyGame()])}>
                    <Plus/>Another game
                </Button>
            )}

            <div className={cn("rounded-xl border px-3.5 py-2.5 text-sm", winner ? "bg-brand-soft" : "bg-card")}>
                <span className="font-semibold tabular-nums">{entrantName(set, 1)} {score1} – {score2} {entrantName(set, 2)}</span>
                <span className="text-muted-foreground">
                    {" · "}{winner ? `${entrantName(set, winner)} wins` : games.length ? "Tied: no winner yet" : "No games yet"}
                </span>
            </div>
        </div>
    );
}

/** Games without the empty ones at the end, unless they have characters or a stage */
function trim(games: Game[]): Game[] {
    const result = [...games];
    while (result.length) {
        const last = result[result.length - 1];
        const used = last.winner != null || last.stage || last.characters["1"]?.length || last.characters["2"]?.length;
        if (used) {
            break;
        }
        result.pop();
    }
    return result;
}
