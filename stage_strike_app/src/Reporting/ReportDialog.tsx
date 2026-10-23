import React from "react";
import {toast} from "sonner";
import {COMPLETED, errorMessage, reportingAdmin, ReportingError, type Game, type ReportingSet} from "./api";
import {GameEditor} from "./GameEditor";
import {entrantName, gamesWinner, playedGames, setPlace, setTitle, startggScore} from "./sets";
import {Button} from "@/components/ui/button";
import {Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle} from "@/components/ui/dialog";
import {Spinner} from "@/components/ui/spinner";
import {Tabs, TabsContent, TabsList, TabsTrigger} from "@/components/ui/tabs";

/*
 * The Admin page's report: the set's games (from start.gg, to change), sent
 * as a final result or as an update, or a DQ. Sent right away, without
 * asking first, except to reset a completed set.
 */
export function ReportDialog({set, open, onOpenChange, onDone, initialTab = "games"}: {
    set: ReportingSet | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onDone: (set: ReportingSet) => void;
    initialTab?: "games" | "dq";
}) {
    const [games, setGames] = React.useState<Game[]>([]);
    const [detail, setDetail] = React.useState<ReportingSet | null>(null);
    const [loading, setLoading] = React.useState(false);
    const [busy, setBusy] = React.useState(false);
    const [tab, setTab] = React.useState(initialTab);

    React.useEffect(() => {
        if (!open || !set) {
            return;
        }
        setTab(initialTab);
        setDetail(set);
        setGames([]);
        setLoading(true);
        reportingAdmin.set(set.id)
            .then((fresh) => {
                setDetail(fresh);
                setGames(playedGames(fresh.games ?? []));
            })
            .catch((e) => toast.error(`Couldn't get the set's games from start.gg: ${errorMessage(e)}`))
            .finally(() => setLoading(false));
    }, [open, set, initialTab]);

    const current = detail ?? set;
    if (!current) {
        return null;
    }
    const completed = current.state === COMPLETED;
    const winner = gamesWinner(games);

    const send = (action: "report" | "update" | "dq", data: object, what: string) => {
        if (completed && action !== "update" && !window.confirm(
            `${setTitle(current)} is already completed on start.gg (${startggScore(current) || "reported"}). ` +
            "Reset it and report this instead? Sets that depend on it are reset on start.gg too.",
        )) {
            return;
        }
        setBusy(true);
        reportingAdmin.action(current.id, action, {...data, force: completed})
            .then(({set: changed}) => {
                toast.success(what);
                onDone(changed);
                onOpenChange(false);
            })
            .catch((e) => {
                const message = errorMessage(e);
                toast.error(e instanceof ReportingError && e.code === "STARTGG_REFUSED" ? `start.gg refused: ${message}` : message);
            })
            .finally(() => setBusy(false));
    };

    return (
        <Dialog open={open} onOpenChange={(o) => !busy && onOpenChange(o)}>
            <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-2xl">
                <DialogHeader>
                    <DialogTitle>{setTitle(current)}</DialogTitle>
                    <DialogDescription>
                        {setPlace(current)}
                        {completed && ` · Completed on start.gg${startggScore(current) ? ` (${startggScore(current)})` : ""}`}
                    </DialogDescription>
                </DialogHeader>

                <Tabs value={tab} onValueChange={(v) => setTab(v as "games" | "dq")}>
                    <TabsList>
                        <TabsTrigger value="games">Result</TabsTrigger>
                        <TabsTrigger value="dq">DQ</TabsTrigger>
                    </TabsList>
                    <TabsContent value="games" className="pt-3">
                        {loading ? (
                            <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner/>Getting the games from start.gg…</div>
                        ) : (
                            <GameEditor set={current} games={games} onChange={setGames}/>
                        )}
                        <DialogFooter className="mt-4 gap-2">
                            {!completed && (
                                <Button variant="secondary" disabled={busy || loading || !games.some((g) => g.winner)}
                                    title="Sends the games so far, without ending the set"
                                    onClick={() => send("update", {games}, "Score updated on start.gg")}>
                                    Send as update
                                </Button>
                            )}
                            <Button disabled={busy || loading || !winner}
                                title={winner ? undefined : "The score is tied: who won the set?"}
                                onClick={() => send("report", {games}, `Reported: ${entrantName(current, winner!)} wins`)}>
                                {busy && <Spinner/>}
                                {completed ? "Reset and report" : winner ? `Report · ${entrantName(current, winner)} wins` : "Report"}
                            </Button>
                        </DialogFooter>
                    </TabsContent>
                    <TabsContent value="dq" className="flex flex-col gap-3 pt-3">
                        <p className="text-sm text-muted-foreground">Who was disqualified? The other player wins the set, without games.</p>
                        <div className="grid gap-2 sm:grid-cols-2">
                            {([1, 2] as const).map((team) => {
                                const other = team === 1 ? 2 : 1;
                                return (
                                    <Button key={team} variant="outline" className="h-auto flex-col items-start gap-0.5 py-3 text-left whitespace-normal" disabled={busy}
                                        onClick={() => send("dq", {winner: other}, `${entrantName(current, team)} DQ'd: ${entrantName(current, other)} wins`)}>
                                        <span className="font-semibold">DQ {entrantName(current, team)}</span>
                                        <span className="text-xs font-normal text-muted-foreground">{entrantName(current, other)} wins</span>
                                    </Button>
                                );
                            })}
                        </div>
                    </TabsContent>
                </Tabs>
            </DialogContent>
        </Dialog>
    );
}
