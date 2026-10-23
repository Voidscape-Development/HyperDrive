import React from "react";
import {ArrowLeft, CheckCircle2, Search, Settings2} from "lucide-react";
import {BASE_URL} from "../env";
import {
    CALLED,
    errorMessage,
    IN_PROGRESS,
    ReportingError,
    stationApi,
    stationSession,
    type Game,
    type ReportingSet,
    type StationApi,
    type StationSets,
} from "./api";
import {GameEditor} from "./GameEditor";
import {ReportingNotice} from "./ReportingNotice";
import {entrantName, gamesScore, gamesWinner, matchesSearch, setPlace, setTitle, stateInfo} from "./sets";
import {setStationConfig, setStationLocked, setStationToken, useStationConfig, useStationLocked} from "./stationSession";
import {usePolledSets} from "./useSets";
import {useDesktopTheme} from "../Dashboard/theme";
import websocketInit from "../ScoreboardPage/websocketInit";
import {Button} from "@/components/ui/button";
import {Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle} from "@/components/ui/dialog";
import {Input} from "@/components/ui/input";
import {Spinner} from "@/components/ui/spinner";
import {cn} from "@/lib/utils";

/*
 * The players' reporting station: find your set (by name, set code, the
 * station you played on, or in the list), enter who won each game, and
 * send it. An admin approves it on the Approval page before it's reported
 * to start.gg.
 */

const BACK_TO_START_MS = 8000;

