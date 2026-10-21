import React from "react";
import {ArrowLeftRight, ArrowRight, Minus, Plus, RotateCcw, Trash2} from "lucide-react";
import i18n from "../i18n/config";
import {api} from "./api";
import {scoreActions} from "./scoreActions";
import {setProgress, teamDisplayName} from "./setProgress";
import {saveOnCommit, useAutoSaveForm} from "./useAutoSaveForm";
import type {HDScoreInfo} from "../backendDataTypes";
import {Field} from "@/components/Field";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {cn} from "@/lib/utils";

type Games = Record<string, {winner?: number | null}>;

/** Whether a key press is someone typing or working a dialog, not a shortcut */
const isTyping = (e: KeyboardEvent) => {
    const target = e.target as HTMLElement | null;
    return !!target && (
        target.isContentEditable
        || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)
        || !!target.closest("[role=dialog], [role=alertdialog]")
    );
};

/**
 * Q and P add a point to the left and right side, with Shift they take one
 * away, and S swaps the sides.
 */
function useScoreShortcuts(actions: ReturnType<typeof scoreActions> | null) {
    const ref = React.useRef(actions);
    ref.current = actions;

    React.useEffect(() => {
        const onKeyDown = (e: KeyboardEvent) => {
            if (!ref.current || e.repeat || e.ctrlKey || e.metaKey || e.altKey || isTyping(e)) {
                return;
            }
            const key = e.key.toLowerCase();
            const team = key === "q" ? 1 : key === "p" ? 2 : null;
            if (team) {
                e.preventDefault();
                if (e.shiftKey) {
                    ref.current.take(team);
                } else {
                    ref.current.add(team);
                }
            } else if (key === "s" && !e.shiftKey) {
                e.preventDefault();
                ref.current.swap();
            }
        };
        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, []);
}

/** What the set is and where it stands: "Game 4 · Ravyn on match point" */
function SetStatus({score}: {score: HDScoreInfo}) {
    const progress = setProgress(score);
    const name = (team: 1 | 2) => teamDisplayName(score?.team?.[team], team);
    const game = i18n.t("game_n", {value: progress.game});
    let status: string;
    switch (progress.stakes) {
        case "over": {
            const [a, b] = progress.scores;
            status = i18n.t("team_wins", {team: name(progress.winner), score: `${Math.max(a, b)}–${Math.min(a, b)}`});
            break;
        }
        case "final_game":
            status = `${game} · ${i18n.t("final_game")}`;
            break;
        case "match_point":
            status = `${game} · ${i18n.t("match_point", {team: name(progress.matchPointTeam)})}`;
            break;
        default:
            status = game;
    }
    return (
        <div
            aria-live="polite"
            className={cn(
                "text-lg font-bold tracking-tight",
                progress.stakes === "over" && "text-pick",
                (progress.stakes === "match_point" || progress.stakes === "final_game") && "text-warning",
            )}
        >
            {status}
        </div>
    );
}

/** Clearing the scoreboard, kept apart from the everyday actions and confirmed first */
function ClearScoreboard({scoreboardNumber}: {scoreboardNumber: number}) {
    return (
        <AlertDialog>
            <AlertDialogTrigger asChild>
                <Button variant="outline" className="border-destructive/50 text-destructive hover:text-destructive">
                    <Trash2/>{i18n.t("clear")}
                </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
                <AlertDialogHeader>
                    <AlertDialogTitle>{i18n.t("clear_scoreboard")}</AlertDialogTitle>
                    <AlertDialogDescription>{i18n.t("clear_scoreboard_confirm")}</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                    <AlertDialogCancel>{i18n.t("cancel")}</AlertDialogCancel>
                    <AlertDialogAction
                        className="bg-destructive text-white hover:bg-destructive/90"
                        onClick={() => api.clearAll(scoreboardNumber).catch(() => {})}
                    >
                        {i18n.t("clear")}
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    );
}

const BEST_OF = [0, 1, 3, 5, 7];

interface ScorePanelProps {
    scoreboardNumber: number;
    score: HDScoreInfo;
    onLoadNext: () => void;
    className?: string;
}

/**
 * The middle of the scoreboard: the set's phase, match and best of, the
 * score, its games and the actions on the whole set.
 */
export function ScorePanel({scoreboardNumber, score, onLoadNext, className}: ScorePanelProps) {
    const actions = scoreActions(scoreboardNumber, score);
    useScoreShortcuts(actions);
    const progress = setProgress(score);
    const games = Object.entries((score as unknown as {games?: Games}).games ?? {});

    const {values, setField, flush} = useAutoSaveForm(
        {phase: score?.phase ?? "", match: score?.match ?? "", bestOf: Number(score?.best_of) || 0},
        (v, changed) => api.setInfo(scoreboardNumber, Object.fromEntries(changed.map((k) => [k, v[k]]))),
        800,
    );
    const idBase = `s-${scoreboardNumber}-info-`;
    const bestOfOptions = BEST_OF.includes(values.bestOf) ? BEST_OF : [...BEST_OF, values.bestOf];

    const side = (team: 1 | 2) => {
        const color = score.team[team]?.color || "var(--muted-foreground)";
        const name = teamDisplayName(score.team[team], team);
        return (
            <div className="flex flex-col items-center gap-2 rounded-xl bg-background py-3" style={{boxShadow: `inset 0 3px 0 ${color}`}}>
                <span className="max-w-full truncate px-2 text-xs font-semibold text-muted-foreground">{name}</span>
                <span className="text-5xl leading-none font-black tabular-nums">{progress.scores[team - 1]}</span>
                <div className="flex gap-1.5">
                    <Button variant="secondary" size="icon-lg" aria-label={i18n.t("take_point_from", {team: name})} onClick={() => actions.take(team)}>
                        <Minus/>
                    </Button>
                    <Button variant="secondary" size="icon-lg" aria-label={i18n.t("add_point_to", {team: name})} onClick={() => actions.add(team)}>
                        <Plus/>
                    </Button>
                </div>
            </div>
        );
    };

    return (
        <section aria-label={i18n.t("set_details")} className={cn("flex flex-col gap-3.5 rounded-xl border bg-card p-4", className)}>
            <SetStatus score={score}/>
            <Field label={i18n.t("phase")} htmlFor={idBase + "phase"}>
                <Input id={idBase + "phase"} value={values.phase} onChange={(e) => setField("phase", e.target.value)} {...saveOnCommit(flush)}/>
            </Field>
            <Field label={i18n.t("match")} htmlFor={idBase + "match"}>
                <Input id={idBase + "match"} value={values.match} onChange={(e) => setField("match", e.target.value)} {...saveOnCommit(flush)}/>
            </Field>
            <div className="flex flex-col gap-1.5">
                <span id={idBase + "bestOf"} className="text-xs text-muted-foreground">{i18n.t("best_of", {value: ""}).trim()}</span>
                <div role="radiogroup" aria-labelledby={idBase + "bestOf"} className="flex w-fit rounded-lg bg-muted p-[3px]">
                    {bestOfOptions.map((n) => (
                        <button
                            key={n}
                            type="button"
                            role="radio"
                            aria-checked={n === values.bestOf}
                            onClick={() => setField("bestOf", n, {immediate: true})}
                            className={cn(
                                "h-8 min-w-9 cursor-pointer rounded-md px-2.5 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                                n === values.bestOf ? "bg-primary font-semibold text-primary-foreground" : "text-muted-foreground hover:text-foreground",
                            )}
                        >
                            {n === 0 ? i18n.t("no_best_of") : n}
                        </button>
                    ))}
                </div>
            </div>

            <div className="grid grid-cols-2 gap-2.5 pt-1">
                {side(1)}
                {side(2)}
            </div>

            {games.length > 0 && (
                <div className="flex flex-col gap-1.5">
                    <span className="text-xs text-muted-foreground">{i18n.t("games")}</span>
                    <div className="grid gap-1" style={{gridTemplateColumns: `repeat(${games.length}, minmax(0, 1fr))`}}>
                        {games.map(([n, game]) => {
                            const winner = game?.winner as 1 | 2 | null | undefined;
                            const color = winner ? score.team[winner]?.color : undefined;
                            return (
                                <span
                                    key={n}
                                    title={winner ? `${i18n.t("game_n", {value: n})}: ${teamDisplayName(score.team[winner], winner)}` : i18n.t("game_n", {value: n})}
                                    className={cn(
                                        "grid h-8 place-items-center rounded-md text-xs font-bold",
                                        winner ? "text-white" : "border border-dashed text-muted-foreground",
                                    )}
                                    style={color ? {backgroundColor: color} : undefined}
                                >
                                    {n}
                                </span>
                            );
                        })}
                    </div>
                </div>
            )}

            {progress.winner && (
                <Button className="h-11 font-bold" onClick={onLoadNext}>
                    {i18n.t("load_next_set")}<ArrowRight/>
                </Button>
            )}

            <div className="grid grid-cols-2 gap-1.5 pt-1">
                <Button variant="secondary" onClick={actions.swap} title={`${i18n.t("swap_teams")} (S)`}>
                    <ArrowLeftRight/>{i18n.t("swap_short")}
                </Button>
                <Button variant="secondary" onClick={actions.reset} title={i18n.t("reset_score")}>
                    <RotateCcw/>{i18n.t("reset_short")}
                </Button>
                <div className="col-span-2 grid"><ClearScoreboard scoreboardNumber={scoreboardNumber}/></div>
            </div>
            <p className="text-xs text-muted-foreground max-lg:hidden">Q / P add a point · {i18n.t("remove_point_hint")}</p>
        </section>
    );
}
