import React from "react";
import {ArrowLeftRight, Check, ChevronDown, Gamepad2, RefreshCw, Trophy, UsersRound, X} from "lucide-react";
import {shallowEqual, useSelector} from "react-redux";
import {toast} from "sonner";
import {dashboard, type TournamentEvents} from "./api";
import {refreshStatus, useCountdown, useStatus} from "./status";
import {useHd} from "./stateTypes";
import type {ReduxState} from "../redux/store";
import type {HDGameInfo} from "../backendDataTypes";
import {Button} from "@/components/ui/button";
import {Command, CommandEmpty, CommandInput, CommandItem, CommandList} from "@/components/ui/command";
import {Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle} from "@/components/ui/dialog";
import {Input} from "@/components/ui/input";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {Spinner} from "@/components/ui/spinner";
import {Switch} from "@/components/ui/switch";
import {cn} from "@/lib/utils";

const failed = (what: string) => () => {
    toast.error(`Couldn't ${what}. Check that HyperDrive is running.`);
};

const MENU_ITEM = "flex min-h-10 w-full cursor-pointer items-center gap-2.5 rounded-md px-2.5 text-left text-sm outline-none hover:bg-accent focus-visible:bg-accent disabled:cursor-default disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0";

// =====================================================
// LOADING A TOURNAMENT
// =====================================================
/** A tournament's events, to pick one to load */
function EventList({events, onPick}: {events: TournamentEvents; onPick: (url: string) => void}) {
    if (events.error) {
        return <p className="px-2.5 py-2 text-sm text-destructive">{events.message || "Couldn't get the events."}</p>;
    }
    const selected = events.selectedEventUrl;
    return (
        <div role="list" className="flex flex-col">
            {(events.events ?? []).map((event) => (
                <button key={event.url} type="button" role="listitem" className={MENU_ITEM} onClick={() => onPick(event.url)}>
                    <span className={cn(
                        "size-3.5 shrink-0 rounded-full border-2",
                        event.url === selected ? "border-[4px] border-brand" : "border-muted-foreground",
                    )}/>
                    <span className="min-w-0 flex-1 truncate">{event.name}</span>
                    {event.numEntrants != null && (
                        <span className="text-xs text-muted-foreground">{event.numEntrants} entrants</span>
                    )}
                </button>
            ))}
        </div>
    );
}

