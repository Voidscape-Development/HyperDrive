import React from "react";
import {Link} from "react-router-dom";
import {LayoutGrid, List, MapPin, MoreHorizontal, Play, RefreshCw, RotateCcw, Search, Send, Tv, UserX} from "lucide-react";
import {toast} from "sonner";
import {
    CALLED,
    COMPLETED,
    errorMessage,
    IN_PROGRESS,
    NOT_STARTED,
    reportingAdmin,
    type ReportingSet,
    type SetAction,
    type SetsData,
} from "./api";
import {ReportDialog} from "./ReportDialog";
import {isReady, matchesSearch, setPlace, setTitle, startggScore, stateInfo, timeAgo, winnerTeam} from "./sets";
import {usePolledSets} from "./useSets";
import {ReportingNotice} from "./ReportingNotice";
import {EmptyState, OptionsBar, PageBody, PageHeader} from "../Dashboard/ui";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {Spinner} from "@/components/ui/spinner";
import {cn} from "@/lib/utils";

/*
 * The Admin page: the loaded event's sets, as a list or by station, and
 * everything that can be done to them on start.gg. Changes are sent right
 * away; only resetting a set asks first.
 */

type StateFilter = "open" | "all" | "ready" | typeof NOT_STARTED | typeof CALLED | typeof IN_PROGRESS | typeof COMPLETED;
type View = "list" | "stations";

const VIEW_KEY = "hyperdrive-reporting-view";
const PAGE_SIZE = 150;

const STATE_FILTERS: [StateFilter, string][] = [
    ["open", "Not completed"],
    ["ready", "Ready to play"],
    [CALLED, "Called"],
    [IN_PROGRESS, "In progress"],
    [COMPLETED, "Completed"],
    ["all", "All"],
];

// In progress first, then called, ready, waiting for players, completed
function priority(set: ReportingSet) {
    if (set.state === IN_PROGRESS) return 0;
    if (set.state === CALLED) return 1;
    if (set.state === COMPLETED) return 4;
    return isReady(set) ? 2 : 3;
}

function compareSets(a: ReportingSet, b: ReportingSet) {
    return priority(a) - priority(b)
        || (a.state === COMPLETED ? (b.completedAt ?? 0) - (a.completedAt ?? 0) : 0)
        || a.phase.localeCompare(b.phase)
        || a.phaseGroup.localeCompare(b.phaseGroup, undefined, {numeric: true})
        || Math.abs(a.round ?? 0) - Math.abs(b.round ?? 0)
        || a.identifier.length - b.identifier.length
        || a.identifier.localeCompare(b.identifier);
}

function matchesState(set: ReportingSet, filter: StateFilter) {
    if (filter === "all") return true;
    if (filter === "open") return set.state !== COMPLETED;
    if (filter === "ready") return set.state === NOT_STARTED && isReady(set);
    return set.state === filter;
}

function readView(): View {
    try {
        return window.localStorage.getItem(VIEW_KEY) === "stations" ? "stations" : "list";
    } catch {
        return "list";
    }
}

/** What's done to a set, from its row or card */
function useSetActions(data: SetsData | null, onChanged: (set: ReportingSet) => void) {
    const [busy, setBusy] = React.useState<string | null>(null);
    const run = (set: ReportingSet, action: SetAction, body: object, done: string) => {
        setBusy(set.id);
        return reportingAdmin.action(set.id, action, body)
            .then(({set: changed}) => {
                onChanged(changed);
                toast.success(done);
            })
            .catch((e) => toast.error(`${setTitle(set)}: ${errorMessage(e)}`))
            .finally(() => setBusy(null));
    };
    return {
        busy,
        call: (set: ReportingSet) => run(set, "call", {}, `Called: ${setTitle(set)}`),
        start: (set: ReportingSet) => run(set, "start", {}, `In progress: ${setTitle(set)}`),
        reset: (set: ReportingSet) => window.confirm(
            `Reset ${setTitle(set)} on start.gg? Its result and games are cleared, and sets that depend on it are reset too.`,
        ) && run(set, "reset", {}, `Reset: ${setTitle(set)}`),
        assignStation: (set: ReportingSet, stationId: string) => {
            const station = data?.stations.find((s) => s.id === stationId);
            return run(set, "assign-station", {stationId}, `${setTitle(set)} → station ${station?.number ?? ""}`);
        },
        assignStream: (set: ReportingSet, streamId: string) => {
            const stream = data?.streams.find((s) => s.id === streamId);
            return run(set, "assign-stream", {streamId}, `${setTitle(set)} → ${stream?.name ?? "stream"}`);
        },
    };
}

