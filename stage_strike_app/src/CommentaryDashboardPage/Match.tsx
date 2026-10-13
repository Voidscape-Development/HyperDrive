import {useState} from "react";
import {RefreshCw} from "lucide-react";
import {toast} from "sonner";
import i18n from "../i18n/config";
import {BASE_URL} from "../env";
import type {Bracket, BracketSet, BracketSlot, DashboardState, Scoreboard, Team} from "./types";
import {CharacterIcons, Empty, numbered, ordinal, SectionTitle, teamName, teamPlayers} from "./util";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {Card, CardContent} from "@/components/ui/card";
import {cn} from "@/lib/utils";

/** The set on the scoreboard: round, score, best of, and how big an upset it would be */
export function SetSummary({scoreboard, scoreboardNumber}: {scoreboard: Scoreboard; scoreboardNumber: number}) {
    const [refreshing, setRefreshing] = useState(false);
    const teams = [scoreboard.team?.["1"], scoreboard.team?.["2"]];

    const refresh = () => {
        setRefreshing(true);
        fetch(`${BASE_URL}/scoreboard${scoreboardNumber}-stats-refresh`)
            .then((res) => {
                if (!res.ok) throw new Error(res.statusText);
                toast.success(i18n.t("stats_refreshing"));
            })
            .catch(() => toast.error(i18n.t("stats_refresh_failed")))
            .finally(() => setRefreshing(false));
    };

    return <Card className="gap-3 py-4">
        <CardContent className="flex flex-col gap-3 px-4">
            <div className="flex flex-wrap items-center justify-center gap-1.5 text-center text-sm">
                {scoreboard.phase ? <Badge variant="secondary">{scoreboard.phase}</Badge> : null}
                {scoreboard.match ? <span className="font-semibold">{scoreboard.match}</span> : null}
                {scoreboard.best_of_text ? <Badge variant="outline">{scoreboard.best_of_text}</Badge> : null}
                {scoreboard.station && scoreboard.station !== -1 ? <Badge variant="outline">{i18n.t("station_n", {value: scoreboard.station})}</Badge> : null}
            </div>
            <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
                <TeamScoreName team={teams[0]} align="right"/>
                <div className="flex items-center gap-2 text-4xl font-bold tabular-nums">
                    <span style={{color: teams[0]?.color}}>{teams[0]?.score ?? 0}</span>
                    <span className="text-muted-foreground">–</span>
                    <span style={{color: teams[1]?.color}}>{teams[1]?.score ?? 0}</span>
                </div>
                <TeamScoreName team={teams[1]} align="left"/>
            </div>
            <UpsetLine scoreboard={scoreboard}/>
            <Button variant="outline" size="sm" className="self-center" onClick={refresh} disabled={refreshing}>
                <RefreshCw className={cn(refreshing && "animate-spin")}/>
                {i18n.t("refresh_stats")}
            </Button>
        </CardContent>
    </Card>;
}

function TeamScoreName({team, align}: {team?: Team; align: "left" | "right"}) {
    return <div className={cn("min-w-0", align === "right" ? "text-right" : "text-left")}>
        <div className="truncate font-semibold">{teamName(team) || "—"}</div>
        {team?.losers ? <Badge variant="outline" className="border-ban/60 text-ban">{i18n.t("losers_short")}</Badge> : null}
    </div>;
}

/** How many placement rounds apart the players are seeded: the upset if the lower seed wins */
function UpsetLine({scoreboard}: {scoreboard: Scoreboard}) {
    const p1 = teamPlayers(scoreboard.team?.["1"]);
    const p2 = teamPlayers(scoreboard.team?.["2"]);
    const factor = scoreboard.upset_factor;
    if (p1.length !== 1 || p2.length !== 1 || !factor || !p1[0].seed || !p2[0].seed) {
        return null;
    }
    const underdog = p1[0].seed > p2[0].seed ? p1[0] : p2[0];
    return <p className="text-center text-sm text-muted-foreground">
        {i18n.t("upset_if", {player: underdog.name, value: factor})}
    </p>;
}

