import {useEffect, useMemo, useState} from "react";
import {ChevronRight, Clock} from "lucide-react";
import i18n from "../i18n/config";
import type {DashboardState, QueueSet, QueueStream, Team} from "./types";
import {clockTime, Empty, etaText, numbered, teamName, scoreText, toNumber} from "./util";
import {PreviewDialog} from "./Preview";
import {Badge} from "@/components/ui/badge";
import {Card, CardAction, CardContent, CardHeader, CardTitle} from "@/components/ui/card";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {cn} from "@/lib/utils";

/** The stream showing this scoreboard, else the channel set in HyperDrive, else the first one */
function defaultStream(streams: QueueStream[], scoreboardNumber: number, currentStream?: string) {
    return streams.find((s) => s.scoreboard === scoreboardNumber)
        ?? streams.find((s) => currentStream && s.name.toLowerCase() === currentStream.toLowerCase())
        ?? streams[0];
}

/** The next sets of the stream queue, with when they should start. Click one for its players. */
export function UpNext({state, scoreboardNumber}: {state: DashboardState; scoreboardNumber: number}) {
    const streams = state.stream_queue?.streams ?? [];
    const fallback = defaultStream(streams, scoreboardNumber, state.stream_queue?.currentStream);
    const [picked, setPicked] = useState<string | null>(null);
    const [previewKey, setPreviewKey] = useState<string | null>(null);

    // Back to the scoreboard's stream when the scoreboard changes
    useEffect(() => setPicked(null), [scoreboardNumber]);

    const stream = streams.find((s) => s.name === picked) ?? fallback;
    const sets = stream?.sets ?? [];
    const preview = useMemo(() => sets.find((s) => s.queueKey === previewKey) ?? null, [sets, previewKey]);

    return <Card className="gap-3 py-4 fit:min-h-0">
        <CardHeader className="shrink-0 px-4">
            <CardTitle>{i18n.t("up_next")}</CardTitle>
            {streams.length > 1 ? <CardAction>
                <Select value={stream?.name} onValueChange={setPicked}>
                    <SelectTrigger size="sm" className="max-w-48"><SelectValue/></SelectTrigger>
                    <SelectContent>
                        {streams.map((s) => <SelectItem key={s.name} value={s.name}>{s.name}</SelectItem>)}
                    </SelectContent>
                </Select>
            </CardAction> : null}
        </CardHeader>
        <CardContent className="px-4 fit:min-h-0 fit:flex-1 fit:scroll-panel">
            {sets.length === 0
                ? <Empty>{streams.length === 0 ? i18n.t("no_stream_queue") : i18n.t("queue_empty")}</Empty>
                : <ul className="flex flex-col divide-y rounded-md border">
                    {sets.map((s) => <QueueRow key={s.queueKey} set={s} onClick={() => setPreviewKey(s.queueKey)}/>)}
                </ul>}
            {state.stream_queue?.average_set_minutes
                ? <p className="mt-2 text-xs text-muted-foreground">{i18n.t("average_set", {value: state.stream_queue.average_set_minutes})}</p>
                : null}
        </CardContent>
        <PreviewDialog set={preview} onClose={() => setPreviewKey(null)}/>
    </Card>;
}

function QueueRow({set, onClick}: {set: QueueSet; onClick: () => void}) {
    const eta = etaText(set.eta_minutes);
    const teams = [set.team?.["1"], set.team?.["2"]];
    return <li>
        <button
            type="button"
            onClick={onClick}
            className={cn("flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-muted/50 focus-visible:bg-muted/50 focus-visible:outline-none", set.onStream && "bg-muted/30")}
        >
            <span className="w-5 shrink-0 text-center text-sm text-muted-foreground tabular-nums">{set.position}</span>
            <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-baseline gap-x-2">
                    <QueueTeam team={teams[0]}/>
                    <span className="text-xs text-muted-foreground">{i18n.t("vs")}</span>
                    <QueueTeam team={teams[1]}/>
                </span>
                <span className="block truncate text-xs text-muted-foreground">
                    {[set.phase, set.match, set.best_of_text].filter(Boolean).join(" · ")}
                </span>
            </span>
            {set.onStream
                ? <Badge>{i18n.t("on_stream")}</Badge>
                : eta ? <span className="flex shrink-0 flex-col items-end text-xs">
                    <span className="inline-flex items-center gap-1 font-medium"><Clock className="size-3"/>{eta}</span>
                    {set.eta_minutes && set.eta_minutes > 0 ? <span className="text-muted-foreground">{clockTime(set.eta)}</span> : null}
                </span> : null}
            <ChevronRight className="size-4 shrink-0 text-muted-foreground"/>
        </button>
    </li>;
}

/** A team's name and seed, kept on one line */
function QueueTeam({team}: {team?: Team}) {
    return <span className="whitespace-nowrap">
        <span className="font-semibold">{teamName(team) || i18n.t("tbd")}</span>
        {team?.seed && team.seed < 100000 ? <span className="ml-1 text-xs text-muted-foreground">({team.seed})</span> : null}
    </span>;
}

/** The event's last completed sets, upsets marked */
export function RecentResults({state}: {state: DashboardState}) {
    const sets = numbered(state.completed_sets);
    const names = (team: Record<string, {sponsor?: string; gamertag?: string}> | undefined, teamName?: string) => {
        const players = numbered(team).filter((p) => p?.gamertag);
        if (players.length === 1) return players[0].sponsor ? `${players[0].sponsor} | ${players[0].gamertag}` : players[0].gamertag;
        return teamName || players.map((p) => p.gamertag).join(" / ");
    };

    return <Card className="gap-3 py-4 fit:min-h-0">
        <CardHeader className="shrink-0 px-4"><CardTitle>{i18n.t("recent_results")}</CardTitle></CardHeader>
        <CardContent className="px-4 fit:min-h-0 fit:flex-1 fit:scroll-panel">
            {sets.length === 0 ? <Empty>{i18n.t("no_recent_results")}</Empty> :
                <ul className="flex flex-col divide-y rounded-md border text-sm">
                    {sets.map((s, i) => <li key={i} className="flex items-center gap-2 px-3 py-2">
                        <span className="min-w-0 flex-1">
                            <span className="flex flex-wrap items-baseline gap-x-1.5">
                                <span className="font-semibold">{names(s.winner_team, s.winner_team_name)}</span>
                                {s.winner_seed ? <span className="text-xs text-muted-foreground">({s.winner_seed})</span> : null}
                                <span className="font-semibold tabular-nums">{scoreText(s.winner_score)}–{scoreText(s.loser_score)}</span>
                                <span>{names(s.loser_team, s.loser_team_name)}</span>
                                {s.loser_seed ? <span className="text-xs text-muted-foreground">({s.loser_seed})</span> : null}
                            </span>
                            <span className="block truncate text-xs text-muted-foreground">
                                {[[s.phase_name, s.phase_id].filter(Boolean).join(" "), s.round_name].filter(Boolean).join(" · ")}
                            </span>
                        </span>
                        {(toNumber(s.upset_factor) ?? 0) > 0
                            ? <Badge variant="outline" className="shrink-0 border-ban/60 text-ban">{i18n.t("upset_n", {value: s.upset_factor})}</Badge>
                            : null}
                    </li>)}
                </ul>}
        </CardContent>
    </Card>;
}
