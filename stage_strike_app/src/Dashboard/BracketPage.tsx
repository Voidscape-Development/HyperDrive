import React from "react";
import {Link} from "react-router-dom";
import {Crosshair, Download, RefreshCw} from "lucide-react";
import {toast} from "sonner";
import {dashboard, type BracketOptions} from "./api";
import {useStatus} from "./status";
import {useHd} from "./stateTypes";
import {EmptyState, PageBody, PageHeader, Panel, useRemoteOptions} from "./ui";
import {Button} from "@/components/ui/button";
import {Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle} from "@/components/ui/dialog";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {Switch} from "@/components/ui/switch";
import {cn} from "@/lib/utils";

interface ExportSet {
    id: string;
    players?: ({name?: string; bye?: boolean} | null)[];
    score?: (number | null)[];
    winner?: number | null;
    completed?: boolean;
}

interface ExportRound {
    key: string;
    name: string;
    sets: string[];
}

interface ExportBracket {
    name?: string;
    type?: string;
    sets?: Record<string, ExportSet>;
    sides?: Record<string, ExportRound[]>;
}

const SIDES: [string, string][] = [["winners", "Winners"], ["losers", "Losers"], ["grand_final", "Grand final"]];

const failed = (what: string) => () => toast.error(`Couldn't ${what}.`);

function SetBox({set, focused}: {set: ExportSet; focused: boolean}) {
    const line = (i: 0 | 1) => {
        const player = set.players?.[i];
        const won = set.completed && set.winner === i;
        return (
            <span className={cn("flex justify-between gap-2 px-2.5 py-1.5", i === 0 && "border-b", won ? "font-bold" : "text-muted-foreground", won && "text-foreground")}>
                <span className="truncate">{player?.bye ? "Bye" : player?.name || "—"}</span>
                <span className="tabular-nums">{set.score?.[i] ?? ""}</span>
            </span>
        );
    };
    return (
        <div className={cn("flex flex-col rounded-lg border bg-background text-xs", focused && "border-brand ring-1 ring-brand")}>
            {line(0)}
            {line(1)}
        </div>
    );
}