type Actions = ReturnType<typeof useSetActions>;

const MENU_ITEM = "flex min-h-9 w-full cursor-pointer items-center gap-2 rounded-md px-2.5 text-left text-sm hover:bg-accent disabled:cursor-default disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0";

function SetMenu({set, data, actions, onReport}: {
    set: ReportingSet;
    data: SetsData;
    actions: Actions;
    onReport: (set: ReportingSet, tab: "games" | "dq") => void;
}) {
    const [open, setOpen] = React.useState(false);
    const [picking, setPicking] = React.useState<"station" | "stream" | null>(null);
    const ready = isReady(set);
    const item = (label: string, Icon: typeof Play, onClick: () => void, disabled = false, className = "") => (
        <button type="button" className={cn(MENU_ITEM, className)} disabled={disabled} onClick={() => {
            setOpen(false);
            onClick();
        }}>
            <Icon/>{label}
        </button>
    );

    return (
        <Popover open={open} onOpenChange={(o) => {
            setOpen(o);
            setPicking(null);
        }}>
            <PopoverTrigger asChild>
                <Button variant="ghost" size="icon-sm" aria-label={`More for ${setTitle(set)}`}><MoreHorizontal/></Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-64 p-1">
                {picking === null ? (
                    <>
                        {item("Mark as called", MapPin, () => actions.call(set), !ready || set.state === COMPLETED || set.state === CALLED)}
                        {item("Mark as in progress", Play, () => actions.start(set), !ready || set.state === COMPLETED || set.state === IN_PROGRESS)}
                        {item(set.state === COMPLETED ? "Change the result…" : "Report or update score…", Send, () => onReport(set, "games"), !ready)}
                        {item("Report a DQ…", UserX, () => onReport(set, "dq"), !ready)}
                        <button type="button" className={MENU_ITEM} disabled={!data.stations.length} onClick={() => setPicking("station")}>
                            <LayoutGrid/>Assign to a station…
                        </button>
                        <button type="button" className={MENU_ITEM} disabled={!data.streams.length} onClick={() => setPicking("stream")}>
                            <Tv/>Assign to a stream…
                        </button>
                        {item("Reset on start.gg…", RotateCcw, () => actions.reset(set), set.state === NOT_STARTED && !set.scores?.some((s) => s != null), "text-destructive")}
                    </>
                ) : (
                    <div className="flex max-h-72 flex-col overflow-y-auto">
                        <span className="px-2.5 py-1.5 text-xs font-semibold text-muted-foreground">{picking === "station" ? "Station" : "Stream"}</span>
                        {picking === "station" && data.stations.map((s) => (
                            <button key={s.id} type="button" className={cn(MENU_ITEM, set.station?.id === s.id && "bg-accent")} onClick={() => {
                                setOpen(false);
                                actions.assignStation(set, s.id);
                            }}>
                                Station {s.number}{s.stream && <span className="text-xs text-muted-foreground">{s.stream}</span>}
                            </button>
                        ))}
                        {picking === "stream" && data.streams.map((s) => (
                            <button key={s.id} type="button" className={cn(MENU_ITEM, set.stream?.id === s.id && "bg-accent")} onClick={() => {
                                setOpen(false);
                                actions.assignStream(set, s.id);
                            }}>
                                {s.name}
                            </button>
                        ))}
                    </div>
                )}
            </PopoverContent>
        </Popover>
    );
}

/** The players, the winner in bold, and the score */
function Players({set}: {set: ReportingSet}) {
    const winner = winnerTeam(set);
    const score = startggScore(set);
    return (
        <span className="flex min-w-0 items-center gap-1.5">
            <span className={cn("truncate", winner === 1 ? "font-bold" : winner ? "text-muted-foreground" : "font-semibold")}>{set.entrants[0]?.name || "TBD"}</span>
            <span className="shrink-0 text-xs text-muted-foreground tabular-nums">{score || "vs"}</span>
            <span className={cn("truncate", winner === 2 ? "font-bold" : winner ? "text-muted-foreground" : "font-semibold")}>{set.entrants[1]?.name || "TBD"}</span>
        </span>
    );
}

