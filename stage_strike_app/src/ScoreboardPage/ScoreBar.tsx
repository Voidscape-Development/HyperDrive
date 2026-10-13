import {Minus, Plus} from "lucide-react";
import i18n from "../i18n/config";
import {api} from "./api";
import type {HDScoreInfo, HDTeamInfo} from "../backendDataTypes";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {cn} from "@/lib/utils";

/** The name shown for a team: its team name, or else its players' tags. */
export function teamDisplayName(team: HDTeamInfo, teamNumber: number) {
    if (team?.teamName) {
        return team.teamName;
    }
    const tags = Object.keys(team?.player ?? {})
        .sort()
        .map((k) => team.player[k]?.name)
        .filter(Boolean);
    return tags.length > 0 ? tags.join(" / ") : i18n.t("team_n", {value: teamNumber});
}

interface TeamScoreProps {
    scoreboardNumber: number;
    teamNumber: number;
    team: HDTeamInfo;
    maxScore: number | null;
    align: "left" | "right";
}

/**
 * One side of the score bar: the team's name and losers state, and its
 * score with buttons that change it right away.
 */
function TeamScore({scoreboardNumber, teamNumber, team, maxScore, align}: TeamScoreProps) {
    const score = Number(team?.score ?? 0);
    const left = align === "left";
    const name = teamDisplayName(team, teamNumber);

    return (
        <div
            className={cn(
                // On phones the name goes above the score so it has the width to show
                "flex min-w-0 flex-1 flex-col gap-1 sm:items-center sm:gap-3",
                left ? "items-start border-l-[6px] pl-2 sm:flex-row sm:pl-4" : "items-end border-r-[6px] pr-2 sm:flex-row-reverse sm:pr-4",
            )}
            style={{borderColor: team?.color || "transparent"}}
        >
            <div className={cn(
                "flex min-w-0 max-w-full flex-1 items-center gap-1.5 sm:flex-col",
                left ? "flex-row sm:items-start" : "flex-row-reverse sm:items-end",
            )}>
                <span className="min-w-0 truncate leading-tight font-semibold" title={name}>{name}</span>
                <Badge
                    asChild
                    variant={team?.losers ? "default" : "outline"}
                    className={cn("cursor-pointer font-bold", team?.losers && "bg-warning text-zinc-950")}
                >
                    <button
                        type="button"
                        title={i18n.t("losers_bracket")}
                        aria-pressed={!!team?.losers}
                        onClick={() => api.teamInfo(scoreboardNumber, teamNumber, {losers: !team?.losers}).catch(() => {})}
                    >
                        [L]
                    </button>
                </Badge>
            </div>

            <div className={cn("flex items-center sm:gap-1", left ? "flex-row" : "flex-row-reverse")}>
                <Button
                    variant="outline"
                    size="icon"
                    className="size-10 rounded-full sm:size-12"
                    aria-label={i18n.t("score_down", {value: teamNumber})}
                    disabled={score <= 0}
                    onClick={() => api.scoreDown(scoreboardNumber, teamNumber).catch(() => {})}
                >
                    <Minus/>
                </Button>
                <span className="min-w-[1.6ch] text-center text-4xl leading-none font-bold tabular-nums sm:min-w-[2ch] sm:text-5xl">
                    {score}
                </span>
                <Button
                    size="icon"
                    className="size-10 rounded-full sm:size-12"
                    aria-label={i18n.t("score_up", {value: teamNumber})}
                    disabled={maxScore !== null && score >= maxScore}
                    onClick={() => api.scoreUp(scoreboardNumber, teamNumber).catch(() => {})}
                >
                    <Plus/>
                </Button>
            </div>
        </div>
    );
}

/**
 * The current score, kept at the top of the page. Teams are shown as they
 * are on the scoreboard: team 1 on the left.
 */
export default function ScoreBar({scoreboardNumber, score}: {scoreboardNumber: number; score: HDScoreInfo}) {
    const teams = score?.team ?? {};
    const bestOf = Number(score?.best_of) || 0;
    const maxScore = bestOf > 0 ? Math.floor(bestOf / 2) + 1 : null;
    const details = [
        score?.phase,
        score?.match,
        bestOf > 0 ? i18n.t("best_of", {value: bestOf}) : null,
    ].filter(Boolean).join(" · ");

    return (
        <div className="sticky top-0 z-40 rounded-xl border bg-card/95 px-2 py-2 shadow-lg backdrop-blur sm:px-4">
            {details && (
                <div className="mb-1 truncate text-center text-xs text-muted-foreground">{details}</div>
            )}
            <div className="flex items-center gap-2 sm:gap-6">
                <TeamScore scoreboardNumber={scoreboardNumber} teamNumber={1} team={teams["1"]}
                           maxScore={maxScore} align={"left"}/>
                <span className="hidden font-bold text-muted-foreground sm:block">–</span>
                <TeamScore scoreboardNumber={scoreboardNumber} teamNumber={2} team={teams["2"]}
                           maxScore={maxScore} align={"right"}/>
            </div>
        </div>
    );
}
