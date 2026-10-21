import {Plus} from "lucide-react";
import i18n from "../i18n/config";
import Player from "./Player";
import {api} from "./api";
import {teamDisplayName} from "./setProgress";
import {saveOnCommit, useAutoSaveForm} from "./useAutoSaveForm";
import type {HDTeamInfo} from "../backendDataTypes";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {cn} from "@/lib/utils";

// <input type="color"> only takes #rrggbb
const hexColor = (color: string) => (/^#[0-9a-f]{6}/i.test(color ?? "") ? color.slice(0, 7).toLowerCase() : "#000000");

// The app's player colors first, then a few that stand apart from them
const PRESET_COLORS = ["#ff7a6d", "#29b6f6", "#f5a524", "#4ade80", "#c084fc", "#f472b6", "#e5e7eb"];

function ColorPicker({id, color, onChange}: {id: string; color: string; onChange: (color: string, immediate: boolean) => void}) {
    const custom = !PRESET_COLORS.includes(color);
    return (
        <Popover>
            <PopoverTrigger asChild>
                <button
                    type="button"
                    aria-label={i18n.t("side_color")}
                    className="size-8 shrink-0 cursor-pointer rounded-md border-2 border-background shadow-[0_0_0_1px_var(--border)] outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
                    style={{backgroundColor: color}}
                />
            </PopoverTrigger>
            <PopoverContent className="w-auto p-3">
                <div role="radiogroup" aria-labelledby={id} className="flex flex-wrap items-center gap-2">
                    <span id={id} className="sr-only">{i18n.t("side_color")}</span>
                    {PRESET_COLORS.map((preset) => (
                        <button
                            key={preset}
                            type="button"
                            role="radio"
                            aria-checked={color === preset}
                            aria-label={preset}
                            onClick={() => onChange(preset, true)}
                            className={cn(
                                "size-9 cursor-pointer rounded-full border-2 p-0.5 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                                color === preset ? "border-foreground" : "border-transparent",
                            )}
                        >
                            <span className="block size-full rounded-full" style={{backgroundColor: preset}}/>
                        </button>
                    ))}
                    <label
                        className={cn(
                            "relative flex size-9 cursor-pointer items-center justify-center rounded-full border-2 p-0.5 focus-within:ring-[3px] focus-within:ring-ring/50",
                            custom ? "border-foreground" : "border-dashed border-muted-foreground",
                        )}
                        title={i18n.t("custom_color")}
                    >
                        {custom ? <span className="block size-full rounded-full" style={{backgroundColor: color}}/> : <Plus className="size-4"/>}
                        <input
                            type="color"
                            aria-label={i18n.t("custom_color")}
                            value={color}
                            onChange={(e) => onChange(e.target.value, false)}
                            className="absolute inset-0 size-full cursor-pointer opacity-0"
                        />
                    </label>
                </div>
            </PopoverContent>
        </Popover>
    );
}

interface TeamColumnProps {
    scoreboardNumber: number;
    // 1 for the left side, 2 for the right
    teamNumber: 1 | 2;
    team: HDTeamInfo;
    className?: string;
}

/**
 * One side of the scoreboard: its color, name and losers mark, then its
 * players. Everything saves as it's edited.
 */
export function TeamColumn({scoreboardNumber, teamNumber, team, className}: TeamColumnProps) {
    const hdTeamId = String(teamNumber);
    const {values, setField, flush} = useAutoSaveForm(
        {name: team?.teamName ?? "", color: hexColor(team?.color)},
        (v, changed) => api.teamInfo(scoreboardNumber, hdTeamId, Object.fromEntries(changed.map((k) => [k, v[k]]))),
        900,
    );

    const playerKeys = Object.keys(team?.player ?? {}).sort((a, b) => Number(a) - Number(b));
    const teamId = `s-${scoreboardNumber}-t-${hdTeamId}`;
    const label = teamNumber === 1 ? i18n.t("team_n", {value: 1}) : i18n.t("team_n", {value: 2});

    return (
        <section aria-label={teamDisplayName(team, teamNumber)} className={cn("flex min-w-0 flex-col", className)}>
            <div className="flex items-center gap-2.5 rounded-t-xl border bg-card px-3.5 py-3" style={{boxShadow: `inset 0 3px 0 ${values.color}`}}>
                <ColorPicker id={teamId + "-color"} color={values.color} onChange={(color, immediate) => setField("color", color, {immediate})}/>
                <Input
                    aria-label={`${label}: ${i18n.t("team_name")}`}
                    placeholder={i18n.t("team_name")}
                    title={i18n.t("team_name_placeholder")}
                    value={values.name}
                    onChange={(e) => setField("name", e.target.value)}
                    {...saveOnCommit(flush)}
                />
                <Button
                    variant="outline"
                    className={cn(
                        "font-bold",
                        team?.losers && "border-warning bg-warning text-zinc-950 hover:bg-warning/90 hover:text-zinc-950 dark:border-warning dark:bg-warning dark:hover:bg-warning/90",
                    )}
                    title={i18n.t("losers_bracket")}
                    aria-label={i18n.t("losers_bracket")}
                    aria-pressed={!!team?.losers}
                    onClick={() => api.teamInfo(scoreboardNumber, hdTeamId, {losers: !team?.losers}).catch(() => {})}
                >
                    {i18n.t("losers_short")}
                </Button>
            </div>
            <div className="flex flex-col gap-6 rounded-b-xl border border-t-0 bg-card p-4">
                {playerKeys.length === 0 && <p className="text-sm text-muted-foreground">{i18n.t("no_players_loaded")}</p>}
                {playerKeys.map((key) => (
                    <Player
                        key={`${teamId}-p-${key}`}
                        scoreboardNumber={scoreboardNumber}
                        hdTeamId={hdTeamId}
                        teamId={teamId}
                        teamKey={key}
                        player={team.player[key]}
                        showHeading={playerKeys.length > 1}
                    />
                ))}
            </div>
        </section>
    );
}
