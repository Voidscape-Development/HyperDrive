import {Minus, Plus} from "lucide-react";
import {shallowEqual, useSelector} from "react-redux";
import {toast} from "sonner";
import {dashboard} from "./api";
import {useStatus} from "./status";
import {useHd, type QueueSet} from "./stateTypes";
import {EmptyState, PageBody, PageHeader, Panel, PanelLink, useOptimistic} from "./ui";
import {LoadTournamentDialog} from "./EventControls";
import {scoreActions} from "../ScoreboardPage/scoreActions";
import {setProgress, teamDisplayName} from "../ScoreboardPage/setProgress";
import type {ReduxState} from "../redux/store";
import type {HDScoreInfo} from "../backendDataTypes";
import {Button} from "@/components/ui/button";
import {Switch} from "@/components/ui/switch";
import {cn} from "@/lib/utils";
import React from "react";

// Layout folders shown first under "On stream", when there are
const MAIN_LAYOUTS = ["scoreboard", "stream_queue", "completed_sets", "commentators", "bracket", "top_8", "starting_soon"];

export const queueSetName = (set: QueueSet) => {
    const team = (n: string) => {
        const t = set.team?.[n];
        const players = Object.values(t?.player ?? {}).map((p) => p?.name).filter(Boolean);
        return t?.teamName || players.join(" / ");
    };
    const a = set.p1_name || team("1") || "TBD";
    const b = set.p2_name || team("2") || "TBD";
    return `${a} vs ${b}`;
};

export const etaText = (set: QueueSet) => {
    if (set.onStream) {
        return "now";
    }
    if (set.eta) {
        return new Date(set.eta * 1000).toLocaleTimeString([], {hour: "numeric", minute: "2-digit"});
    }
    return "";
};

function LiveSet({number, score}: {number: number; score?: HDScoreInfo}) {
    if (!score?.team?.[1] || !score?.team?.[2]) {
        return <EmptyState>Scoreboard {number} has no set yet.</EmptyState>;
    }
    const progress = setProgress(score);
    const actions = scoreActions(number, score);
    const games = Object.entries((score as unknown as {games?: Record<string, {winner?: number | null}>}).games ?? {});

    const side = (team: 1 | 2) => {
        const t = score.team[team];
        const right = team === 2;
        return (
            <div className={cn("flex min-w-0 flex-col gap-1", right && "items-end text-right")}>
                <span className={cn("flex min-w-0 items-center gap-2", right && "flex-row-reverse")}>
                    <span aria-hidden className="size-2.5 shrink-0 rounded-sm" style={{backgroundColor: t?.color || undefined}}/>
                    <span className="truncate text-2xl font-bold">{teamDisplayName(t, team)}</span>
                </span>
                {t?.losers && <span className="text-xs font-bold text-warning">Losers</span>}
            </div>
        );
    };

    const scoreButtons = (team: 1 | 2) => (
        <div className={cn("flex items-center gap-2", team === 2 && "flex-row-reverse")}>
            <Button variant="secondary" size="icon-lg" aria-label={`Take a point from ${teamDisplayName(score.team[team], team)}`} onClick={() => actions.take(team)}>
                <Minus/>
            </Button>
            <span className="w-12 text-center text-5xl font-black tabular-nums">{progress.scores[team - 1]}</span>
            <Button variant="secondary" size="icon-lg" aria-label={`Add a point to ${teamDisplayName(score.team[team], team)}`} onClick={() => actions.add(team)}>
                <Plus/>
            </Button>
        </div>
    );

    return (
        <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-sm">
                <span className="flex items-center gap-1.5 text-[11px] font-bold tracking-wider text-brand-text uppercase">
                    <span aria-hidden className="size-1.5 rounded-full bg-brand"/>Live
                </span>
                <span className="font-semibold">{score.match || "No match name"}</span>
                <span className="text-muted-foreground">
                    {[score.phase, progress.bestOf ? `Best of ${progress.bestOf}` : null].filter(Boolean).join(" · ")}
                </span>
            </div>
            {/* Phones: a row per team. Wider: the teams face each other, as on stream */}
            <div className="flex flex-col gap-3 sm:hidden">
                {([1, 2] as const).map((team) => (
                    <div key={team} className="flex items-center justify-between gap-3">
                        {side(team)}
                        <div className="flex items-center gap-2">
                            <Button variant="secondary" size="icon-lg" aria-label={`Take a point from ${teamDisplayName(score.team[team], team)}`} onClick={() => actions.take(team)}>
                                <Minus/>
                            </Button>
                            <span className="w-10 text-center text-4xl font-black tabular-nums">{progress.scores[team - 1]}</span>
                            <Button variant="secondary" size="icon-lg" aria-label={`Add a point to ${teamDisplayName(score.team[team], team)}`} onClick={() => actions.add(team)}>
                                <Plus/>
                            </Button>
                        </div>
                    </div>
                ))}
            </div>
            <div className="hidden items-center gap-4 sm:grid sm:grid-cols-[minmax(0,1fr)_auto_auto_minmax(0,1fr)]">
                {side(1)}
                {scoreButtons(1)}
                {scoreButtons(2)}
                {side(2)}
            </div>
            <div className="flex flex-wrap items-center gap-2">
                {games.length > 0 && <span className="mr-1 text-xs text-muted-foreground">Games</span>}
                {games.map(([n, game]) => {
                    const winner = game?.winner;
                    const color = winner ? score.team[winner as 1 | 2]?.color : undefined;
                    return (
                        <span
                            key={n}
                            className={cn("rounded-md px-2.5 py-1 text-xs font-semibold", !winner && "border border-dashed text-muted-foreground")}
                            style={color ? {backgroundColor: `color-mix(in oklab, ${color} 25%, transparent)`} : undefined}
                        >
                            G{n}{winner ? ` ${teamDisplayName(score.team[winner as 1 | 2], winner)}` : ""}
                        </span>
                    );
                })}
                <div className="flex-1"/>
                <Button variant="secondary" onClick={actions.swap}>Swap teams</Button>
                <Button variant="secondary" onClick={actions.reset}>Reset score</Button>
            </div>
        </div>
    );
}