/** The quickest next step for a set */
function NextAction({set, actions, onReport}: {set: ReportingSet; actions: Actions; onReport: (set: ReportingSet, tab: "games" | "dq") => void}) {
    if (!isReady(set)) {
        return null;
    }
    if (set.state === NOT_STARTED) {
        return <Button variant="outline" size="sm" onClick={() => actions.call(set)}>Call</Button>;
    }
    if (set.state === CALLED) {
        return <Button variant="outline" size="sm" onClick={() => actions.start(set)}>Start</Button>;
    }
    if (set.state === IN_PROGRESS) {
        return <Button size="sm" onClick={() => onReport(set, "games")}>Report</Button>;
    }
    return <Button variant="ghost" size="sm" onClick={() => onReport(set, "games")}>Edit</Button>;
}

function PendingBadge({set, approvalPath}: {set: ReportingSet; approvalPath: string}) {
    if (!set.pending) {
        return null;
    }
    return (
        <Badge asChild variant="secondary" className="bg-warning/20 text-foreground">
            <Link to={approvalPath} title="Results sent from a reporting station, waiting for approval">
                {set.pending} to approve
            </Link>
        </Badge>
    );
}

function SetRow({set, data, actions, onReport, approvalPath}: {
    set: ReportingSet;
    data: SetsData;
    actions: Actions;
    onReport: (set: ReportingSet, tab: "games" | "dq") => void;
    approvalPath: string;
}) {
    const state = stateInfo(set.state);
    return (
        <div className={cn(
            "grid min-h-13 grid-cols-[6.5rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 border-b px-4 py-2 text-[13px] last:border-0 md:grid-cols-[6.5rem_minmax(0,1.6fr)_minmax(0,1.2fr)_7rem_auto]",
            set.state === IN_PROGRESS && "shadow-[inset_3px_0_0_var(--live)]",
        )}>
            <span className={cn("text-xs font-semibold", state.className)}>
                {state.label}
                {!isReady(set) && set.state !== COMPLETED && <span className="block font-normal text-muted-foreground">Waiting for players</span>}
            </span>
            <span className="flex min-w-0 flex-col gap-0.5">
                <Players set={set}/>
                <span className="truncate text-xs text-muted-foreground md:hidden">{setPlace(set)}</span>
            </span>
            <span className="hidden truncate text-muted-foreground md:block">{setPlace(set)}</span>
            <span className="hidden flex-col text-xs text-muted-foreground md:flex">
                {set.station && <span>Station {set.station.number}</span>}
                {set.stream && <span className="truncate">{set.stream.name}</span>}
                {set.state === COMPLETED && <span>{timeAgo(set.completedAt)}</span>}
            </span>
            <span className="flex items-center justify-end gap-1.5">
                <PendingBadge set={set} approvalPath={approvalPath}/>
                {actions.busy === set.id ? <Spinner/> : <NextAction set={set} actions={actions} onReport={onReport}/>}
                <SetMenu set={set} data={data} actions={actions} onReport={onReport}/>
            </span>
        </div>
    );
}

function StationCard({title, subtitle, sets, data, actions, onReport, approvalPath}: {
    title: string;
    subtitle?: string;
    sets: ReportingSet[];
    data: SetsData;
    actions: Actions;
    onReport: (set: ReportingSet, tab: "games" | "dq") => void;
    approvalPath: string;
}) {
    const [current, ...queued] = sets;
    return (
        <section className={cn("flex min-w-0 flex-col rounded-xl border bg-card", current?.state === IN_PROGRESS && "border-live/60")}>
            <header className="flex items-center gap-2 border-b px-3.5 py-2.5">
                <h3 className="flex-1 font-semibold">{title}</h3>
                {subtitle && <span className="truncate text-xs text-muted-foreground">{subtitle}</span>}
            </header>
            {!current ? (
                <p className="px-3.5 py-4 text-sm text-muted-foreground">Free</p>
            ) : (
                <div className="flex flex-col gap-2 p-3.5">
                    <div className="flex items-center gap-2">
                        <span className={cn("text-xs font-semibold", stateInfo(current.state).className)}>{stateInfo(current.state).label}</span>
                        <span className="flex-1"/>
                        <PendingBadge set={current} approvalPath={approvalPath}/>
                    </div>
                    <Players set={current}/>
                    <span className="truncate text-xs text-muted-foreground">{setPlace(current)}</span>
                    <div className="flex items-center justify-end gap-1.5">
                        {actions.busy === current.id ? <Spinner/> : <NextAction set={current} actions={actions} onReport={onReport}/>}
                        <SetMenu set={current} data={data} actions={actions} onReport={onReport}/>
                    </div>
                </div>
            )}
            {queued.length > 0 && (
                <ol className="border-t px-3.5 py-2 text-xs text-muted-foreground">
                    {queued.slice(0, 3).map((s) => (
                        <li key={s.id} className="flex items-center gap-2 py-0.5">
                            <span className="min-w-0 flex-1 truncate">Then: {setTitle(s)}</span>
                            <SetMenu set={s} data={data} actions={actions} onReport={onReport}/>
                        </li>
                    ))}
                    {queued.length > 3 && <li>+{queued.length - 3} more</li>}
                </ol>
            )}
        </section>
    );
}