/** Pastes a tournament or event link, then picks the event */
export function LoadTournamentDialog({open, onOpenChange}: {open: boolean; onOpenChange: (open: boolean) => void}) {
    const [url, setUrl] = React.useState("");
    const [events, setEvents] = React.useState<TournamentEvents | null>(null);
    const [busy, setBusy] = React.useState(false);

    React.useEffect(() => {
        if (!open) {
            setUrl("");
            setEvents(null);
        }
    }, [open]);

    const find = (e: React.FormEvent) => {
        e.preventDefault();
        setBusy(true);
        dashboard.tournament.events(url.trim())
            .then(setEvents)
            .catch(failed("look up that tournament"))
            .finally(() => setBusy(false));
    };

    const load = (eventUrl: string) => {
        dashboard.tournament.load(eventUrl)
            .then(() => {
                toast.success("Loading the event");
                onOpenChange(false);
                setTimeout(refreshStatus, 500);
            })
            .catch(failed("load the event"));
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                    <DialogTitle>Load a tournament</DialogTitle>
                    <DialogDescription>
                        Paste a start.gg or parry.gg tournament or event link, a start.gg short link, or the tournament's slug.
                    </DialogDescription>
                </DialogHeader>
                <form onSubmit={find} className="flex gap-2">
                    <Input
                        autoFocus
                        aria-label="Tournament link"
                        placeholder="https://www.start.gg/tournament/..."
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                    />
                    <Button type="submit" disabled={!url.trim() || busy}>
                        {busy ? <Spinner/> : "Find events"}
                    </Button>
                </form>
                {events && (
                    <div className="flex max-h-80 flex-col gap-1 overflow-y-auto">
                        {events.tournamentName && <p className="px-2.5 text-sm font-semibold">{events.tournamentName}</p>}
                        <EventList events={events} onPick={load}/>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}

// =====================================================
// TOURNAMENT
// =====================================================
function TournamentCard() {
    const status = useStatus();
    const info = useHd((s) => s.tournamentInfo);
    const [open, setOpen] = React.useState(false);
    const [loadOpen, setLoadOpen] = React.useState(false);
    const [events, setEvents] = React.useState<TournamentEvents | null>(null);

    const loaded = status?.tournament.loaded;

    React.useEffect(() => {
        if (open && loaded) {
            setEvents(null);
            dashboard.tournament.events().then(setEvents).catch(() => setEvents({error: "failed"}));
        }
    }, [open, loaded]);

    if (status && !loaded) {
        return (
            <>
                <Button className="h-11 w-full justify-start gap-2.5 font-bold" onClick={() => setLoadOpen(true)}>
                    <Trophy/>Load tournament
                </Button>
                <LoadTournamentDialog open={loadOpen} onOpenChange={setLoadOpen}/>
            </>
        );
    }

    const name = info?.tournamentName || status?.tournament.url || "Loading…";
    const detail = [info?.eventName, info?.numEntrants ? `${info.numEntrants} entrants` : null].filter(Boolean).join(" · ");
    const act = (call: () => Promise<unknown>, done: string, what: string) => () => {
        setOpen(false);
        call().then(() => {
            toast.success(done);
            setTimeout(refreshStatus, 500);
        }).catch(failed(what));
    };

    return (
        <>
            <Popover open={open} onOpenChange={setOpen}>
                <PopoverTrigger asChild>
                    <button type="button" className={cn(MENU_ITEM, "min-h-13 gap-2.5 rounded-lg p-2 hover:bg-accent", open && "bg-accent")}>
                        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-secondary text-brand"><Trophy/></span>
                        <span className="flex min-w-0 flex-1 flex-col leading-snug">
                            <span className="truncate font-semibold">{name}</span>
                            <span className="truncate text-xs text-muted-foreground">{detail || status?.tournament.host}</span>
                        </span>
                        <ChevronDown className="text-muted-foreground"/>
                    </button>
                </PopoverTrigger>
                <PopoverContent side="right" align="start" className="w-90">
                    <div className="flex flex-col gap-0.5 px-2.5 pt-1.5 pb-2.5">
                        <span className="font-bold">{name}</span>
                        <span className="truncate text-xs text-muted-foreground">{status?.tournament.url}</span>
                    </div>
                    <p className="px-2.5 pb-1 text-[11px] font-bold tracking-wider text-muted-foreground uppercase">Event</p>
                    {events ? (
                        <EventList
                            events={events}
                            onPick={(url) => act(() => dashboard.tournament.load(url), "Loading the event", "switch events")()}
                        />
                    ) : (
                        <div className="flex items-center gap-2 px-2.5 py-2 text-sm text-muted-foreground"><Spinner/>Getting the events…</div>
                    )}
                    <div className="mx-1 my-2 h-px bg-border"/>
                    <button type="button" className={MENU_ITEM} onClick={act(dashboard.tournament.repull, "Pulling the entrants again", "repull the entrants")}>
                        <UsersRound/>Repull entrants
                    </button>
                    <button type="button" className={MENU_ITEM} onClick={() => {
                        setOpen(false);
                        setLoadOpen(true);
                    }}>
                        <ArrowLeftRight/>Load a different tournament…
                    </button>
                    <button type="button" className={cn(MENU_ITEM, "text-destructive")} onClick={act(dashboard.tournament.unload, "Tournament unloaded", "unload the tournament")}>
                        <X/>Unload tournament
                    </button>
                </PopoverContent>
            </Popover>
            <LoadTournamentDialog open={loadOpen} onOpenChange={setLoadOpen}/>
        </>
    );
}

// =====================================================
// GAME
// =====================================================
function GameCard() {
    const {games, game} = useSelector((s: ReduxState) => ({games: s.hdGames.value, game: s.hdState.hdState?.game}), shallowEqual);
    const modded = useHd((s) => ({has: !!s.game?.has_modded_content, on: !!s.game?.mods_active}));
    const [open, setOpen] = React.useState(false);
    const list = React.useMemo(() => (Object.values(games ?? {}) as HDGameInfo[]).sort((a, b) => (a.name ?? "").localeCompare(b.name ?? "")), [games]);

    const pick = (codename: string, mods = false) => {
        setOpen(false);
        dashboard.game(codename, mods).catch(failed("change the game"));
    };

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <button type="button" className={cn(MENU_ITEM, "min-h-13 gap-2.5 rounded-lg p-2 hover:bg-accent", open && "bg-accent")}>
                    <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-secondary"><Gamepad2/></span>
                    <span className="flex min-w-0 flex-1 flex-col leading-snug">
                        <span className="truncate font-semibold">{game?.name || "No game"}</span>
                        <span className="truncate text-xs text-muted-foreground">Game{modded.on ? " · modded content" : ""}</span>
                    </span>
                    <ChevronDown className="text-muted-foreground"/>
                </button>
            </PopoverTrigger>
            <PopoverContent side="right" align="start" className="w-80 p-0">
                <Command>
                    <CommandInput placeholder="Search games"/>
                    <CommandList className="max-h-72">
                        <CommandEmpty>No game found. Download its assets in HyperDrive first.</CommandEmpty>
                        {list.map((g) => (
                            <CommandItem key={g.codename} value={`${g.name} ${g.codename}`} onSelect={() => pick(g.codename)}>
                                <span className="flex-1 truncate">{g.name}</span>
                                {g.codename === game?.codename && <Check className="text-brand"/>}
                            </CommandItem>
                        ))}
                    </CommandList>
                </Command>
                {game?.codename && (
                    <div className="flex flex-col gap-1 border-t p-2">
                        {modded.has && (
                            <label className={cn(MENU_ITEM, "justify-between")}>
                                Modded content
                                <Switch checked={modded.on} onCheckedChange={(on) => pick(game.codename!, on)}/>
                            </label>
                        )}
                        <button type="button" className={MENU_ITEM} onClick={() => pick(game.codename!, modded.on)}>
                            <RefreshCw/>Reload game assets
                        </button>
                    </div>
                )}
            </PopoverContent>
        </Popover>
    );
}

// =====================================================
// COMPLETED SETS
// =====================================================
export function useCompletedSetsText() {
    const status = useStatus();
    const job = status?.completedSets;
    const seconds = useCountdown(job);
    if (!job) {
        return {dot: "off" as const, text: ""};
    }
    if (job.running) {
        return {dot: "busy" as const, text: "Pulling…"};
    }
    if (!job.autoPull) {
        return {dot: "off" as const, text: "Auto pull off"};
    }
    if (!job.supported) {
        return {dot: "off" as const, text: "Waiting for a tournament"};
    }
    return {dot: "ok" as const, text: seconds == null ? "Auto pull on" : `Next pull in ${seconds}s`};
}

export const DOT_CLASS = {ok: "bg-live", busy: "bg-brand", off: "bg-muted-foreground/50"};

function CompletedSetsRow() {
    const status = useStatus();
    const {dot, text} = useCompletedSetsText();
    const job = status?.completedSets;

    return (
        <div className="flex items-center gap-2.5 rounded-lg bg-background/60 py-1.5 pr-1.5 pl-3">
            <span aria-hidden className={cn("size-2 shrink-0 rounded-full", DOT_CLASS[dot])}/>
            <span className="flex min-w-0 flex-1 flex-col leading-snug">
                <span className="text-[13px] font-semibold">Completed sets</span>
                <span className="truncate text-xs text-muted-foreground">{text}</span>
            </span>
            <Switch
                aria-label="Auto pull completed sets"
                title="Auto pull completed sets"
                checked={!!job?.autoPull}
                onCheckedChange={(on) => dashboard.completedSets.auto(on).then(refreshStatus).catch(failed("change auto pull"))}
            />
            <Button
                variant="ghost"
                size="icon-sm"
                aria-label="Pull completed sets now"
                title="Pull completed sets now"
                disabled={!job?.supported || job?.running}
                onClick={() => dashboard.completedSets.pull().then(refreshStatus).catch(failed("pull the completed sets"))}
            >
                <RefreshCw/>
            </Button>
        </div>
    );
}

/** The sidebar's Event section: what's loaded, and what to do with it */
export function EventControls() {
    return (
        <div className="flex flex-col gap-0.5">
            <TournamentCard/>
            <GameCard/>
            <CompletedSetsRow/>
        </div>
    );
}
