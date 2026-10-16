import React from "react";
import {ArrowLeftRight, ArrowRight, CircleCheck, RotateCcw, Trash2, Tv} from "lucide-react";
import {useSelector} from "react-redux";
import i18n from "../i18n/config";
import ScoreBoard, {Kbd, SetStatus} from "./ScoreBoard";
import SetDetails from "./SetDetails";
import TeamSheet from "./TeamSheet";
import {api} from "./api";
import {scoreActions} from "./scoreActions";
import {setProgress, teamDisplayName} from "./setProgress";
import type {ReduxState} from "../redux/store";
import type {HDScoreInfo} from "../backendDataTypes";
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
import {cn} from "@/lib/utils";

/** Clearing the scoreboard, kept apart from the everyday actions and confirmed first */
function ClearScoreboard({scoreboardNumber, iconOnly}: {scoreboardNumber: number; iconOnly?: boolean}) {
    return (
        <AlertDialog>
            <AlertDialogTrigger asChild>
                <Button
                    variant="outline"
                    className={cn(
                        "h-11 rounded-xl border-destructive/50 text-destructive hover:text-destructive",
                        iconOnly && "w-11 px-0",
                    )}
                    aria-label={i18n.t("clear_scoreboard")}
                    title={i18n.t("clear_scoreboard")}
                >
                    <Trash2/>
                    {!iconOnly && i18n.t("clear_scoreboard")}
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

interface CurrentSetProps {
    scoreboardNumber: number;
    wide: boolean;
    onLoadNext: () => void;
}

/**
 * The scoreboard being controlled: where the set stands, both sides as big
 * targets to score on, the everyday actions and the set's details.
 */
export default function CurrentSet({scoreboardNumber, wide, onLoadNext}: CurrentSetProps) {
    const score: HDScoreInfo = useSelector((state: ReduxState) => state.hdState.hdState?.score?.[scoreboardNumber]);
    const [detailsOpen, setDetailsOpen] = React.useState(false);
    const [editing, setEditing] = React.useState<1 | 2 | null>(null);

    const hasTeams = !!score?.team && Object.keys(score.team).length >= 2;
    const actions = scoreActions(scoreboardNumber, score);
    useScoreShortcuts(hasTeams ? actions : null);

    if (!hasTeams) {
        return <p className="p-4 text-lg font-medium">{i18n.t("no_set")}</p>;
    }

    const progress = setProgress(score);
    const toggleLosers = (team: 1 | 2) =>
        api.teamInfo(scoreboardNumber, team, {losers: !score.team[team]?.losers}).catch(() => {});

    // On phones the labels may wrap onto two lines rather than be cut off
    const actionButton = "h-11 rounded-xl px-2 text-[13px] leading-tight whitespace-normal sm:px-3 sm:text-sm sm:whitespace-nowrap";

    return (
        <div className="flex flex-col gap-4">
            <SetStatus
                score={score}
                progress={progress}
                onEditDetails={() => setDetailsOpen(!detailsOpen)}
                detailsOpen={detailsOpen}
            />

            {!wide && detailsOpen && <SetDetails scoreboardNumber={scoreboardNumber} score={score}/>}

            <ScoreBoard
                score={score}
                progress={progress}
                onAdd={actions.add}
                onTake={actions.take}
                onToggleLosers={toggleLosers}
                onEdit={setEditing}
            />

            {progress.winner
                ? (
                    <div className="flex flex-col gap-3 rounded-2xl bg-primary p-4 text-primary-foreground sm:flex-row sm:items-center">
                        <div className="flex min-w-0 flex-1 items-center gap-2.5">
                            <CircleCheck className="size-6 shrink-0 text-green-700"/>
                            <span className="truncate text-xl font-bold tracking-tight">
                                {i18n.t("team_wins", {
                                    team: teamDisplayName(score.team[progress.winner], progress.winner),
                                    score: `${Math.max(...progress.scores)}–${Math.min(...progress.scores)}`,
                                })}
                            </span>
                        </div>
                        <div className="flex">
                            <Button
                                className="h-11 w-full rounded-xl bg-primary-foreground text-primary hover:bg-primary-foreground/90 sm:w-auto"
                                onClick={onLoadNext}
                            >
                                {i18n.t("load_next_set")}<ArrowRight/>
                            </Button>
                        </div>
                    </div>
                )
                : null}

            <div className="grid grid-cols-[repeat(3,minmax(0,1fr))_auto] gap-2 sm:flex sm:flex-wrap">
                <Button variant="outline" className={actionButton} onClick={actions.swap} title={i18n.t("swap_teams")}>
                    <ArrowLeftRight/>
                    <span>{i18n.t("swap_short")}</span>
                    <Kbd>S</Kbd>
                </Button>
                <Button variant="outline" className={actionButton} onClick={actions.reset} title={i18n.t("reset_score")}>
                    <RotateCcw/>
                    <span>{i18n.t("reset_short")}</span>
                </Button>
                <Button
                    variant="outline"
                    className={actionButton}
                    title={i18n.t("load_stream_set")}
                    onClick={() => api.pullStreamSet(scoreboardNumber).catch(() => {})}
                >
                    <Tv/>
                    <span>{i18n.t("stream_set_short")}</span>
                </Button>
                <div className="sm:ml-auto">
                    <ClearScoreboard scoreboardNumber={scoreboardNumber} iconOnly={!wide}/>
                </div>
            </div>
            {wide && <p className="-mt-2 text-xs text-muted-foreground">{i18n.t("remove_point_hint")}</p>}

            {wide && <SetDetails scoreboardNumber={scoreboardNumber} score={score}/>}

            {([1, 2] as const).map((team) => (
                <TeamSheet
                    key={team}
                    open={editing === team}
                    onOpenChange={(open) => setEditing(open ? team : null)}
                    scoreboardNumber={scoreboardNumber}
                    hdTeamId={String(team)}
                    team={score.team[team]}
                />
            ))}
        </div>
    );
}
