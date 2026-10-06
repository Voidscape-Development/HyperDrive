import React from "react";
import {Box, Chip, IconButton, Paper, Stack, Typography} from "@mui/material";
import {Add, Remove} from "@mui/icons-material";
import i18n from "../i18n/config";
import {api} from "./api";

/** The name shown for a team: its team name, or else its players' tags. */
export function teamDisplayName(team, teamNumber) {
    if (team?.teamName) {
        return team.teamName;
    }
    const tags = Object.keys(team?.player ?? {})
        .sort()
        .map((k) => team.player[k]?.name)
        .filter(Boolean);
    return tags.length > 0 ? tags.join(" / ") : i18n.t("team_n", {value: teamNumber});
}

/**
 * One side of the score bar: the team's name and losers state, and its
 * score with buttons that change it right away.
 */
function TeamScore({scoreboardNumber, teamNumber, team, maxScore, align}) {
    const score = Number(team?.score ?? 0);
    const color = team?.color || 'transparent';
    const left = align === 'left';

    return (
        <Stack
            // On phones the name goes above the score so it has the width to show
            direction={{xs: 'column', sm: left ? "row" : "row-reverse"}}
            alignItems={{xs: left ? "flex-start" : "flex-end", sm: "center"}}
            gap={{xs: 0.5, sm: 1.5}}
            sx={{
                flex: 1,
                minWidth: 0,
                [left ? 'borderLeft' : 'borderRight']: `6px solid ${color}`,
                [left ? 'pl' : 'pr']: {xs: 1, sm: 2},
            }}
        >
            <Stack
                direction={{xs: left ? 'row' : 'row-reverse', sm: 'column'}}
                sx={{flex: 1, minWidth: 0, maxWidth: '100%'}}
                alignItems={{xs: 'center', sm: left ? "flex-start" : "flex-end"}}
                gap={0.5}
            >
                <Typography
                    variant={"subtitle1"}
                    noWrap
                    title={teamDisplayName(team, teamNumber)}
                    sx={{fontWeight: 600, minWidth: 0, lineHeight: 1.2}}
                >
                    {teamDisplayName(team, teamNumber)}
                </Typography>
                <Chip
                    size={"small"}
                    label={"[L]"}
                    title={i18n.t("losers_bracket")}
                    color={team?.losers ? "warning" : "default"}
                    variant={team?.losers ? "filled" : "outlined"}
                    onClick={() => api.teamInfo(scoreboardNumber, teamNumber, {losers: !team?.losers}).catch(() => {})}
                    sx={{height: 22, fontWeight: 700, flexShrink: 0}}
                />
            </Stack>

            <Stack direction={left ? "row" : "row-reverse"} alignItems={"center"} gap={{xs: 0, sm: 0.5}}>
                <IconButton
                    aria-label={i18n.t("score_down", {value: teamNumber})}
                    disabled={score <= 0}
                    onClick={() => api.scoreDown(scoreboardNumber, teamNumber).catch(() => {})}
                    sx={{border: 1, borderColor: 'divider', width: {xs: 40, sm: 48}, height: {xs: 40, sm: 48}}}
                >
                    <Remove/>
                </IconButton>
                <Typography
                    component={"span"}
                    sx={{
                        fontSize: {xs: '2.25rem', sm: '3rem'},
                        fontWeight: 700,
                        minWidth: {xs: '1.6ch', sm: '2ch'},
                        textAlign: 'center',
                        fontVariantNumeric: 'tabular-nums',
                        lineHeight: 1,
                    }}
                >
                    {score}
                </Typography>
                <IconButton
                    aria-label={i18n.t("score_up", {value: teamNumber})}
                    color={"primary"}
                    disabled={maxScore !== null && score >= maxScore}
                    onClick={() => api.scoreUp(scoreboardNumber, teamNumber).catch(() => {})}
                    sx={{border: 1, borderColor: 'primary.main', width: {xs: 40, sm: 48}, height: {xs: 40, sm: 48}}}
                >
                    <Add/>
                </IconButton>
            </Stack>
        </Stack>
    );
}

/**
 * The current score, kept at the top of the page. Teams are shown as they
 * are on the scoreboard: team 1 on the left.
 */
export default function ScoreBar({scoreboardNumber, score}) {
    const teams = score?.team ?? {};
    const bestOf = Number(score?.best_of) || 0;
    const maxScore = bestOf > 0 ? Math.floor(bestOf / 2) + 1 : null;
    const details = [
        score?.phase,
        score?.match,
        bestOf > 0 ? i18n.t("best_of", {value: bestOf}) : null,
    ].filter(Boolean).join(" · ");

    return (
        <Paper
            elevation={6}
            sx={{
                position: 'sticky',
                top: 0,
                zIndex: (theme) => theme.zIndex.appBar,
                px: {xs: 1, sm: 2},
                py: 1,
            }}
        >
            {details && (
                <Typography
                    variant={"caption"}
                    color={"text.secondary"}
                    component={"div"}
                    noWrap
                    sx={{textAlign: 'center', mb: 0.5}}
                >
                    {details}
                </Typography>
            )}
            <Stack direction={"row"} alignItems={"center"} gap={{xs: 1, sm: 3}}>
                <TeamScore scoreboardNumber={scoreboardNumber} teamNumber={1} team={teams["1"]}
                           maxScore={maxScore} align={"left"}/>
                <Box sx={{color: 'text.disabled', fontWeight: 700, display: {xs: 'none', sm: 'block'}}}>–</Box>
                <TeamScore scoreboardNumber={scoreboardNumber} teamNumber={2} team={teams["2"]}
                           maxScore={maxScore} align={"right"}/>
            </Stack>
        </Paper>
    );
}