/** The set's games: stage, characters and who won each */
export function GameLog({scoreboard}: {scoreboard: Scoreboard}) {
    const games = numbered(scoreboard.games);
    const colors = [scoreboard.team?.["1"]?.color, scoreboard.team?.["2"]?.color];

    return <section className="flex flex-col gap-2">
        <SectionTitle>{i18n.t("games")}</SectionTitle>
        {games.length === 0 ? <Empty>{i18n.t("no_games")}</Empty> :
            <ul className="flex flex-col divide-y rounded-md border text-sm">
                {games.map((g, i) => {
                    const stage = g.stageData?.display_name || g.stageData?.name || g.stageData?.en_name || g.stage;
                    return <li key={i} className={cn("grid grid-cols-[3.5rem_minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2 px-2 py-1.5", g.current && "bg-muted/50")}>
                        <span className="text-muted-foreground">{i18n.t("game", {value: g.game ?? i + 1})}</span>
                        <span className={cn("flex items-center justify-end gap-1", g.winner === 1 && "font-semibold")}>
                            {g.winner === 1 ? <WinDot color={colors[0]}/> : null}
                            <CharacterIcons characters={Object.fromEntries((g.characterData?.["1"] ?? []).map((c, j) => [String(j + 1), c]))}/>
                        </span>
                        <span className="max-w-32 truncate text-center text-xs text-muted-foreground">
                            {g.current && !g.winner ? <Badge variant="secondary">{i18n.t("playing")}</Badge> : (stage || "—")}
                        </span>
                        <span className={cn("flex items-center gap-1", g.winner === 2 && "font-semibold")}>
                            <CharacterIcons characters={Object.fromEntries((g.characterData?.["2"] ?? []).map((c, j) => [String(j + 1), c]))}/>
                            {g.winner === 2 ? <WinDot color={colors[1]}/> : null}
                        </span>
                    </li>;
                })}
            </ul>}
    </section>;
}

function WinDot({color}: {color?: string}) {
    return <span className="size-2 shrink-0 rounded-full bg-pick" style={color ? {backgroundColor: color} : undefined}/>;
}

/** Every bracket HyperDrive has, the main channel's first */
function brackets(state: DashboardState): {bracket: Bracket; phase?: string}[] {
    const list: {bracket: Bracket; phase?: string}[] = [];
    if (state.bracket?.bracket) {
        list.push({bracket: state.bracket.bracket, phase: state.bracket.phase});
    }
    for (const channel of Object.values(state.bracket?.channels ?? {})) {
        if (channel?.bracket && channel.bracket !== state.bracket?.bracket) {
            list.push({bracket: channel.bracket, phase: channel.phase});
        }
    }
    return list;
}

const norm = (s: string | undefined) => (s ?? "").trim().toLowerCase();

/** The scoreboard's set in a bracket: by its start.gg id, or by its two players */
function findSet(state: DashboardState, scoreboard: Scoreboard) {
    const all = brackets(state);
    const setId = scoreboard.set_id;
    if (setId !== undefined && setId !== null && setId !== "") {
        for (const {bracket, phase} of all) {
            const found = Object.values(bracket.sets ?? {}).find((s) => s.startggId != null && String(s.startggId) === String(setId));
            if (found) return {set: found, bracket, phase, swapped: false};
        }
    }

    const names = [1, 2].map((t) => {
        const team = scoreboard.team?.[String(t)];
        const players = teamPlayers(team);
        return [norm(team?.teamName), ...players.map((p) => norm(p.name))].filter(Boolean);
    });
    if (names[0].length === 0 || names[1].length === 0) return null;
    const matches = (slot: BracketSlot | undefined, candidates: string[]) => !!slot?.name && candidates.some((n) => norm(slot.name).endsWith(n));

    for (const {bracket, phase} of all) {
        for (const s of Object.values(bracket.sets ?? {})) {
            if (s.completed) continue;
            const [a, b] = s.players ?? [];
            if (matches(a, names[0]) && matches(b, names[1])) return {set: s, bracket, phase, swapped: false};
            if (matches(a, names[1]) && matches(b, names[0])) return {set: s, bracket, phase, swapped: true};
        }
    }
    return null;
}

