import React from "react";
import {Box, FormControlLabel, Paper, Stack, Switch, Tooltip} from "@mui/material";
import i18n from "../i18n/config";
import Player from "./Player";
import TextField from "./TextField";
import {api} from "./api";
import {saveOnCommit, useAutoSaveForm} from "./useAutoSaveForm";

// <input type="color"> only takes #rrggbb
const hexColor = (color) => (/^#[0-9a-f]{6}/i.test(color ?? "") ? color.slice(0, 7) : "#000000");

/**
 * A team: its name, color and losers state, and its players. Everything
 * saves as it's edited.
 *
 * @param {Object} props
 * @param {number} props.scoreboardNumber
 * @param {string|number} props.tshTeamId 1 for the left side, 2 for the right
 * @param {TSHTeamInfo} props.team
 */
export default function Team({scoreboardNumber, tshTeamId, team}) {
    const {values, setField, flush} = useAutoSaveForm(
        {name: team.teamName ?? "", color: hexColor(team.color)},
        (v, changed) => api.teamInfo(scoreboardNumber, tshTeamId,
            Object.fromEntries(changed.map((k) => [k, v[k]]))),
        900,
    );

    const playerKeys = Object.keys(team.player ?? {}).sort((a, b) => Number(a) - Number(b));
    const teamId = `s-${scoreboardNumber}-t-${tshTeamId}`;

    return (
        <Paper elevation={3} sx={{borderTop: `solid 4px ${team.color || 'transparent'}`, overflow: 'hidden'}}>
            <Stack gap={1.5} padding={1.5}>
                <Stack direction={"row"} gap={1.5} alignItems={"center"}>
                    <Tooltip title={i18n.t("team_color")}>
                        <Box
                            component={"input"}
                            type={"color"}
                            aria-label={i18n.t("team_color")}
                            value={values.color}
                            onChange={(e) => setField("color", e.target.value)}
                            sx={{
                                width: 44, height: 44, p: 0, border: 0, borderRadius: 1,
                                background: 'none', cursor: 'pointer', flexShrink: 0,
                            }}
                        />
                    </Tooltip>
                    <TextField
                        fullWidth
                        size={"small"}
                        label={i18n.t("team_name")}
                        placeholder={i18n.t("team_name_placeholder")}
                        value={values.name}
                        onChange={(e) => setField("name", e.target.value)}
                        {...saveOnCommit(flush)}
                    />
                </Stack>
                <FormControlLabel
                    control={
                        <Switch
                            checked={!!team.losers}
                            onChange={(e) => api.teamInfo(scoreboardNumber, tshTeamId, {losers: e.target.checked}).catch(() => {})}
                        />
                    }
                    label={i18n.t("losers_bracket")}
                />
                <Stack gap={1.5}>
                    {playerKeys.map((key) => (
                        <Player
                            key={`${teamId}-p-${key}`}
                            scoreboardNumber={scoreboardNumber}
                            tshTeamId={tshTeamId}
                            teamId={teamId}
                            teamKey={key}
                            player={team.player[key]}
                            defaultExpanded={playerKeys.length <= 2}
                        />
                    ))}
                </Stack>
            </Stack>
        </Paper>
    );
}
