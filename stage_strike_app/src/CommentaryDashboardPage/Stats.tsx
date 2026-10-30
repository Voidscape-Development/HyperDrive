import i18n from "../i18n/config";
import type {HeadToHeadSet, HistorySet, LastSet} from "./types";
import {CharacterIcons, Empty, ordinal, scoreText, SectionTitle, toNumber} from "./util";
import {Badge} from "@/components/ui/badge";
import {Spinner} from "@/components/ui/spinner";
import {cn} from "@/lib/utils";

/** null: the stats can't be had (not 1v1, or the provider has none); undefined: loading */
type Loadable<T> = T[] | null | undefined;

function Status<T>({items, empty}: {items: Loadable<T>; empty: string}) {
    if (items === undefined) {
        return <p className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner/>{i18n.t("loading")}</p>;
    }
    if (items === null) {
        return <Empty>{i18n.t("stats_unavailable")}</Empty>;
    }
    return <Empty>{empty}</Empty>;
}

/** The player's last sets in this event, most recent first */
export function LastSets({sets}: {sets: Loadable<LastSet>}) {
    // The round shows when the column is wide enough to leave the opponent's name whole
    return <section className="@container flex flex-col gap-2">
        <SectionTitle>{i18n.t("last_sets")}</SectionTitle>
        {!sets?.length ? <Status items={sets} empty={i18n.t("no_last_sets")}/> :
            <ul className="flex flex-col divide-y rounded-md border text-sm">
                {sets.map((s, i) => {
                    const own = toNumber(s.player_score) ?? 0;
                    const theirs = toNumber(s.oponent_score) ?? 0;
                    const won = own > theirs;
                    return <li key={i} className="flex items-center gap-2 px-2 py-1.5">
                        <Badge variant="outline" className={cn("w-6 justify-center px-0", won ? "border-pick/60 text-pick" : "border-ban/60 text-ban")}>
                            {won ? i18n.t("win_short") : i18n.t("loss_short")}
                        </Badge>
                        <span className="w-10 shrink-0 text-center font-semibold tabular-nums">
                            {scoreText(s.player_score)}–{scoreText(s.oponent_score)}
                        </span>
                        <CharacterIcons characters={s.player_char?.character}/>
                        <span className="min-w-0 flex-1 truncate">
                            <span className="text-muted-foreground">{i18n.t("vs")} </span>
                            {s.oponent_team ? <span className="text-muted-foreground">{s.oponent_team} | </span> : null}
                            {s.oponent_name}
                            {s.oponent_seed ? <span className="text-muted-foreground"> ({i18n.t("seed_n", {value: s.oponent_seed})})</span> : null}
                        </span>
                        <CharacterIcons characters={s.oponent_char?.character}/>
                        <span className="hidden shrink-0 text-xs text-muted-foreground @lg:inline">
                            {[s.phase_name, s.phase_id].filter(Boolean).join(" ")} · {s.round_name}
                        </span>
                    </li>;
                })}
            </ul>}
    </section>;
}

/** Placement rounds above (positive) or below the seed */
function SprBadge({spr}: {spr: number | null | undefined}) {
    if (spr === null || spr === undefined) return null;
    const label = spr > 0 ? `+${spr}` : String(spr);
    return <Badge
        variant="outline"
        title={i18n.t("spr_hint")}
        className={cn("tabular-nums", spr > 0 && "border-pick/60 text-pick", spr < 0 && "border-ban/60 text-ban")}
    >{i18n.t("spr", {value: label})}</Badge>;
}

/** The player's results at past events */
export function PastEvents({sets}: {sets: Loadable<HistorySet>}) {
    return <section className="flex flex-col gap-2">
        <SectionTitle>{i18n.t("past_events")}</SectionTitle>
        {!sets?.length ? <Status items={sets} empty={i18n.t("no_past_events")}/> :
            <ul className="flex flex-col divide-y rounded-md border text-sm">
                {sets.map((s, i) => <li key={i} className="flex items-center gap-2 px-2 py-1.5">
                    <span className="w-12 shrink-0 text-right font-semibold tabular-nums">{ordinal(s.placement)}</span>
                    <span className="min-w-0 flex-1">
                        <span className="block truncate">{s.tournament_name}</span>
                        <span className="block truncate text-xs text-muted-foreground">
                            {[s.event_name, s.entrants ? i18n.t("entrants_n", {value: s.entrants}) : null,
                                [s.event_date_month, s.event_date_year].filter(Boolean).join(" ")].filter(Boolean).join(" · ")}
                        </span>
                    </span>
                    {s.seed ? <span className="shrink-0 text-xs text-muted-foreground">{i18n.t("seed_n", {value: s.seed})}</span> : null}
                    <SprBadge spr={s.spr}/>
                </li>)}
            </ul>}
    </section>;
}

/** The sets the two players played against each other, from team 1's side */
export function HeadToHead({sets, names, colors, loading}: {
    sets: Loadable<HeadToHeadSet>;
    names: [string, string];
    // The teams' colors, the players' colors without them
    colors?: [string | undefined, string | undefined];
    loading?: boolean;
}) {
    const wins = [0, 0];
    for (const s of sets ?? []) {
        if (s.winner === 0 || s.winner === 1) wins[s.winner] += 1;
    }

    return <section className="flex flex-col gap-2">
        <SectionTitle action={loading ? <Spinner className="size-3.5"/> : null}>{i18n.t("head_to_head")}</SectionTitle>
        {!sets?.length ? <Status items={sets} empty={i18n.t("no_head_to_head")}/> : <>
            <div className="flex items-center justify-center gap-3 rounded-md border bg-muted/30 px-3 py-2">
                <span className="min-w-0 flex-1 truncate text-right text-sm">{names[0]}</span>
                <span className="text-2xl font-bold tabular-nums">
                    <span className="text-p1" style={{color: colors?.[0]}}>{wins[0]}</span>
                    <span className="px-1 text-muted-foreground">–</span>
                    <span className="text-p2" style={{color: colors?.[1]}}>{wins[1]}</span>
                </span>
                <span className="min-w-0 flex-1 truncate text-sm">{names[1]}</span>
            </div>
            <ul className="flex flex-col divide-y rounded-md border text-sm">
                {sets.map((s, i) => <li key={i} className="flex items-center gap-2 px-2 py-1.5">
                    <CharacterIcons characters={s.p1_char?.character}/>
                    <span className="shrink-0 font-semibold tabular-nums">
                        <span className={cn(s.winner === 0 && "text-p1")} style={s.winner === 0 ? {color: colors?.[0]} : undefined}>{scoreText(s.score?.[0])}</span>
                        –
                        <span className={cn(s.winner === 1 && "text-p2")} style={s.winner === 1 ? {color: colors?.[1]} : undefined}>{scoreText(s.score?.[1])}</span>
                    </span>
                    <CharacterIcons characters={s.p2_char?.character}/>
                    <span className="min-w-0 flex-1">
                        <span className="block truncate">{s.tournament}{s.online ? <Badge variant="secondary" className="ml-1.5">{i18n.t("online")}</Badge> : null}</span>
                        <span className="block truncate text-xs text-muted-foreground">
                            {[s.event, s.round, s.timestamp ? new Date(s.timestamp * 1000).toLocaleDateString() : null].filter(Boolean).join(" · ")}
                        </span>
                    </span>
                </li>)}
            </ul>
        </>}
    </section>;
}
