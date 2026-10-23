import React from "react";
import {useSelector} from "react-redux";
import {AlertTriangle, Check, Pencil, RefreshCw, X} from "lucide-react";
import {toast} from "sonner";
import type {ReduxState} from "../redux/store";
import {
    COMPLETED,
    errorMessage,
    reportingAdmin,
    ReportingError,
    type Conflict,
    type Game,
    type LogEntry,
    type ReportingSet,
    type Submission,
} from "./api";
import {GameEditor} from "./GameEditor";
import {ReportingNotice} from "./ReportingNotice";
import {clockTime, entrantName, gamesWinner, setPlace, setTitle, startggScore, timeAgo} from "./sets";
import {EmptyState, PageBody, PageHeader} from "../Dashboard/ui";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle} from "@/components/ui/dialog";
import {Input} from "@/components/ui/input";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {Spinner} from "@/components/ui/spinner";
import {Tabs, TabsContent, TabsList, TabsTrigger} from "@/components/ui/tabs";
import {cn} from "@/lib/utils";

/*
 * The Approval page: results players sent from a reporting station, reported
 * to start.gg once an admin approves them (as sent, or edited first), or
 * rejected. Below them, what was done before and the reporting log.
 */

const POLL_MS = 5000;

function conflictText(conflict: Conflict, current: ReportingSet | null | undefined) {
    switch (conflict) {
        case "completed":
            return `Already completed on start.gg${current && startggScore(current) ? ` (${startggScore(current)})` : ""}. Approving resets it first.`;
        case "entrants_changed":
            return "The set's players changed on start.gg since. It can only be rejected.";
        case "duplicate":
            return "Another result was sent for this set. Approving one drops the others.";
        case "updated":
            return "The set changed on start.gg since this was sent.";
        case "missing":
            return "This set isn't in the loaded event anymore.";
    }
}

/** A game, e.g. "Mario › Fox · Battlefield", the winner's side in bold */
function GameChips({set, games}: {set: ReportingSet; games: Game[]}) {
    const characters = useSelector((s: ReduxState) => s.hdCharacters.characters);
    const stages = useSelector((s: ReduxState) => (s.hdState.hdState as any)?.game?.stages ?? {});
    const name = (c: string) => characters[c]?.display_name ?? c;
    return (
        <ol className="flex flex-wrap gap-1.5">
            {games.map((g, i) => {
                const chars = ([1, 2] as const).map((t) => (g.characters[String(t) as "1" | "2"] ?? []).map(name).join(", "));
                const stage = g.stage ? (stages[g.stage]?.display_name ?? stages[g.stage]?.name ?? g.stage) : "";
                return (
                    <li key={i} className="rounded-md border bg-background px-2 py-1 text-xs">
                        <span className="text-muted-foreground">G{i + 1} </span>
                        <span className="font-semibold">{g.winner ? entrantName(set, g.winner) : "—"}</span>
                        {(chars[0] || chars[1]) && (
                            <span className="text-muted-foreground">
                                {" · "}<span className={cn(g.winner === 1 && "text-foreground")}>{chars[0] || "?"}</span>
                                {" vs "}<span className={cn(g.winner === 2 && "text-foreground")}>{chars[1] || "?"}</span>
                            </span>
                        )}
                        {stage && <span className="text-muted-foreground"> · {stage}</span>}
                    </li>
                );
            })}
        </ol>
    );
}

function Score({submission}: {submission: Submission}) {
    const {set, score, winner} = submission;
    return (
        <span className="flex flex-wrap items-baseline gap-x-2 text-base">
            <span className={cn(winner === 1 ? "font-bold" : "text-muted-foreground")}>{entrantName(set, 1)}</span>
            <span className="font-bold tabular-nums">{score[0]} – {score[1]}</span>
            <span className={cn(winner === 2 ? "font-bold" : "text-muted-foreground")}>{entrantName(set, 2)}</span>
        </span>
    );
}

function RejectButton({onReject, disabled}: {onReject: (reason: string) => void; disabled: boolean}) {
    const [open, setOpen] = React.useState(false);
    const [reason, setReason] = React.useState("");
    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button variant="ghost" className="text-destructive" disabled={disabled}><X/>Reject</Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-72">
                <form className="flex flex-col gap-2" onSubmit={(e) => {
                    e.preventDefault();
                    setOpen(false);
                    onReject(reason.trim());
                    setReason("");
                }}>
                    <label className="flex flex-col gap-1.5 text-xs text-muted-foreground">
                        Why (optional, kept in the log)
                        <Input autoFocus value={reason} maxLength={200} onChange={(e) => setReason(e.target.value)}/>
                    </label>
                    <Button type="submit" variant="destructive">Reject this result</Button>
                </form>
            </PopoverContent>
        </Popover>
    );
}

