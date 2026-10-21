import React from "react";
import {ArrowDown, ArrowUp, ChevronsUp, Download, MoreHorizontal, Plus, RefreshCw, X} from "lucide-react";
import {toast} from "sonner";
import {dashboard, type StreamQueueOptions} from "./api";
import {etaText, queueSetName} from "./Overview";
import {useStatus} from "./status";
import {useHd, type QueueSet} from "./stateTypes";
import {EmptyState, PageBody, PageHeader, Panel, useRemoteOptions} from "./ui";
import {Button} from "@/components/ui/button";
import {Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle} from "@/components/ui/dialog";
import {Input} from "@/components/ui/input";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {Switch} from "@/components/ui/switch";
import {cn} from "@/lib/utils";

// start.gg's set states
const STATUS: Record<number, [string, string]> = {
    2: ["In progress", "text-live"],
    3: ["Finished", "text-muted-foreground"],
    6: ["Called", "text-sky-400"],
};

const AFTER_SET = [
    ["nothing", "Do nothing"],
    ["ask", "Ask to load the next set"],
    ["load_next", "Load the next set"],
] as const;

const failed = (what: string) => () => toast.error(`Couldn't ${what}.`);

function statusOf(set: QueueSet): [string, string] {
    if (set.onStream) {
        return ["On stream", "text-brand-text"];
    }
    if (set.source === "custom") {
        return ["Added here", "text-violet-300"];
    }
    return STATUS[Number(set.state)] ?? ["Waiting", "text-muted-foreground"];
}

