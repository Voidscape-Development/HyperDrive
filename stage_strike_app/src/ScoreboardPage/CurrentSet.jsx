import React from "react";
import {Stack, Typography} from "@mui/material";
import {Grid} from "@mui/system";
import {useSelector} from "react-redux";
import i18n from "../i18n/config";

import ScoreBar from "./ScoreBar";
import MatchInfo from "./MatchInfo";
import SourceBar from "./SourceBar";
import Team from "./Team";

/**
 * The scoreboard being controlled, in the desktop scoreboard's order: where
 * the set comes from, the score (kept at the top while scrolling), the
 * phase and match, then both teams.
 */
export default function CurrentSet({scoreboardNumber}) {
    /** @type {HDScoreInfo} */
    const score = useSelector((state) => state.hdState.hdState?.score?.[scoreboardNumber]);

    const hasTeams = !!score?.team && Object.keys(score.team).length >= 2;
    if (!hasTeams) {
        return <Typography variant={"h6"} sx={{p: 2}}>{i18n.t("no_set")}</Typography>;
    }

    return (
        <Stack gap={2}>
            <SourceBar scoreboardNumber={scoreboardNumber} score={score}/>
            <ScoreBar scoreboardNumber={scoreboardNumber} score={score}/>
            <MatchInfo scoreboardNumber={scoreboardNumber} score={score}/>
            <Grid container spacing={2}>
                {["1", "2"].map((teamKey) => (
                    <Grid key={teamKey} size={{xs: 12, md: 6}}>
                        <Team
                            key={`s-${scoreboardNumber}-t-${teamKey}`}
                            scoreboardNumber={scoreboardNumber}
                            hdTeamId={teamKey}
                            team={score.team[teamKey]}
                        />
                    </Grid>
                ))}
            </Grid>
        </Stack>
    );
}
