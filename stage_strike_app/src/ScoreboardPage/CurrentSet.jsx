import React from "react";
import {
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogContentText,
    DialogTitle,
    Stack,
    Typography,
} from "@mui/material";
import {Grid} from "@mui/system";
import {DeleteSweep, LiveTv, RestartAlt, SwapHoriz} from "@mui/icons-material";
import {useSelector} from "react-redux";
import i18n from "../i18n/config";

import ScoreBar from "./ScoreBar";
import MatchInfo from "./MatchInfo";
import Team from "./Team";
import {api} from "./api";

/** Buttons for the things done between and during sets. */
function QuickActions({scoreboardNumber}) {
    const [confirmClear, setConfirmClear] = React.useState(false);
    const run = (call) => () => call(scoreboardNumber).catch(() => {});

    return (
        <>
            <Stack direction={"row"} gap={1} flexWrap={"wrap"} justifyContent={"center"}>
                <Button variant={"outlined"} startIcon={<SwapHoriz/>} onClick={run(api.swapTeams)}>
                    {i18n.t("swap_teams")}
                </Button>
                <Button variant={"outlined"} startIcon={<RestartAlt/>} onClick={run(api.resetScores)}>
                    {i18n.t("reset_score")}
                </Button>
                <Button variant={"outlined"} startIcon={<LiveTv/>} onClick={run(api.pullStreamSet)}>
                    {i18n.t("load_stream_set")}
                </Button>
                <Button variant={"outlined"} color={"error"} startIcon={<DeleteSweep/>} onClick={() => setConfirmClear(true)}>
                    {i18n.t("clear_scoreboard")}
                </Button>
            </Stack>

            <Dialog open={confirmClear} onClose={() => setConfirmClear(false)}>
                <DialogTitle>{i18n.t("clear_scoreboard")}</DialogTitle>
                <DialogContent>
                    <DialogContentText>{i18n.t("clear_scoreboard_confirm")}</DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setConfirmClear(false)}>{i18n.t("cancel")}</Button>
                    <Button color={"error"} onClick={() => {
                        setConfirmClear(false);
                        api.clearAll(scoreboardNumber).catch(() => {});
                    }}>
                        {i18n.t("clear")}
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    );
}

/**
 * The scoreboard being controlled: the score (kept at the top while
 * scrolling), quick actions, the set's details and both teams.
 */
export default function CurrentSet({scoreboardNumber}) {
    /** @type {TSHScoreInfo} */
    const score = useSelector((state) => state.tshState.tshState?.score?.[scoreboardNumber]);

    const hasTeams = !!score?.team && Object.keys(score.team).length >= 2;
    if (!hasTeams) {
        return <Typography variant={"h6"} sx={{p: 2}}>{i18n.t("no_set")}</Typography>;
    }

    return (
        <Stack gap={2}>
            <ScoreBar scoreboardNumber={scoreboardNumber} score={score}/>
            <QuickActions scoreboardNumber={scoreboardNumber}/>
            <MatchInfo scoreboardNumber={scoreboardNumber} score={score}/>
            <Grid container spacing={2}>
                {["1", "2"].map((teamKey) => (
                    <Grid key={teamKey} size={{xs: 12, md: 6}}>
                        <Team
                            key={`s-${scoreboardNumber}-t-${teamKey}`}
                            scoreboardNumber={scoreboardNumber}
                            tshTeamId={teamKey}
                            team={score.team[teamKey]}
                        />
                    </Grid>
                ))}
            </Grid>
        </Stack>
    );
}