function UpNext({scoreboard}: {scoreboard: number}) {
    const queue = useHd((s) => s.stream_queue);
    const stream = queue?.streams?.find((s) => Number(s.scoreboard) === scoreboard) ?? queue?.streams?.[0];

    if (!stream) {
        return <EmptyState>No streams yet. They show up when start.gg has a stream queue, or add one in Stream Queue.</EmptyState>;
    }
    const sets = stream.sets.filter((s) => !s.onStream).slice(0, 3);
    return (
        <div className="flex flex-1 flex-col gap-2">
            {sets.length === 0 && <p className="text-sm text-muted-foreground">Nothing queued on {stream.name}.</p>}
            {sets.map((set) => (
                <div key={set.queueKey} className="flex items-center gap-3 rounded-lg border bg-background px-3 py-2.5">
                    <span className="w-14 text-xs text-muted-foreground tabular-nums">{etaText(set)}</span>
                    <span className="flex min-w-0 flex-1 flex-col leading-snug">
                        <span className="truncate font-semibold">{queueSetName(set)}</span>
                        <span className="truncate text-xs text-muted-foreground">{[set.match, set.phase].filter(Boolean).join(" · ")}</span>
                    </span>
                </div>
            ))}
            <div className="flex-1"/>
            <div className="flex items-center gap-2 pt-2">
                <span className="flex-1 text-xs text-muted-foreground">
                    {stream.scoreboard ? `Loads into scoreboard ${stream.scoreboard}` : "Pick its scoreboard in Stream Queue to load sets"}
                </span>
                <Button
                    disabled={!stream.scoreboard || sets.length === 0}
                    onClick={() => dashboard.streamQueue.edit(stream.name, "load-next")
                        .then(() => toast.success("Loading the next set"))
                        .catch(() => toast.error("Couldn't load the next set."))}
                >
                    Load next set
                </Button>
            </div>
        </div>
    );
}

function LayoutSwitch({name, shown: serverShown}: {name: string; shown: boolean}) {
    const [shown, setShown] = useOptimistic(serverShown);
    return (
        <label className="flex min-h-10 cursor-pointer items-center gap-2.5">
            <span className="flex-1 truncate font-mono text-[13px]">{name}</span>
            <span className="text-xs text-muted-foreground">{shown ? "Shown" : "Hidden"}</span>
            <Switch checked={shown} onCheckedChange={(next) => {
                setShown(next);
                dashboard.display.set("folder", name, next ? "show" : "hide").catch(() => {});
            }}/>
        </label>
    );
}

function OnStream() {
    const display = useHd((s) => s.display);
    const folders = Object.entries(display?.folders ?? {});
    const shown = folders
        .filter(([name, on]) => MAIN_LAYOUTS.includes(name) || !on)
        .sort(([a], [b]) => (MAIN_LAYOUTS.indexOf(a) + 1 || 99) - (MAIN_LAYOUTS.indexOf(b) + 1 || 99))
        .slice(0, 8);

    return (
        <div className="flex flex-col">
            {shown.map(([name, on]) => <LayoutSwitch key={name} name={name} shown={on}/>)}
            <div className="flex gap-2 pt-3">
                <Button variant="secondary" className="flex-1" onClick={() => dashboard.display.all("show").catch(() => {})}>Show all</Button>
                <Button variant="secondary" className="flex-1" onClick={() => dashboard.display.all("hide").catch(() => {})}>Hide all</Button>
            </div>
        </div>
    );
}