function AddStreamDialog({open, onOpenChange}: {open: boolean; onOpenChange: (open: boolean) => void}) {
    const [name, setName] = React.useState("");
    const submit = (e: React.FormEvent) => {
        e.preventDefault();
        dashboard.streamQueue.addStream(name.trim()).then(() => {
            setName("");
            onOpenChange(false);
        }).catch(failed("add the stream"));
    };
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <form onSubmit={submit} className="flex flex-col gap-4">
                    <DialogHeader>
                        <DialogTitle>Add stream</DialogTitle>
                        <DialogDescription>Its name, e.g. the Twitch channel. A stream in start.gg's stream queue gets its queue.</DialogDescription>
                    </DialogHeader>
                    <Input autoFocus aria-label="Stream name" value={name} onChange={(e) => setName(e.target.value)}/>
                    <DialogFooter><Button type="submit" disabled={!name.trim()}>Add stream</Button></DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

function AddCustomDialog({stream, open, onOpenChange}: {stream: string; open: boolean; onOpenChange: (open: boolean) => void}) {
    const [values, setValues] = React.useState({team1: "", team2: "", match: ""});
    const submit = (e: React.FormEvent) => {
        e.preventDefault();
        dashboard.streamQueue.edit(stream, "add-custom", values).then(() => {
            setValues({team1: "", team2: "", match: ""});
            onOpenChange(false);
        }).catch(failed("add the set"));
    };
    const field = (key: keyof typeof values, label: string) => (
        <label className="flex flex-col gap-1.5 text-xs text-muted-foreground">
            {label}
            <Input value={values[key]} onChange={(e) => setValues({...values, [key]: e.target.value})}/>
        </label>
    );
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <form onSubmit={submit} className="flex flex-col gap-4">
                    <DialogHeader>
                        <DialogTitle>Add custom set</DialogTitle>
                        <DialogDescription>A set that isn't on start.gg, e.g. an exhibition. Added to {stream}'s queue only.</DialogDescription>
                    </DialogHeader>
                    {field("team1", "Player/Team 1")}
                    {field("team2", "Player/Team 2")}
                    {field("match", "Match")}
                    <DialogFooter><Button type="submit" disabled={!values.team1.trim() && !values.team2.trim()}>Add set</Button></DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

function QueueRow({stream, set, index}: {stream: string; set: QueueSet; index: number}) {
    const [label, color] = statusOf(set);
    const edit = (action: "move" | "move-to" | "remove" | "load", data: object, what: string) =>
        dashboard.streamQueue.edit(stream, action, {key: set.queueKey, ...data}).catch(failed(what));
    const station = set.station != null && Number(set.station) >= 0 ? String(set.station) : "—";

    return (
        <div className={cn(
            "grid min-h-13 grid-cols-[4.5rem_4.5rem_minmax(0,1.6fr)_minmax(0,1.2fr)_minmax(0,0.8fr)_6.5rem_auto] items-center gap-3 border-b px-4 text-[13px] last:border-0",
            set.onStream && "bg-accent shadow-[inset_3px_0_0_var(--brand)]",
        )}>
            <span className="text-muted-foreground tabular-nums">{etaText(set) || "—"}</span>
            <span className="text-muted-foreground">{station}</span>
            <span className="truncate font-semibold">{queueSetName(set)}</span>
            <span className="truncate text-muted-foreground">{set.match}</span>
            <span className="truncate text-muted-foreground">{set.phase}</span>
            <span className={cn("text-xs font-semibold", color)}>{label}</span>
            <span className="flex justify-end">
                <Button variant="ghost" size="icon-sm" aria-label={`Load ${queueSetName(set)} into the scoreboard`} title="Load into scoreboard"
                    onClick={() => edit("load", {}, "load the set").then(() => toast.success(`Loading ${queueSetName(set)}`))}>
                    <Download/>
                </Button>
                <Button variant="ghost" size="icon-sm" aria-label="Move up" disabled={index === 0} onClick={() => edit("move", {offset: -1}, "move the set")}>
                    <ArrowUp/>
                </Button>
                <Button variant="ghost" size="icon-sm" aria-label="Move down" onClick={() => edit("move", {offset: 1}, "move the set")}>
                    <ArrowDown/>
                </Button>
                <Popover>
                    <PopoverTrigger asChild>
                        <Button variant="ghost" size="icon-sm" aria-label="More actions"><MoreHorizontal/></Button>
                    </PopoverTrigger>
                    <PopoverContent align="end" className="w-56 p-1">
                        <button type="button" className="flex min-h-9 w-full cursor-pointer items-center gap-2 rounded-md px-2.5 text-sm hover:bg-accent [&_svg]:size-4"
                            onClick={() => edit("move-to", {index: 0}, "move the set")}>
                            <ChevronsUp/>Move to the top
                        </button>
                        <button type="button" className="flex min-h-9 w-full cursor-pointer items-center gap-2 rounded-md px-2.5 text-sm text-destructive hover:bg-accent [&_svg]:size-4"
                            onClick={() => edit("remove", {}, "remove the set")}>
                            <X/>Remove from this queue
                        </button>
                    </PopoverContent>
                </Popover>
            </span>
        </div>
    );
}

/**
 * The Stream Queue: each stream's coming sets, when they should start, and
 * loading the next one into the stream's scoreboard. Changes here only change
 * HyperDrive's queue, not start.gg's.
 */
export default function StreamQueuePage() {
    const queue = useHd((s) => s.stream_queue);
    const status = useStatus();
    const {options, change, reload} = useRemoteOptions<StreamQueueOptions>(dashboard.streamQueue.options, dashboard.streamQueue.setOptions);
    const [current, setCurrent] = React.useState<string | null>(null);
    const [addStream, setAddStream] = React.useState(false);
    const [addCustom, setAddCustom] = React.useState(false);

    const streams = queue?.streams ?? [];
    const stream = streams.find((s) => s.name === current) ?? streams[0];
    const updated = queue?.lastUpdated ? Math.round((Date.now() / 1000 - queue.lastUpdated)) : null;

    return (
        <PageBody>
            <PageHeader
                title="Stream Queue"
                description={[
                    updated != null ? `Updated ${updated < 60 ? `${updated}s` : `${Math.round(updated / 60)} min`} ago` : "Not updated yet",
                    queue?.average_set_minutes ? `sets take about ${queue.average_set_minutes} min` : null,
                ].filter(Boolean).join(" · ")}
            >
                <Button variant="secondary" disabled={!status?.tournament.loaded} onClick={() => dashboard.streamQueue.refresh().then(reload).catch(failed("update the queues"))}>
                    <RefreshCw/>Update the queues now
                </Button>
            </PageHeader>

            {options && (
                <div className="flex flex-wrap items-center gap-x-5 gap-y-2.5 text-[13px] text-muted-foreground">
                    <label className="flex items-center gap-2">
                        <Switch checked={options.autoRefresh} onCheckedChange={(on) => change({autoRefresh: on})}/>
                        Update every {options.interval}s
                    </label>
                    <label className="flex items-center gap-2">
                        <Switch checked={options.autoAdd} onCheckedChange={(on) => change({autoAdd: on})}/>
                        Add start.gg's streams automatically
                    </label>
                    <span className="flex items-center gap-2">
                        After a set
                        <Select value={options.afterSet} onValueChange={(v) => change({afterSet: v as StreamQueueOptions["afterSet"]})}>
                            <SelectTrigger aria-label="After a set" className="w-56 text-foreground"><SelectValue/></SelectTrigger>
                            <SelectContent>
                                {AFTER_SET.map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}
                            </SelectContent>
                        </Select>
                    </span>
                </div>
            )}

            <div role="tablist" aria-label="Streams" className="flex flex-wrap items-center gap-1.5">
                {streams.map((s) => (
                    <button
                        key={s.name}
                        type="button"
                        role="tab"
                        aria-selected={s.name === stream?.name}
                        onClick={() => setCurrent(s.name)}
                        className={cn(
                            "flex min-h-9 cursor-pointer items-center gap-2 rounded-lg border px-3.5 text-[13px] outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                            s.name === stream?.name ? "border-brand bg-accent font-semibold" : "text-muted-foreground hover:text-foreground",
                        )}
                    >
                        {s.name}<span className="text-muted-foreground">{s.sets.length}</span>
                    </button>
                ))}
                <Button variant="outline" size="sm" className="border-dashed" onClick={() => setAddStream(true)}><Plus/>Add stream</Button>
            </div>

            {!stream ? (
                <EmptyState>No streams yet. Streams in start.gg's stream queue show up here, or add one with Add stream.</EmptyState>
            ) : (
                <>
                    <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-card px-4 py-3 text-[13px] text-muted-foreground">
                        <span className="flex items-center gap-2">
                            Scoreboard
                            <Select
                                value={stream.scoreboard ? String(stream.scoreboard) : "none"}
                                onValueChange={(v) => dashboard.streamQueue.setScoreboard(stream.name, v === "none" ? null : Number(v)).catch(failed("change the scoreboard"))}
                            >
                                <SelectTrigger aria-label={`Scoreboard for ${stream.name}`} className="w-48 text-foreground"><SelectValue/></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="none">None</SelectItem>
                                    {(status?.scoreboards ?? []).map((sb) => (
                                        <SelectItem key={sb.number} value={String(sb.number)}>{sb.number} · {sb.name}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </span>
                        <div className="flex-1"/>
                        <Button
                            variant="ghost"
                            className="text-destructive"
                            onClick={() => window.confirm(`Remove ${stream.name}? start.gg's streams can be added back.`)
                                && dashboard.streamQueue.removeStream(stream.name).catch(failed("remove the stream"))}
                        >
                            Remove stream
                        </Button>
                        <Button
                            disabled={!stream.scoreboard}
                            title={stream.scoreboard ? undefined : "Pick its scoreboard first"}
                            onClick={() => dashboard.streamQueue.edit(stream.name, "load-next").then(() => toast.success("Loading the next set")).catch(failed("load the next set"))}
                        >
                            Load next set
                        </Button>
                    </div>

                    <Panel bodyClassName="p-0 overflow-x-auto">
                        <div className="min-w-[52rem]">
                            <div className="grid grid-cols-[4.5rem_4.5rem_minmax(0,1.6fr)_minmax(0,1.2fr)_minmax(0,0.8fr)_6.5rem_auto] gap-3 border-b px-4 py-2.5 text-[11px] font-bold tracking-wider text-muted-foreground uppercase">
                                <span>Starts</span><span>Station</span><span>Players</span><span>Round</span><span>Phase</span><span>Status</span><span className="w-[8.5rem] text-right">Actions</span>
                            </div>
                            {stream.sets.length === 0
                                ? <p className="p-4 text-sm text-muted-foreground">No sets in this queue.</p>
                                : stream.sets.map((set, i) => <QueueRow key={set.queueKey} stream={stream.name} set={set} index={i}/>)}
                        </div>
                    </Panel>

                    <div className="flex flex-wrap gap-2">
                        <Button variant="secondary" onClick={() => setAddCustom(true)}>Add custom…</Button>
                        <div className="flex-1"/>
                        <Button variant="outline" onClick={() => window.confirm(`Undo the changes made to ${stream.name}'s queue?`)
                            && dashboard.streamQueue.edit(stream.name, "reset").catch(failed("reset the queue"))}>
                            Reset to start.gg's queue
                        </Button>
                    </div>
                    <AddCustomDialog stream={stream.name} open={addCustom} onOpenChange={setAddCustom}/>
                </>
            )}
            <AddStreamDialog open={addStream} onOpenChange={setAddStream}/>
        </PageBody>
    );
}
