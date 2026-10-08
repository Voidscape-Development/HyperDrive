import React from "react";
import {
    Box,
    Chip,
    IconButton,
    Paper,
    Stack,
    ToggleButton,
    ToggleButtonGroup,
    Tooltip,
    Typography,
} from "@mui/material";
import {Add, Remove, RestartAlt, SwapHoriz} from "@mui/icons-material";
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
 * Between the teams, like on the desktop: the best of, a pip per game in
 * the color of the team that won it, and swapping teams or resetting the
 * score.
 */
function SetFormat({scoreboardNumber, score}) {
    const teams = score?.team ?? {};
    const bestOf = Number(score?.best_of) || 0;
    const games = Object.keys(score?.games ?? {})
        .sort((a, b) => Number(a) - Number(b))
        .map((k) => score.games[k]);
    const pipCount = Math.max(bestOf, games.length);
    const run = (call) => () => call(scoreboardNumber).catch(() => {});

    return (
        <Stack alignItems={"center"} gap={0.75} sx={{flexShrink: 0}}>
            <ToggleButtonGroup
                size={"small"}
                exclusive
                value={bestOf}
                onChange={(e, value) => api.setInfo(scoreboardNumber, {bestOf: value ?? 0}).catch(() => {})}
                aria-label={i18n.t("best_of", {value: ""}).trim()}
            >
                {[1, 3, 5, 7].map((value) => (
                    <ToggleButton key={value} value={value} sx={{px: 1, py: 0.25, fontWeight: 600}}>
                        BO{value}
                    </ToggleButton>
                ))}
            </ToggleButtonGroup>
            {pipCount > 0 && (
                <Stack direction={"row"} gap={0.5}>
                    {Array.from({length: pipCount}, (_, i) => {
                        const winner = games[i]?.winner;
                        const color = winner === 1 || winner === 2
                            ? (teams[String(winner)]?.color || 'text.secondary')
                            : null;
                        const label = winner === 1 || winner === 2
                            ? i18n.t("game_n_won", {value: i + 1, team: teamDisplayName(teams[String(winner)], winner)})
                            : i18n.t("game_n", {value: i + 1});
                        return (
                            <Tooltip key={i} title={label}>
                                <Box sx={{
                                    width: 14, height: 14, borderRadius: '3px',
                                    border: 1, borderColor: color ?? 'divider',
                                    bgcolor: color ?? 'action.hover',
                                }}/>
                            </Tooltip>
                        );
                    })}
                </Stack>
            )}
            <Stack direction={"row"} alignItems={"center"} gap={0.5}>
                {bestOf > 0 && (
                    <Typography variant={"caption"} color={"text.secondary"}>
                        {i18n.t("first_to", {value: Math.floor(bestOf / 2) + 1})}
                    </Typography>
                )}
                <Tooltip title={i18n.t("swap_teams")}>
                    <IconButton size={"small"} aria-label={i18n.t("swap_teams")} onClick={run(api.swapTeams)}>
                        <SwapHoriz fontSize={"small"}/>
                    </IconButton>
                </Tooltip>
                <Tooltip title={i18n.t("reset_score")}>
                    <IconButton size={"small"} aria-label={i18n.t("reset_score")} onClick={run(api.resetScores)}>
                        <RestartAlt fontSize={"small"}/>
                    </IconButton>
                </Tooltip>
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
    const details = [score?.phase, score?.match].filter(Boolean).join(" · ");

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
                <Box sx={{display: {xs: 'none', sm: 'block'}}}>
                    <SetFormat scoreboardNumber={scoreboardNumber} score={score}/>
                </Box>
                <TeamScore scoreboardNumber={scoreboardNumber} teamNumber={2} team={teams["2"]}
                           maxScore={maxScore} align={"right"}/>
            </Stack>
            {/* On phones it goes under the teams */}
            <Box sx={{display: {xs: 'block', sm: 'none'}, mt: 1}}>
                <SetFormat scoreboardNumber={scoreboardNumber} score={score}/>
            </Box>
        </Paper>
    );
}