function RecentResults() {
    const sets = useHd((s) => s.completed_sets);
    const list = Object.values(sets ?? {}).slice(0, 5);
    if (list.length === 0) {
        return <p className="text-sm text-muted-foreground">No completed sets pulled yet.</p>;
    }
    const name = (team: Record<string, {gamertag?: string}>, teamName?: string) =>
        teamName || Object.values(team ?? {}).map((p) => p?.gamertag).filter(Boolean).join(" / ");
    return (
        <div className="flex flex-col">
            {list.map((set, i) => (
                <div key={i} className="flex items-center gap-2.5 border-b py-2 text-[13px] last:border-0">
                    <span className="min-w-0 flex-1 truncate">
                        <b>{name(set.winner_team, set.winner_team_name)}</b>
                        <span className="text-muted-foreground"> def. </span>
                        {name(set.loser_team, set.loser_team_name)}
                    </span>
                    <span className="font-semibold tabular-nums">{set.winner_score}–{set.loser_score}</span>
                    {(set.upset_factor ?? 0) > 0 && <span className="text-[11px] font-bold text-brand-text">UPSET</span>}
                </div>
            ))}
        </div>
    );
}

function Commentators() {
    const commentary = useHd((s) => s.commentary);
    const list = Object.entries(commentary ?? {}).filter(([k]) => /^\d+$/.test(k)).map(([, c]) => c).filter((c) => c?.name);
    if (list.length === 0) {
        return <p className="text-sm text-muted-foreground">No commentators yet.</p>;
    }
    return (
        <div className="flex flex-col gap-2">
            {list.map((c, i) => (
                <div key={i} className="flex items-center gap-3 rounded-lg border bg-background px-3 py-2.5">
                    <span className="grid size-8 place-items-center rounded-full bg-secondary text-xs font-bold">{c.name.slice(0, 2).toUpperCase()}</span>
                    <span className="flex min-w-0 flex-col leading-snug">
                        <b className="truncate">{c.team ? `${c.team} | ${c.name}` : c.name}</b>
                        <span className="truncate text-xs text-muted-foreground">
                            {[c.twitter ? `@${c.twitter}` : null, c.pronoun].filter(Boolean).join(" · ")}
                        </span>
                    </span>
                </div>
            ))}
        </div>
    );
}

function TournamentFacts() {
    const info = useHd((s) => s.tournamentInfo as Record<string, unknown> | undefined);
    const rows: [string, unknown][] = [
        ["Event", [info?.tournamentName, info?.eventName].filter(Boolean).join(" · ")],
        ["Entrants", info?.numEntrants],
        ["Date", info?.startAt ?? info?.date],
        ["Short link", info?.shortLink],
    ];
    return (
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 text-[13px]">
            {rows.filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => (
                <React.Fragment key={k}>
                    <dt className="text-muted-foreground">{k}</dt>
                    <dd className="truncate font-medium">{String(v)}</dd>
                </React.Fragment>
            ))}
        </dl>
    );
}

/** The dashboard's home: what's happening, with the most used controls */
export default function Overview() {
    const status = useStatus();
    const {selected, scores} = useSelector((s: ReduxState) => ({
        selected: s.selectedScoreboard.value,
        scores: s.hdState.hdState?.score,
    }), shallowEqual);
    const [loadOpen, setLoadOpen] = React.useState(false);
    const name = status?.scoreboards.find((s) => s.number === selected)?.name ?? `Scoreboard ${selected}`;
    const info = useHd((s) => s.tournamentInfo);

    return (
        <PageBody>
            <PageHeader title="Overview" description={[name, info?.tournamentName].filter(Boolean).join(" · ")}/>
            {status && !status.tournament.loaded && (
                <EmptyState action={<Button onClick={() => setLoadOpen(true)}>Load tournament</Button>}>
                    No tournament is loaded. Load one to get its players, bracket and stream queue.
                </EmptyState>
            )}
            <LoadTournamentDialog open={loadOpen} onOpenChange={setLoadOpen}/>
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
                <Panel title="Live set" action={<PanelLink to="/dashboard/scoreboard">Open scoreboard</PanelLink>} className="xl:col-span-2">
                    <LiveSet number={selected} score={scores?.[selected]}/>
                </Panel>
                <Panel title="Up next" action={<PanelLink to="/dashboard/stream-queue">Stream Queue</PanelLink>} bodyClassName="flex-1">
                    <UpNext scoreboard={selected}/>
                </Panel>
                <Panel title="On stream" action={<PanelLink to="/dashboard/display-controls">Display Controls</PanelLink>}>
                    <OnStream/>
                </Panel>
                <Panel title="Recent results"><RecentResults/></Panel>
                <Panel title="On commentary" action={<PanelLink to="/dashboard/commentary">Commentary</PanelLink>}>
                    <Commentators/>
                </Panel>
                <Panel title="Tournament" action={<PanelLink to="/dashboard/tournament-info">Tournament Info</PanelLink>}>
                    <TournamentFacts/>
                </Panel>
            </div>
        </PageBody>
    );
}
