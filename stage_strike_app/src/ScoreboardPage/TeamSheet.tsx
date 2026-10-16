import {Plus} from "lucide-react";
import i18n from "../i18n/config";
import Player from "./Player";
import {api} from "./api";
import {teamDisplayName, useMediaQuery, WIDE_SCREEN} from "./setProgress";
import {saveOnCommit, useAutoSaveForm} from "./useAutoSaveForm";
import type {HDTeamInfo} from "../backendDataTypes";
import {Field} from "@/components/Field";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Sheet, SheetClose, SheetContent, SheetDescription, SheetHeader, SheetTitle} from "@/components/ui/sheet";
import {cn} from "@/lib/utils";

// <input type="color"> only takes #rrggbb
const hexColor = (color: string) => (/^#[0-9a-f]{6}/i.test(color ?? "") ? color.slice(0, 7).toLowerCase() : "#000000");

// The app's player colors first, then a few that stand apart from them
const PRESET_COLORS = ["#ff7a6d", "#29b6f6", "#f5a524", "#4ade80", "#c084fc", "#f472b6", "#e5e7eb"];

interface TeamEditorProps {
    scoreboardNumber: number;
    // 1 for the left side, 2 for the right
    hdTeamId: string;
    team: HDTeamInfo;
}

/** A team's name, color and players. Everything saves as it's edited. */
function TeamEditor({scoreboardNumber, hdTeamId, team}: TeamEditorProps) {
    const {values, setField, flush} = useAutoSaveForm(
        {name: team.teamName ?? "", color: hexColor(team.color)},
        (v, changed) => api.teamInfo(scoreboardNumber, hdTeamId,
            Object.fromEntries(changed.map((k) => [k, v[k]]))),
        900,
    );

    const playerKeys = Object.keys(team.player ?? {}).sort((a, b) => Number(a) - Number(b));
    const teamId = `s-${scoreboardNumber}-t-${hdTeamId}`;
    const custom = !PRESET_COLORS.includes(values.color);

    return (
        <div className="flex flex-col gap-6">
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

            <div className="flex flex-col gap-4 border-t pt-5">
                <Field label={i18n.t("team_name")} htmlFor={teamId + "-name"}>
                    <Input
                        id={teamId + "-name"}
                        placeholder={i18n.t("team_name_placeholder")}
                        value={values.name}
                        onChange={(e) => setField("name", e.target.value)}
                        {...saveOnCommit(flush)}
                    />
                </Field>

                <div className="flex flex-col gap-1.5">
                    <span id={teamId + "-color"} className="text-xs text-muted-foreground">{i18n.t("side_color")}</span>
                    <div role="radiogroup" aria-labelledby={teamId + "-color"} className="flex flex-wrap items-center gap-2">
                        {PRESET_COLORS.map((color) => (
                            <button
                                key={color}
                                type="button"
                                role="radio"
                                aria-checked={values.color === color}
                                aria-label={color}
                                onClick={() => setField("color", color, {immediate: true})}
                                className={cn(
                                    "size-10 cursor-pointer rounded-full border-2 p-0.5 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                                    values.color === color ? "border-foreground" : "border-transparent",
                                )}
                            >
                                <span className="block size-full rounded-full" style={{backgroundColor: color}}/>
                            </button>
                        ))}
                        <label
                            className={cn(
                                "relative flex size-10 cursor-pointer items-center justify-center rounded-full border-2 p-0.5 focus-within:ring-[3px] focus-within:ring-ring/50",
                                custom ? "border-foreground" : "border-dashed border-muted-foreground",
                            )}
                            title={i18n.t("custom_color")}
                        >
                            {custom
                                ? <span className="block size-full rounded-full" style={{backgroundColor: values.color}}/>
                                : <Plus className="size-4"/>}
                            <input
                                type="color"
                                aria-label={i18n.t("custom_color")}
                                value={values.color}
                                onChange={(e) => setField("color", e.target.value)}
                                className="absolute inset-0 size-full cursor-pointer opacity-0"
                            />
                        </label>
                    </div>
                </div>
            </div>
        </div>
    );
}

interface TeamSheetProps extends TeamEditorProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

/**
 * Editing a side: a sheet from the bottom on phones, a panel on the right on
 * wide screens, so the score stays where it is.
 */
export default function TeamSheet({open, onOpenChange, scoreboardNumber, hdTeamId, team}: TeamSheetProps) {
    const wide = useMediaQuery(WIDE_SCREEN);
    const name = teamDisplayName(team, Number(hdTeamId));

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent
                side={wide ? "right" : "bottom"}
                showCloseButton={false}
                className={cn("gap-0", wide ? "w-full sm:max-w-md" : "max-h-[92dvh] rounded-t-3xl")}
                onEscapeKeyDown={(e) => {
                    // Escape closes an open suggestion list first, not the sheet
                    if ((e.target as HTMLElement)?.getAttribute?.("aria-expanded") === "true") {
                        e.preventDefault();
                    }
                }}
            >
                {!wide && <div aria-hidden className="mx-auto mt-2 h-1 w-10 shrink-0 rounded-full bg-muted-foreground/40"/>}
                <SheetHeader className="flex-row items-center gap-3 border-b px-4 py-3">
                    <span aria-hidden className="size-3 shrink-0 rounded-full" style={{backgroundColor: team?.color || undefined}}/>
                    <div className="min-w-0 flex-1">
                        <SheetDescription className="text-[11px] font-semibold tracking-wider uppercase">
                            {hdTeamId === "1" ? i18n.t("left_side") : i18n.t("right_side")}
                        </SheetDescription>
                        <SheetTitle className="truncate text-xl">{name}</SheetTitle>
                    </div>
                    <SheetClose asChild>
                        <Button className="h-11 rounded-xl px-5">{i18n.t("done")}</Button>
                    </SheetClose>
                </SheetHeader>
                <div className="min-h-0 flex-1 overflow-y-auto px-4 pt-4 pb-8">
                    {team && <TeamEditor scoreboardNumber={scoreboardNumber} hdTeamId={hdTeamId} team={team}/>}
                    <p className="mt-6 flex items-center gap-2 text-xs text-muted-foreground">
                        <span aria-hidden className="size-1.5 rounded-full bg-pick"/>
                        {i18n.t("changes_live")}
                    </p>
                </div>
            </SheetContent>
        </Sheet>
    );
}
