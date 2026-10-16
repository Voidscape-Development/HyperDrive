import type {ReactNode} from "react";
import {Minus, Pencil, Plus, UserPen} from "lucide-react";
import i18n from "../i18n/config";
import {teamDisplayName, type SetProgress} from "./setProgress";
import type {HDCharacterSelection, HDScoreInfo, HDTeamInfo} from "../backendDataTypes";
import {Button} from "@/components/ui/button";
import {cn} from "@/lib/utils";

const sortedPlayers = (team: HDTeamInfo) => Object.keys(team?.player ?? {})
    .sort((a, b) => Number(a) - Number(b))
    .map((k) => team.player[k])
    .filter(Boolean);

export const Kbd = ({children, className}: {children: ReactNode; className?: string}) => (
    <kbd className={cn(
        "hidden rounded border border-border bg-muted px-1.5 font-mono text-[11px] font-medium text-foreground normal-case lg:inline",
        className,
    )}>
        {children}
    </kbd>
);

interface TeamHalfProps {
    teamNumber: 1 | 2;
    team: HDTeamInfo;
    progress: SetProgress;
    shortcut: string;
    onAdd: () => void;
    onTake: () => void;
    onToggleLosers: () => void;
    onEdit: () => void;
}

/**
 * One side of the scoreboard, as it is on stream: the whole card adds a point,
 * with taking one away, the losers state and editing the players below it.
 */
function TeamHalf({teamNumber, team, progress, shortcut, onAdd, onTake, onToggleLosers, onEdit}: TeamHalfProps) {
    const left = teamNumber === 1;
    const color = team?.color || "var(--muted-foreground)";
    const score = progress.scores[teamNumber - 1];
    const name = teamDisplayName(team, teamNumber);
    const players = sortedPlayers(team);
    // A lone player shows their sponsor above their tag
    const single = players.length === 1 && !team?.teamName ? players[0] : null;
    const characters = players.flatMap((p) => Object.values<HDCharacterSelection>(p?.character ?? {})
        .map((c) => c?.display_name)
        .filter(Boolean));
    const over = progress.winner !== null;
    const won = progress.winner === teamNumber;

    return (
        <div className="flex min-w-0 flex-col gap-2">
            <button
                type="button"
                onClick={onAdd}
                disabled={over}
                aria-label={i18n.t("add_point_to", {team: name})}
                className={cn(
                    "flex min-h-72 flex-1 flex-col overflow-hidden rounded-2xl border bg-card transition-[transform,background-color] outline-none select-none",
                    "focus-visible:ring-[3px] focus-visible:ring-ring/50 enabled:cursor-pointer enabled:hover:bg-accent/40 enabled:active:scale-[0.98] lg:min-h-64",
                    left ? "text-left" : "text-right",
                )}
                style={won ? {boxShadow: `0 0 0 2px ${color}`} : undefined}
            >
                <span aria-hidden className="h-1.5 w-full shrink-0" style={{backgroundColor: color}}/>
                <span
                    className="flex min-w-0 flex-col gap-1 px-3 pt-2.5 pb-3 sm:px-4"
                    style={{backgroundColor: `color-mix(in oklab, ${color} 14%, transparent)`}}
                >
                    <span className={cn(
                        "flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase",
                        !left && "flex-row-reverse",
                    )}>
                        {left ? i18n.t("left_side") : i18n.t("right_side")}
                        <Kbd>{shortcut}</Kbd>
                    </span>
                    {single?.team && <span className="truncate text-xs text-muted-foreground">{single.team}</span>}
                    <span className="truncate text-2xl leading-tight font-bold tracking-tight sm:text-3xl" title={name}>
                        {single?.name || name}
                    </span>
                    {(characters.length > 0 || team?.losers) && (
                        <span className={cn("flex min-w-0 flex-wrap gap-1.5 pt-1", !left && "justify-end")}>
                            {characters.map((c, i) => (
                                <span key={i} className="max-w-full truncate rounded-md bg-black/30 px-2 py-0.5 text-xs">{c}</span>
                            ))}
                            {team?.losers && (
                                <span className="rounded-md bg-warning px-1.5 py-0.5 text-xs font-bold text-zinc-950">L</span>
                            )}
                        </span>
                    )}
                </span>

                <span className="flex flex-1 flex-col items-center justify-center gap-3 py-4">
                    <span className="text-[7rem] leading-[0.85] font-black tracking-tighter tabular-nums sm:text-[8rem]">
                        {score}
                    </span>
                    {progress.firstTo !== null && progress.firstTo <= 10 && (
                        <span aria-hidden className="flex gap-1.5">
                            {Array.from({length: progress.firstTo}, (_, i) => (
                                <span
                                    key={i}
                                    className="size-3 rounded-full border-2"
                                    style={{borderColor: color, backgroundColor: i < score ? color : "transparent"}}
                                />
                            ))}
                        </span>
                    )}
                </span>

                <span className="flex items-center justify-center gap-1 pb-3 text-xs text-muted-foreground">
                    {over
                        ? (won ? i18n.t("set_over") : " ")
                        : <><Plus className="size-3.5"/>{i18n.t("tap_to_score")}</>}
                </span>
            </button>

            <div className={cn("flex gap-2", !left && "flex-row-reverse")}>
                <Button
                    variant="outline"
                    size="icon"
                    className="size-11 rounded-xl"
                    aria-label={i18n.t("take_point_from", {team: name})}
                    disabled={score <= 0}
                    onClick={onTake}
                >
                    <Minus/>
                </Button>
                <Button
                    variant="outline"
                    className={cn(
                        "h-11 rounded-xl px-3 font-bold",
                        team?.losers
                            ? "border-warning bg-warning text-zinc-950 hover:bg-warning/90 hover:text-zinc-950 dark:border-warning dark:bg-warning dark:hover:bg-warning/90"
                            : "text-muted-foreground",
                    )}
                    title={i18n.t("losers_bracket")}
                    aria-label={i18n.t("losers_bracket")}
                    aria-pressed={!!team?.losers}
                    onClick={onToggleLosers}
                >
                    {i18n.t("losers_short")}
                </Button>
                <Button
                    variant="outline"
                    className="h-11 min-w-11 rounded-xl px-3"
                    aria-label={i18n.t("edit_team", {team: name})}
                    onClick={onEdit}
                >
                    <UserPen/>
                    <span className="hidden sm:inline">{i18n.t("edit")}</span>
                </Button>
            </div>
        </div>
    );
}

