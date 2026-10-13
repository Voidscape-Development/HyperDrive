import i18n from "../i18n/config";
import Player from "./Player";
import {api} from "./api";
import {saveOnCommit, useAutoSaveForm} from "./useAutoSaveForm";
import type {HDTeamInfo} from "../backendDataTypes";
import {Field} from "@/components/Field";
import {Card} from "@/components/ui/card";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {Switch} from "@/components/ui/switch";
import {Tooltip, TooltipContent, TooltipTrigger} from "@/components/ui/tooltip";

// <input type="color"> only takes #rrggbb
const hexColor = (color: string) => (/^#[0-9a-f]{6}/i.test(color ?? "") ? color.slice(0, 7) : "#000000");

interface TeamProps {
    scoreboardNumber: number;
    // 1 for the left side, 2 for the right
    hdTeamId: string;
    team: HDTeamInfo;
}

/**
 * A team: its name, color and losers state, and its players. Everything
 * saves as it's edited.
 */
export default function Team({scoreboardNumber, hdTeamId, team}: TeamProps) {
    const {values, setField, flush} = useAutoSaveForm(
        {name: team.teamName ?? "", color: hexColor(team.color)},
        (v, changed) => api.teamInfo(scoreboardNumber, hdTeamId,
            Object.fromEntries(changed.map((k) => [k, v[k]]))),
        900,
    );

    const playerKeys = Object.keys(team.player ?? {}).sort((a, b) => Number(a) - Number(b));
    const teamId = `s-${scoreboardNumber}-t-${hdTeamId}`;

    return (
        <Card className="gap-3 border-t-4 p-3" style={{borderTopColor: team.color || undefined}}>
            <div className="flex items-end gap-3">
                <Tooltip>
                    <TooltipTrigger asChild>
                        <input
                            type={"color"}
                            aria-label={i18n.t("team_color")}
                            value={values.color}
                            onChange={(e) => setField("color", e.target.value)}
                            className="size-9 shrink-0 cursor-pointer rounded-md border-0 bg-transparent p-0"
                        />
                    </TooltipTrigger>
                    <TooltipContent>{i18n.t("team_color")}</TooltipContent>
                </Tooltip>
                <Field label={i18n.t("team_name")} htmlFor={teamId + "-name"} className="flex-1">
                    <Input
                        id={teamId + "-name"}
                        placeholder={i18n.t("team_name_placeholder")}
                        value={values.name}
                        onChange={(e) => setField("name", e.target.value)}
                        {...saveOnCommit(flush)}
                    />
                </Field>
            </div>
            <div className="flex items-center gap-2">
                <Switch
                    id={teamId + "-losers"}
                    checked={!!team.losers}
                    onCheckedChange={(checked) => api.teamInfo(scoreboardNumber, hdTeamId, {losers: checked}).catch(() => {})}
                />
                <Label htmlFor={teamId + "-losers"}>{i18n.t("losers_bracket")}</Label>
            </div>
            <div className="flex flex-col gap-3">
                {playerKeys.map((key) => (
                    <Player
                        key={`${teamId}-p-${key}`}
                        scoreboardNumber={scoreboardNumber}
                        hdTeamId={hdTeamId}
                        teamId={teamId}
                        teamKey={key}
                        player={team.player[key]}
                        defaultExpanded={playerKeys.length <= 2}
                    />
                ))}
            </div>
        </Card>
    );
}