/** The bracket as it goes to the layouts, a column per round */
function BracketView({bracket, focus}: {bracket?: ExportBracket; focus: string[]}) {
    if (!bracket?.sides || !bracket.sets) {
        return <EmptyState>This channel has no bracket yet. Load one from start.gg, or build one in HyperDrive's Bracket tab.</EmptyState>;
    }
    return (
        <div className="flex min-w-max flex-col gap-6">
            {SIDES.filter(([key]) => bracket.sides![key]?.length).map(([key, label]) => (
                <div key={key} className="flex flex-col gap-2">
                    <span className="text-[11px] font-bold tracking-wider text-muted-foreground uppercase">{label}</span>
                    <div className="flex items-stretch gap-6">
                        {bracket.sides![key].map((round) => (
                            <div key={round.key} className="flex w-48 flex-col gap-1.5">
                                <span className="truncate text-xs font-semibold text-muted-foreground">{round.name}</span>
                                <div className="flex flex-1 flex-col justify-around gap-2.5">
                                    {round.sets.map((id) => bracket.sets![id] && (
                                        <SetBox key={id} set={bracket.sets![id]} focused={focus.includes(id)}/>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}

/** Picks a start.gg phase group to load into the current channel */
function LoadDialog({options, open, onOpenChange}: {options: BracketOptions; open: boolean; onOpenChange: (open: boolean) => void}) {
    const [phase, setPhase] = React.useState<string>("");
    const [group, setGroup] = React.useState<string>("");
    const groups = options.sources.find((s) => String(s.index) === phase)?.groups ?? [];

    React.useEffect(() => {
        setGroup(groups.length === 1 ? "0" : "");
    }, [phase]); // eslint-disable-line react-hooks/exhaustive-deps

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Load a bracket from start.gg</DialogTitle>
                    <DialogDescription>Its players and sets are loaded, and shown on the channel open in HyperDrive's Bracket tab. Loading it again reloads it.</DialogDescription>
                </DialogHeader>
                {options.sources.length === 0 ? (
                    <p className="text-sm text-muted-foreground">The event's phases haven't loaded. Load a tournament first.</p>
                ) : (
                    <div className="flex flex-col gap-3">
                        <Select value={phase} onValueChange={setPhase}>
                            <SelectTrigger aria-label="Phase" className="w-full"><SelectValue placeholder="Phase"/></SelectTrigger>
                            <SelectContent>
                                {options.sources.map((s) => <SelectItem key={s.index} value={String(s.index)}>{s.name}</SelectItem>)}
                            </SelectContent>
                        </Select>
                        <Select value={group} onValueChange={setGroup} disabled={groups.length === 0}>
                            <SelectTrigger aria-label="Phase group" className="w-full"><SelectValue placeholder="Phase group"/></SelectTrigger>
                            <SelectContent>
                                {groups.map((g) => <SelectItem key={g.index} value={String(g.index)}>{g.name || "Bracket"}</SelectItem>)}
                            </SelectContent>
                        </Select>
                    </div>
                )}
                <DialogFooter>
                    <Button
                        disabled={!phase || !group}
                        onClick={() => dashboard.bracket.load(Number(phase), Number(group))
                            .then(() => {
                                toast.success("Loading the bracket");
                                onOpenChange(false);
                            })
                            .catch(failed("load the bracket"))}
                    >
                        Load
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

/**
 * The Bracket: what's shown on stream, by channel. Building brackets by hand
 * (phases, seeds) stays in the desktop app's Bracket tab.
 */
export default function BracketPage() {
    const bracket = useHd((s) => s.bracket as unknown as {channels?: Record<string, {bracket?: ExportBracket}>; focus?: Record<string, {sets?: string[]}>} | undefined);
    const loaded = useStatus()?.tournament.loaded;
    const {options, reload} = useRemoteOptions<BracketOptions>(dashboard.bracket.options, async () => {});
    const [channel, setChannel] = React.useState("main");
    const [loadOpen, setLoadOpen] = React.useState(false);

    // The options (auto update, top N) change from the desktop app too
    React.useEffect(() => {
        const id = setInterval(reload, 5000);
        return () => clearInterval(id);
    }, [reload]);

    const channels = options?.channels ?? [{name: "main", phase: null, limit: null}];
    const current = channels.find((c) => c.name === channel) ?? channels[0];
    const setChannelOption = (data: {phase?: string; limit?: number | null}) =>
        dashboard.bracket.setChannel(current.name, data).then(reload).catch(failed("change the channel"));

    return (
        <PageBody>
            <PageHeader title="Bracket" description="What the bracket layouts show, by channel. Build brackets by hand in HyperDrive's Bracket tab.">
                <Button variant="secondary" disabled={!loaded || !options} onClick={() => setLoadOpen(true)}>
                    <Download/>Load from start.gg
                </Button>
                <Button variant="ghost" asChild>
                    <Link to="/dashboard/bracket-focus"><Crosshair/>Focus</Link>
                </Button>
            </PageHeader>

            <div className="flex flex-wrap items-center gap-x-5 gap-y-2.5 text-[13px] text-muted-foreground">
                <div role="tablist" aria-label="Channels" className="flex flex-wrap gap-1">
                    {channels.map((c) => (
                        <button key={c.name} type="button" role="tab" aria-selected={c.name === current.name} onClick={() => setChannel(c.name)}
                            className={cn(
                                "min-h-9 cursor-pointer rounded-lg border px-3.5 text-[13px]",
                                c.name === current.name ? "border-brand bg-accent font-semibold text-foreground" : "hover:text-foreground",
                            )}>
                            {c.name === "main" ? "Main" : c.name}
                        </button>
                    ))}
                </div>
                {options && options.phases.length > 0 && (
                    <span className="flex items-center gap-2">
                        Phase
                        <Select value={current.phase ?? undefined} onValueChange={(phase) => setChannelOption({phase})}>
                            <SelectTrigger aria-label="Phase" className="w-48 text-foreground"><SelectValue placeholder="No phase"/></SelectTrigger>
                            <SelectContent>
                                {options.phases.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}{p.fromProvider ? " · start.gg" : ""}</SelectItem>)}
                            </SelectContent>
                        </Select>
                    </span>
                )}
                <span className="flex items-center gap-2">
                    On stream
                    <Select value={current.limit ? String(current.limit) : "all"} onValueChange={(v) => setChannelOption({limit: v === "all" ? null : Number(v)})}>
                        <SelectTrigger aria-label="Players on stream" className="w-32 text-foreground"><SelectValue/></SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">Everyone</SelectItem>
                            {[4, 6, 8, 12, 16, 24, 32, 48, 64].map((n) => <SelectItem key={n} value={String(n)}>Top {n}</SelectItem>)}
                        </SelectContent>
                    </Select>
                </span>
            </div>

            <Panel bodyClassName="overflow-x-auto p-5">
                <BracketView bracket={bracket?.channels?.[current.name]?.bracket} focus={bracket?.focus?.[current.name]?.sets ?? []}/>
            </Panel>

            {options && (
                <div className="flex flex-wrap items-center justify-end gap-3 text-[13px] text-muted-foreground">
                    <Button variant="secondary" disabled={!options.loaded || options.fetching}
                        onClick={() => dashboard.bracket.updateSets().then(reload).catch(failed("update the sets"))}>
                        <RefreshCw className={cn(options.fetching && "animate-spin")}/>Update sets
                    </Button>
                    <label className="flex items-center gap-2">
                        <Switch checked={options.autoUpdate.enabled}
                            onCheckedChange={(on) => dashboard.bracket.autoUpdate(on).then(reload).catch(failed("change auto update"))}/>
                        Auto update{options.autoUpdate.enabled && options.autoUpdate.remainingMs != null
                            ? ` · next in ${Math.round(options.autoUpdate.remainingMs / 1000)}s` : ""}
                    </label>
                </div>
            )}

            {options && <LoadDialog options={options} open={loadOpen} onOpenChange={setLoadOpen}/>}
        </PageBody>
    );
}