/** What the set is and where it stands: "Game 4 · Ravyn on match point" */
export function SetStatus({score, progress, onEditDetails, detailsOpen}: {
    score: HDScoreInfo;
    progress: SetProgress;
    onEditDetails?: () => void;
    detailsOpen?: boolean;
}) {
    const details = [
        score?.phase,
        score?.match,
        progress.bestOf > 0 ? i18n.t("best_of", {value: progress.bestOf}) : null,
    ].filter(Boolean).join(" · ");

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
        <div className="flex items-center gap-3">
            <div className="min-w-0 flex-1">
                {details && (
                    <div className="truncate text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
                        {details}
                    </div>
                )}
                <div
                    aria-live="polite"
                    className={cn(
                        "truncate text-xl font-bold tracking-tight",
                        progress.stakes === "over" && "text-pick",
                        (progress.stakes === "match_point" || progress.stakes === "final_game") && "text-warning",
                    )}
                >
                    {status}
                </div>
            </div>
            {onEditDetails && (
                <Button
                    variant="outline"
                    size="icon"
                    className="size-11 shrink-0 rounded-xl lg:hidden"
                    aria-label={i18n.t("edit_set_details")}
                    aria-expanded={detailsOpen}
                    onClick={onEditDetails}
                >
                    <Pencil/>
                </Button>
            )}
        </div>
    );
}

interface ScoreBoardProps {
    score: HDScoreInfo;
    progress: SetProgress;
    onAdd: (team: 1 | 2) => void;
    onTake: (team: 1 | 2) => void;
    onToggleLosers: (team: 1 | 2) => void;
    onEdit: (team: 1 | 2) => void;
}

/** Both sides, team 1 on the left as on the scoreboard */
export default function ScoreBoard({score, progress, onAdd, onTake, onToggleLosers, onEdit}: ScoreBoardProps) {
    return (
        <section aria-label={i18n.t("scoreboard")} className="grid grid-cols-2 gap-2.5 sm:gap-4">
            {([1, 2] as const).map((teamNumber) => (
                <TeamHalf
                    key={teamNumber}
                    teamNumber={teamNumber}
                    team={score.team[teamNumber]}
                    progress={progress}
                    shortcut={teamNumber === 1 ? "Q" : "P"}
                    onAdd={() => onAdd(teamNumber)}
                    onTake={() => onTake(teamNumber)}
                    onToggleLosers={() => onToggleLosers(teamNumber)}
                    onEdit={() => onEdit(teamNumber)}
                />
            ))}
        </section>
    );
}