export default function AdminPage({approvalPath = "/dashboard/reporting-approval"}: {approvalPath?: string}) {
    const {data, error, loading, reload, applySet} = usePolledSets(reportingAdmin.sets);
    const actions = useSetActions(data, applySet);
    const [view, setView] = React.useState<View>(readView);
    const [stateFilter, setStateFilter] = React.useState<StateFilter>("open");
    const [phase, setPhase] = React.useState("all");
    const [station, setStation] = React.useState("all");
    const [search, setSearch] = React.useState("");
    const [limit, setLimit] = React.useState(PAGE_SIZE);
    const [reporting, setReporting] = React.useState<{set: ReportingSet; tab: "games" | "dq"} | null>(null);

    const changeView = (next: View) => {
        setView(next);
        try {
            window.localStorage.setItem(VIEW_KEY, next);
        } catch {
            // Kept for this page only
        }
    };
    const onReport = (set: ReportingSet, tab: "games" | "dq") => setReporting({set, tab});

    const sets = data?.sets ?? [];
    const phases = [...new Set(sets.map((s) => s.phase).filter(Boolean))];
    const filtered = sets
        .filter((s) => matchesState(s, stateFilter))
        .filter((s) => phase === "all" || s.phase === phase)
        .filter((s) => station === "all" || (station === "none" ? !s.station : s.station?.id === station))
        .filter((s) => matchesSearch(s, search))
        .sort(compareSets);
    const counts = {
        inProgress: sets.filter((s) => s.state === IN_PROGRESS).length,
        called: sets.filter((s) => s.state === CALLED).length,
        ready: sets.filter((s) => s.state === NOT_STARTED && isReady(s)).length,
        completed: sets.filter((s) => s.state === COMPLETED).length,
    };

    const byStation = (data?.stations ?? []).map((st) => ({
        station: st,
        sets: sets.filter((s) => s.station?.id === st.id && s.state !== COMPLETED && matchesSearch(s, search)).sort(compareSets),
    }));
    const unassigned = sets
        .filter((s) => !s.station && s.state !== COMPLETED && isReady(s) && matchesSearch(s, search))
        .filter((s) => phase === "all" || s.phase === phase)
        .sort(compareSets);

    return (
        <PageBody>
            <PageHeader
                title="Reporting"
                description={data ? [
                    `${counts.inProgress} in progress · ${counts.called} called · ${counts.ready} ready · ${counts.completed} completed`,
                    data.updatedAt ? `updated ${timeAgo(data.updatedAt)}` : null,
                ].filter(Boolean).join(" · ") : "The event's sets on start.gg"}
            >
                <div role="radiogroup" aria-label="View" className="flex rounded-lg border p-0.5">
                    {([["list", "List", List], ["stations", "Stations", LayoutGrid]] as const).map(([value, label, Icon]) => (
                        <Button key={value} role="radio" aria-checked={view === value} variant={view === value ? "secondary" : "ghost"} size="sm" onClick={() => changeView(value)}>
                            <Icon/>{label}
                        </Button>
                    ))}
                </div>
                <Button variant="secondary" disabled={loading} onClick={() => reload(true).then(() => toast.success("Sets updated from start.gg"))}>
                    {loading ? <Spinner/> : <RefreshCw/>}Update from start.gg
                </Button>
            </PageHeader>

            <ReportingNotice error={error} data={data}/>

            {data && (
                <>
                    <OptionsBar>
                        <label className="relative flex min-w-56 flex-1 items-center">
                            <Search className="pointer-events-none absolute left-2.5 size-4 text-muted-foreground"/>
                            <Input value={search} onChange={(e) => {
                                setSearch(e.target.value);
                                setLimit(PAGE_SIZE);
                            }} placeholder="Player or set (e.g. A1 C)" aria-label="Search sets" className="pl-8 text-foreground"/>
                        </label>
                        {view === "list" && (
                            <Select value={String(stateFilter)} onValueChange={(v) => setStateFilter((/^\d+$/.test(v) ? Number(v) : v) as StateFilter)}>
                                <SelectTrigger aria-label="State" className="w-44 text-foreground"><SelectValue/></SelectTrigger>
                                <SelectContent>
                                    {STATE_FILTERS.map(([value, label]) => <SelectItem key={value} value={String(value)}>{label}</SelectItem>)}
                                </SelectContent>
                            </Select>
                        )}
                        {phases.length > 1 && (
                            <Select value={phase} onValueChange={setPhase}>
                                <SelectTrigger aria-label="Phase" className="w-44 text-foreground"><SelectValue/></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">Every phase</SelectItem>
                                    {phases.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                                </SelectContent>
                            </Select>
                        )}
                        {view === "list" && data.stations.length > 0 && (
                            <Select value={station} onValueChange={setStation}>
                                <SelectTrigger aria-label="Station" className="w-40 text-foreground"><SelectValue/></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">Every station</SelectItem>
                                    <SelectItem value="none">No station</SelectItem>
                                    {data.stations.map((s) => <SelectItem key={s.id} value={s.id}>Station {s.number}</SelectItem>)}
                                </SelectContent>
                            </Select>
                        )}
                    </OptionsBar>

                    {view === "list" ? (
                        filtered.length === 0 ? (
                            <EmptyState>No sets match. {sets.length === 0 ? "start.gg has no sets for this event yet." : "Try another filter."}</EmptyState>
                        ) : (
                            <div className="rounded-xl border bg-card">
                                {filtered.slice(0, limit).map((s) => (
                                    <SetRow key={s.id} set={s} data={data} actions={actions} onReport={onReport} approvalPath={approvalPath}/>
                                ))}
                                {filtered.length > limit && (
                                    <div className="flex justify-center border-t p-3">
                                        <Button variant="ghost" onClick={() => setLimit(limit + PAGE_SIZE)}>
                                            Show more ({filtered.length - limit} left)
                                        </Button>
                                    </div>
                                )}
                            </div>
                        )
                    ) : data.stations.length === 0 ? (
                        <EmptyState>This event has no stations on start.gg. Add them in the event's Stations settings on start.gg to see them here.</EmptyState>
                    ) : (
                        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
                            <div className="grid content-start gap-3 sm:grid-cols-2 2xl:grid-cols-3">
                                {byStation.map(({station: st, sets: stationSets}) => (
                                    <StationCard key={st.id} title={`Station ${st.number}`} subtitle={st.stream} sets={stationSets}
                                        data={data} actions={actions} onReport={onReport} approvalPath={approvalPath}/>
                                ))}
                            </div>
                            <section className="flex min-w-0 flex-col self-start rounded-xl border bg-card">
                                <header className="border-b px-3.5 py-2.5 font-semibold">Ready, without a station <span className="text-muted-foreground">{unassigned.length}</span></header>
                                {unassigned.length === 0 && <p className="px-3.5 py-4 text-sm text-muted-foreground">None</p>}
                                {unassigned.slice(0, limit).map((s) => (
                                    <div key={s.id} className="flex items-center gap-2 border-b px-3.5 py-2 text-[13px] last:border-0">
                                        <span className="flex min-w-0 flex-1 flex-col">
                                            <Players set={s}/>
                                            <span className="truncate text-xs text-muted-foreground">
                                                <span className={stateInfo(s.state).className}>{stateInfo(s.state).label}</span> · {setPlace(s)}
                                            </span>
                                        </span>
                                        <PendingBadge set={s} approvalPath={approvalPath}/>
                                        {actions.busy === s.id && <Spinner/>}
                                        <SetMenu set={s} data={data} actions={actions} onReport={onReport}/>
                                    </div>
                                ))}
                            </section>
                        </div>
                    )}
                </>
            )}

            <ReportDialog
                set={reporting?.set ?? null}
                initialTab={reporting?.tab}
                open={reporting !== null}
                onOpenChange={(open) => !open && setReporting(null)}
                onDone={applySet}
            />
        </PageBody>
    );
}