function opponentText(target: BracketSet | undefined, slot: number) {
    const opponent = target?.players?.[1 - slot];
    if (!opponent) return null;
    if (opponent.bye) return null;
    if (opponent.name && !opponent.pending) return opponent.name;
    return opponent.source || i18n.t("tbd");
}

/** Rows of what happens to each player depending on who wins */
function stakes(set: BracketSet, bracket: Bracket): {label: string; text: string; good: boolean}[] {
    const sets = bracket.sets ?? {};
    const names = (set.players ?? []).map((p) => p?.name || "");

    if (set.isGrandFinal && !set.isReset) {
        const hasReset = Object.values(sets).some((s) => s.isReset);
        // The winners side's player is in the first slot
        return [
            {label: i18n.t("if_wins", {player: names[0] || i18n.t("winners_side")}), text: i18n.t("stakes_champion"), good: true},
            {
                label: i18n.t("if_wins", {player: names[1] || i18n.t("losers_side")}),
                text: hasReset ? i18n.t("stakes_reset") : i18n.t("stakes_champion"),
                good: !hasReset,
            },
        ];
    }

    const winTo = set.nextWin ? sets[set.nextWin.set] : undefined;
    const loseTo = set.nextLose ? sets[set.nextLose.set] : undefined;

    let winner;
    if (winTo && set.nextWin) {
        const vs = opponentText(winTo, set.nextWin.slot);
        winner = vs ? i18n.t("stakes_to_vs", {round: winTo.roundName, player: vs}) : i18n.t("stakes_to", {round: winTo.roundName});
    } else if (bracket.progressionsOut) {
        winner = i18n.t("stakes_advances");
    } else {
        winner = i18n.t("stakes_champion");
    }

    let loser;
    if (loseTo && set.nextLose) {
        const vs = opponentText(loseTo, set.nextLose.slot);
        loser = vs ? i18n.t("stakes_to_vs", {round: loseTo.roundName, player: vs}) : i18n.t("stakes_to", {round: loseTo.roundName});
        if (set.loserPlacement) {
            loser += ` ${i18n.t("stakes_out_there", {place: ordinal(set.loserPlacement)})}`;
        }
    } else if (set.loserPlacement) {
        loser = i18n.t("stakes_out", {place: ordinal(set.loserPlacement)});
    } else {
        loser = i18n.t("stakes_out_unknown");
    }

    return [
        {label: i18n.t("winner"), text: winner, good: true},
        {label: i18n.t("loser"), text: loser, good: false},
    ];
}

/** What's at stake: where the winner and the loser of the set go next */
export function BracketStakes({state, scoreboard}: {state: DashboardState; scoreboard: Scoreboard}) {
    const found = findSet(state, scoreboard);

    let body;
    if (!found) {
        body = <Empty>{i18n.t("stakes_not_found")}</Empty>;
    } else {
        body = <dl className="grid grid-cols-[auto_1fr] items-baseline gap-x-3 gap-y-1.5 text-sm">
            {stakes(found.set, found.bracket).map((row, i) => <div key={i} className="contents">
                <dt><Badge variant="outline" className={cn("max-w-40 truncate", row.good ? "border-pick/60 text-pick" : "border-ban/60 text-ban")}>{row.label}</Badge></dt>
                <dd>{row.text}</dd>
            </div>)}
        </dl>;
    }

    return <section className="flex flex-col gap-2">
        <SectionTitle>{i18n.t("bracket_stakes")}{found?.phase ? ` · ${found.phase}` : ""}</SectionTitle>
        {body}
    </section>;
}