function EditDialog({submission, onClose, onApprove}: {
    submission: Submission | null;
    onClose: () => void;
    onApprove: (submission: Submission, games: Game[]) => Promise<void>;
}) {
    const [games, setGames] = React.useState<Game[]>([]);
    const [busy, setBusy] = React.useState(false);
    React.useEffect(() => {
        setGames(submission?.games ?? []);
    }, [submission]);
    if (!submission) {
        return null;
    }
    const set = submission.current ?? submission.set;
    const winner = gamesWinner(games);
    return (
        <Dialog open onOpenChange={(open) => !open && !busy && onClose()}>
            <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-2xl">
                <DialogHeader>
                    <DialogTitle>Edit, then approve</DialogTitle>
                    <DialogDescription>{setTitle(set)} · {setPlace(set)}</DialogDescription>
                </DialogHeader>
                <GameEditor set={set} games={games} onChange={setGames}/>
                <DialogFooter>
                    <Button variant="ghost" disabled={busy} onClick={onClose}>Cancel</Button>
                    <Button disabled={busy || !winner} onClick={() => {
                        setBusy(true);
                        onApprove(submission, games).finally(() => setBusy(false));
                    }}>
                        {busy && <Spinner/>}Approve and report{winner ? ` · ${entrantName(set, winner)} wins` : ""}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

function SubmissionCard({submission, busy, onApprove, onEdit, onReject}: {
    submission: Submission;
    busy: boolean;
    onApprove: () => void;
    onEdit: () => void;
    onReject: (reason: string) => void;
}) {
    const conflicts = submission.conflicts ?? [];
    const blocked = conflicts.includes("entrants_changed") || conflicts.includes("missing");
    return (
        <section className={cn("flex flex-col gap-3 rounded-xl border bg-card p-4", conflicts.length > 0 && "border-warning/60")}>
            <div className="flex flex-wrap items-start gap-x-4 gap-y-1">
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <Score submission={submission}/>
                    <span className="text-[13px] text-muted-foreground">{setPlace(submission.set)}</span>
                </div>
                <div className="flex flex-col items-end text-xs text-muted-foreground">
                    <span title={new Date(submission.createdAt * 1000).toLocaleString()}>
                        {clockTime(submission.createdAt)} · {timeAgo(submission.createdAt)}
                    </span>
                    <span>
                        {submission.station || "Reporting station"}
                        {submission.stationNumber ? ` (station ${submission.stationNumber})` : ""}
                        {submission.submitter ? ` · by ${submission.submitter}` : ""}
                    </span>
                </div>
            </div>

            {submission.games.length > 0 && <GameChips set={submission.set} games={submission.games}/>}

            {conflicts.map((c) => (
                <p key={c} className="flex items-start gap-2 text-[13px] text-warning">
                    <AlertTriangle className="mt-0.5 size-4 shrink-0"/>{conflictText(c, submission.current)}
                </p>
            ))}

            <div className="flex flex-wrap items-center justify-end gap-2">
                <RejectButton onReject={onReject} disabled={busy}/>
                <Button variant="outline" disabled={busy || blocked} onClick={onEdit}><Pencil/>Edit…</Button>
                <Button disabled={busy || blocked} onClick={onApprove}>
                    {busy ? <Spinner/> : <Check/>}Approve and report
                </Button>
            </div>
        </section>
    );
}

const STATUS_BADGE: Record<string, string> = {
    approved: "bg-live/20 text-foreground",
    rejected: "bg-destructive/20 text-foreground",
    superseded: "bg-muted text-muted-foreground",
};

function History({submissions}: {submissions: Submission[]}) {
    if (!submissions.length) {
        return <EmptyState>No results approved or rejected yet.</EmptyState>;
    }
    return (
        <div className="rounded-xl border bg-card">
            {submissions.map((s) => (
                <div key={s.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b px-4 py-2.5 text-[13px] last:border-0">
                    <Badge variant="secondary" className={cn("capitalize", STATUS_BADGE[s.status])}>{s.status}</Badge>
                    <span className="min-w-0 flex-1"><Score submission={s}/></span>
                    <span className="text-xs text-muted-foreground">
                        {s.station || "Station"} · {s.resolvedAt ? `${clockTime(s.resolvedAt)} by ${s.resolvedBy}` : ""}
                        {s.originalGames && " · edited"}
                        {s.message && ` · “${s.message}”`}
                    </span>
                </div>
            ))}
        </div>
    );
}

const ACTION_TEXT: Record<string, string> = {
    submitted: "Sent from a station",
    approved: "Approved",
    rejected: "Rejected",
    report: "Reported",
    update: "Score updated",
    dq: "DQ reported",
    call: "Called",
    start: "Marked in progress",
    reset: "Reset",
    assign_station: "Assigned to a station",
    assign_stream: "Assigned to a stream",
};

function Log({entries}: {entries: LogEntry[]}) {
    if (!entries.length) {
        return <EmptyState>Nothing reported from the web pages yet.</EmptyState>;
    }
    return (
        <div className="rounded-xl border bg-card">
            {entries.map((e, i) => (
                <div key={i} className="grid grid-cols-[3.5rem_minmax(0,1fr)] gap-x-3 border-b px-4 py-2 text-[13px] last:border-0 md:grid-cols-[3.5rem_10rem_minmax(0,1fr)_minmax(0,14rem)]">
                    <span className="text-muted-foreground tabular-nums" title={new Date(e.time * 1000).toLocaleString()}>{clockTime(e.time)}</span>
                    <span className={cn("font-semibold", !e.ok && "text-destructive")}>{ACTION_TEXT[e.action] ?? e.action}{!e.ok && " (failed)"}</span>
                    <span className="min-w-0 truncate max-md:col-start-2">
                        {e.setName}
                        {e.score && e.score.some((v) => v != null) && <span className="text-muted-foreground tabular-nums"> · {e.score[0] ?? 0} – {e.score[1] ?? 0}</span>}
                        {e.message && <span className={cn(e.ok ? "text-muted-foreground" : "text-destructive")}> · {e.message}</span>}
                    </span>
                    <span className="truncate text-xs text-muted-foreground max-md:col-start-2">{e.by}{e.submitter && e.submitter !== e.by ? ` · ${e.submitter}` : ""}</span>
                </div>
            ))}
        </div>
    );
}

export default function ApprovalPage() {
    const [pending, setPending] = React.useState<Submission[] | null>(null);
    const [history, setHistory] = React.useState<Submission[]>([]);
    const [log, setLog] = React.useState<LogEntry[]>([]);
    const [error, setError] = React.useState<{code: string; message: string} | null>(null);
    const [tab, setTab] = React.useState("pending");
    const [busy, setBusy] = React.useState<string | null>(null);
    const [editing, setEditing] = React.useState<Submission | null>(null);

    const load = React.useCallback(() => {
        reportingAdmin.submissions("pending")
            .then(({submissions}) => {
                setPending(submissions);
                setError(null);
            })
            .catch((e) => setError({code: e instanceof ReportingError ? e.code : "", message: errorMessage(e)}));
        if (tab === "history") {
            reportingAdmin.submissions("all").then(({submissions}) => setHistory(submissions.filter((s) => s.status !== "pending"))).catch(() => {});
        }
        if (tab === "log") {
            reportingAdmin.log().then(({log}) => setLog(log)).catch(() => {});
        }
    }, [tab]);

    React.useEffect(() => {
        load();
        const id = setInterval(() => document.visibilityState === "visible" && load(), POLL_MS);
        return () => clearInterval(id);
    }, [load]);

    const approve = (submission: Submission, games?: Game[], force = false): Promise<void> => {
        setBusy(submission.id);
        return reportingAdmin.approve(submission.id, {games, force})
            .then(() => {
                toast.success(`Reported: ${setTitle(submission.set)}`);
                setEditing(null);
                load();
            })
            .catch((e) => {
                if (e instanceof ReportingError && e.code === "SET_COMPLETED" && !force) {
                    const current = submission.current;
                    if (window.confirm(
                        `${setTitle(submission.set)} is already completed on start.gg${current?.state === COMPLETED && startggScore(current) ? ` (${startggScore(current)})` : ""}. ` +
                        "Reset it and report this result instead? Sets that depend on it are reset on start.gg too.",
                    )) {
                        return approve(submission, games, true);
                    }
                    return;
                }
                toast.error(errorMessage(e));
                load();
            })
            .finally(() => setBusy(null));
    };

    const reject = (submission: Submission, reason: string) => {
        setBusy(submission.id);
        reportingAdmin.reject(submission.id, reason)
            .then(() => {
                toast(`Rejected: ${setTitle(submission.set)}`);
                load();
            })
            .catch((e) => toast.error(errorMessage(e)))
            .finally(() => setBusy(null));
    };

    return (
        <PageBody>
            <PageHeader title="Approval" description="Results sent from the players' reporting stations. They're reported to start.gg once approved.">
                <Button variant="secondary" onClick={load}><RefreshCw/>Refresh</Button>
            </PageHeader>

            <ReportingNotice error={error} data={null}/>

            <Tabs value={tab} onValueChange={setTab}>
                <TabsList>
                    <TabsTrigger value="pending">Waiting{pending?.length ? ` (${pending.length})` : ""}</TabsTrigger>
                    <TabsTrigger value="history">Done</TabsTrigger>
                    <TabsTrigger value="log">Log</TabsTrigger>
                </TabsList>
                <TabsContent value="pending" className="flex flex-col gap-3 pt-3">
                    {pending === null ? (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner/>Loading…</div>
                    ) : pending.length === 0 ? (
                        <EmptyState>Nothing to approve. Results sent from a reporting station (/report) show up here.</EmptyState>
                    ) : pending.map((s) => (
                        <SubmissionCard
                            key={s.id}
                            submission={s}
                            busy={busy === s.id}
                            onApprove={() => approve(s)}
                            onEdit={() => setEditing(s)}
                            onReject={(reason) => reject(s, reason)}
                        />
                    ))}
                </TabsContent>
                <TabsContent value="history" className="pt-3"><History submissions={history}/></TabsContent>
                <TabsContent value="log" className="pt-3"><Log entries={log}/></TabsContent>
            </Tabs>

            <EditDialog submission={editing} onClose={() => setEditing(null)} onApprove={(s, games) => approve(s, games)}/>
        </PageBody>
    );
}