function StationSettings({open, onOpenChange, stations}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    stations: StationSets["stations"];
}) {
    const config = useStationConfig();
    const [name, setName] = React.useState(config.name);
    const [number, setNumber] = React.useState(config.number ? String(config.number) : "");
    React.useEffect(() => {
        if (open) {
            setName(config.name);
            setNumber(config.number ? String(config.number) : "");
        }
    }, [open, config]);
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <form className="flex flex-col gap-4" onSubmit={(e) => {
                    e.preventDefault();
                    const n = Number(number);
                    setStationConfig({name: name.trim(), number: number && Number.isFinite(n) && n > 0 ? n : null});
                    onOpenChange(false);
                }}>
                    <DialogHeader>
                        <DialogTitle>This reporting station</DialogTitle>
                        <DialogDescription>
                            Kept in this browser. A link like /report?station=5&amp;name=Station%205 sets it up too.
                        </DialogDescription>
                    </DialogHeader>
                    <label className="flex flex-col gap-1.5 text-xs font-semibold text-muted-foreground">
                        Name, shown to the admins with each result
                        <Input value={name} maxLength={40} placeholder="e.g. TO desk" onChange={(e) => setName(e.target.value)}/>
                    </label>
                    <label className="flex flex-col gap-1.5 text-xs font-semibold text-muted-foreground">
                        start.gg station number, whose sets are shown first (empty: none)
                        <Input inputMode="numeric" value={number} onChange={(e) => setNumber(e.target.value.replace(/\D/g, ""))}
                            list="reporting-stations"/>
                        <datalist id="reporting-stations">
                            {stations.map((s) => <option key={s.id} value={String(s.number)}/>)}
                        </datalist>
                    </label>
                    <DialogFooter><Button type="submit">Save</Button></DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

function SetButton({set, onPick}: {set: ReportingSet; onPick: (set: ReportingSet) => void}) {
    const state = stateInfo(set.state);
    return (
        <button
            type="button"
            onClick={() => onPick(set)}
            className="flex min-h-18 w-full cursor-pointer flex-col gap-1 rounded-xl border bg-card px-4 py-3 text-left outline-none hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
            <span className="flex items-center gap-2">
                <span className="min-w-0 flex-1 truncate text-base font-semibold">{setTitle(set)}</span>
                <span className={cn("shrink-0 text-xs font-semibold", state.className)}>{state.label}</span>
            </span>
            <span className="flex flex-wrap gap-x-2 text-[13px] text-muted-foreground">
                <span>{setPlace(set)}</span>
                {set.station && <span>· Station {set.station.number}</span>}
                {set.pending > 0 && <span className="text-warning">· A result was already sent</span>}
            </span>
        </button>
    );
}

function SetList({title, sets, onPick, empty}: {title: string; sets: ReportingSet[]; onPick: (set: ReportingSet) => void; empty?: string}) {
    if (!sets.length && !empty) {
        return null;
    }
    return (
        <section className="flex flex-col gap-2">
            <h2 className="text-sm font-bold tracking-wide text-muted-foreground uppercase">{title}</h2>
            {sets.length ? sets.map((s) => <SetButton key={s.id} set={s} onPick={onPick}/>) : <p className="text-sm text-muted-foreground">{empty}</p>}
        </section>
    );
}

function PickSet({data, onPick}: {data: StationSets; onPick: (set: ReportingSet) => void}) {
    const config = useStationConfig();
    const [search, setSearch] = React.useState("");
    const [all, setAll] = React.useState(false);
    const sets = data.sets;
    const playing = (s: ReportingSet) => s.state === IN_PROGRESS || s.state === CALLED;
    const sort = (list: ReportingSet[]) => [...list].sort((a, b) => Number(playing(b)) - Number(playing(a)) || setTitle(a).localeCompare(setTitle(b)));

    if (search.trim()) {
        const found = sort(sets.filter((s) => matchesSearch(s, search)));
        return (
            <div className="flex flex-col gap-4">
                <SearchBox value={search} onChange={setSearch}/>
                <SetList title={`${found.length} set${found.length === 1 ? "" : "s"} found`} sets={found.slice(0, 40)} onPick={onPick}
                    empty="No set to report found. Check the spelling, or ask a tournament organizer."/>
            </div>
        );
    }

    const here = config.number ? sort(sets.filter((s) => s.station?.number === config.number)) : [];
    const others = sort(sets.filter((s) => playing(s) && !here.includes(s)));
    const rest = sort(sets.filter((s) => !playing(s) && !here.includes(s)));

    return (
        <div className="flex flex-col gap-5">
            <SearchBox value={search} onChange={setSearch}/>
            {config.number && <SetList title={`At station ${config.number}`} sets={here} onPick={onPick} empty="No set at this station right now. Search for yours above."/>}
            <SetList title="Being played" sets={others} onPick={onPick}/>
            {all ? (
                <SetList title="Ready to play" sets={rest} onPick={onPick}/>
            ) : rest.length > 0 && (
                <Button variant="outline" size="lg" onClick={() => setAll(true)}>Show {rest.length} more set{rest.length === 1 ? "" : "s"} ready to play</Button>
            )}
            {sets.length === 0 && <p className="text-center text-muted-foreground">No set to report right now.</p>}
        </div>
    );
}

function SearchBox({value, onChange}: {value: string; onChange: (value: string) => void}) {
    return (
        <label className="relative flex items-center">
            <Search className="pointer-events-none absolute left-3.5 size-5 text-muted-foreground"/>
            <Input
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder="Your name, or the set's code (e.g. A1 C)"
                aria-label="Find your set"
                className="h-14 pl-11 text-lg md:text-lg"
                autoComplete="off"
            />
        </label>
    );
}

function ReportSet({set, api, onBack, onSent}: {
    set: ReportingSet;
    api: StationApi;
    onBack: () => void;
    onSent: (score: [number, number]) => void;
}) {
    const config = useStationConfig();
    const [games, setGames] = React.useState<Game[]>([]);
    const [submitter, setSubmitter] = React.useState("");
    const [busy, setBusy] = React.useState(false);
    const [error, setError] = React.useState<string | null>(null);
    const winner = gamesWinner(games);

    const submit = () => {
        setBusy(true);
        setError(null);
        api.submit({setId: set.id, games, station: config.name, stationNumber: config.number, submitter: submitter.trim()})
            .then(({score}) => onSent(score))
            .catch((e) => setError(errorMessage(e)))
            .finally(() => setBusy(false));
    };

    return (
        <div className="flex flex-col gap-5">
            <div className="flex items-start gap-3">
                <Button variant="ghost" size="icon-lg" aria-label="Back to the sets" onClick={onBack}><ArrowLeft/></Button>
                <div className="min-w-0 flex-1">
                    <h2 className="text-xl font-bold">{setTitle(set)}</h2>
                    <p className="text-sm text-muted-foreground">{setPlace(set)}</p>
                </div>
            </div>
            {set.pending > 0 && (
                <p className="rounded-xl border border-warning/50 px-4 py-3 text-sm">
                    A result was already sent for this set and is waiting for approval. Send this one only if it was wrong.
                </p>
            )}
            <GameEditor set={set} games={games} onChange={setGames} large/>
            <label className="flex flex-col gap-1.5 text-xs font-semibold text-muted-foreground">
                Your name (optional)
                <Input value={submitter} maxLength={40} onChange={(e) => setSubmitter(e.target.value)} className="h-11"/>
            </label>
            {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
            <Button size="lg" className="h-14 text-base font-bold" disabled={!winner || busy} onClick={submit}>
                {busy && <Spinner/>}
                {winner ? `Send · ${entrantName(set, winner)} wins ${Math.max(...gamesScore(games))}–${Math.min(...gamesScore(games))}` : "Who won? Set the score above"}
            </Button>
            <p className="text-center text-xs text-muted-foreground">A tournament organizer checks it before it's reported on start.gg.</p>
        </div>
    );
}

function Sent({set, score, onDone}: {set: ReportingSet; score: [number, number]; onDone: () => void}) {
    React.useEffect(() => {
        const id = setTimeout(onDone, BACK_TO_START_MS);
        return () => clearTimeout(id);
    }, [onDone]);
    return (
        <div className="flex flex-col items-center gap-4 py-10 text-center">
            <CheckCircle2 className="size-16 text-live"/>
            <h2 className="text-2xl font-bold">Result sent</h2>
            <p className="text-muted-foreground">
                {entrantName(set, 1)} {score[0]} – {score[1]} {entrantName(set, 2)}
                <br/>A tournament organizer will check it and report it on start.gg.
            </p>
            <Button size="lg" onClick={onDone}>Report another set</Button>
        </div>
    );
}

/** The station's content, on its own page or in the dashboard */
export function StationContent({api}: {api: StationApi}) {
    const {data, error, reload} = usePolledSets(() => api.sets());
    const [picked, setPicked] = React.useState<ReportingSet | null>(null);
    const [sent, setSent] = React.useState<[number, number] | null>(null);
    const reset = React.useCallback(() => {
        setPicked(null);
        setSent(null);
        reload();
    }, [reload]);

    if (error && !data) {
        return <ReportingNotice error={error}/>;
    }
    if (!data) {
        return <div className="flex items-center gap-2 text-muted-foreground"><Spinner/>Getting the sets…</div>;
    }
    if (picked && sent) {
        return <Sent set={picked} score={sent} onDone={reset}/>;
    }
    if (picked) {
        return <ReportSet set={picked} api={api} onBack={() => setPicked(null)} onSent={setSent}/>;
    }
    return (
        <>
            <ReportingNotice error={error} data={data}/>
            <PickSet data={data} onPick={setPicked}/>
        </>
    );
}

/** The station's PIN screen */
function StationPin() {
    const [pin, setPin] = React.useState("");
    const [error, setError] = React.useState<string | null>(null);
    const [busy, setBusy] = React.useState(false);
    return (
        <form className="flex w-full max-w-80 flex-col gap-3.5 self-center rounded-2xl border bg-card p-5" onSubmit={(e) => {
            e.preventDefault();
            setBusy(true);
            setError(null);
            stationSession.unlock(pin)
                .then(({token}) => setStationToken(token))
                .catch((err) => {
                    setPin("");
                    setError(err instanceof ReportingError && err.status === 429
                        ? "Too many wrong PINs. Wait a moment and try again."
                        : err instanceof ReportingError && err.status === 401 ? "That's not the PIN." : errorMessage(err));
                })
                .finally(() => setBusy(false));
        }}>
            <h1 className="text-lg font-bold">Set up this reporting station</h1>
            <p className="text-sm text-muted-foreground">
                A tournament organizer enters the station PIN (HyperDrive's Settings › Web Reporting) once. This browser remembers it.
            </p>
            <Input type="password" autoComplete="one-time-code" autoFocus aria-label="Station PIN" value={pin}
                onChange={(e) => setPin(e.target.value)} aria-invalid={!!error} className="h-12 text-xl tracking-[0.4em]"/>
            {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
            <Button type="submit" disabled={!pin || busy} className="h-12 text-base font-bold">{busy ? <Spinner/> : "Unlock"}</Button>
        </form>
    );
}

/** /report: the station on its own, full screen, behind the station PIN */
export default function StationPage() {
    useDesktopTheme();
    const locked = useStationLocked();
    const config = useStationConfig();
    const [failed, setFailed] = React.useState(false);
    const [settings, setSettings] = React.useState(false);
    const [stations, setStations] = React.useState<StationSets["stations"]>([]);

    React.useEffect(() => {
        document.title = "Report a set · HyperDrive";
        websocketInit();
        stationSession.session()
            .then(({pinRequired, unlocked}) => setStationLocked(pinRequired && !unlocked))
            .catch(() => setFailed(true));
    }, []);
    React.useEffect(() => {
        if (locked === false && settings) {
            stationApi.sets().then((d) => setStations(d.stations)).catch(() => {});
        }
    }, [locked, settings]);

    return (
        <div className="flex min-h-dvh flex-col bg-background text-foreground">
            <header className="flex items-center gap-3 border-b bg-card px-4 py-2.5">
                <img alt="" src={`${BASE_URL}/assets/icons/icon.png`} className="size-8"/>
                <span className="flex-1 font-semibold">
                    Report a set
                    {(config.name || config.number) && (
                        <span className="font-normal text-muted-foreground"> · {config.name || `Station ${config.number}`}</span>
                    )}
                </span>
                {locked === false && (
                    <Button variant="ghost" size="icon" aria-label="Set up this station" title="Set up this station" onClick={() => setSettings(true)}>
                        <Settings2/>
                    </Button>
                )}
            </header>
            <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 p-4 pb-16">
                {failed ? (
                    <p className="text-center text-muted-foreground">HyperDrive didn't answer. Is it running? Reload the page to try again.</p>
                ) : locked === "unknown" ? (
                    <Spinner/>
                ) : locked ? (
                    <StationPin/>
                ) : (
                    <StationContent api={stationApi}/>
                )}
            </main>
            <StationSettings open={settings} onOpenChange={setSettings} stations={stations}/>
        </div>
    );
}
