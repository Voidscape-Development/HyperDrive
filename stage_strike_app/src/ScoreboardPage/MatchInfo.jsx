import React from "react";
import {Card, CardContent, Stack, Typography} from "@mui/material";
import i18n from "../i18n/config";
import TextField from "./TextField";
import {NumberInput} from "../NumberInput";
import {api} from "./api";
import {saveOnCommit, useAutoSaveForm} from "./useAutoSaveForm";

const countOf = (obj) => Object.keys(obj ?? {}).length;

/**
 * The set's phase, match and best of, and how many players and characters
 * the scoreboard has. Saves as it's edited.
 */
export default function MatchInfo({scoreboardNumber, score}) {
    const teams = Object.values(score?.team ?? {});
    const playersPerTeam = Math.max(1, ...teams.map((t) => countOf(t?.player)));
    const firstPlayer = Object.values(teams[0]?.player ?? {})[0];
    const charactersPerPlayer = countOf(firstPlayer?.character);

    const server = {
        phase: score?.phase ?? "",
        match: score?.match ?? "",
        bestOf: Number(score?.best_of) || 0,
        players: playersPerTeam,
        characters: charactersPerPlayer,
    };

    const {values, setField, flush} = useAutoSaveForm(
        server,
        (v, changed) => api.setInfo(scoreboardNumber, Object.fromEntries(changed.map((k) => [k, v[k]]))),
        800,
    );

    const number = (key, label, min) => (
        <Stack gap={0.5} alignItems={"center"}>
            <Typography variant={"caption"} color={"text.secondary"}>{label}</Typography>
            <NumberInput
                value={values[key]}
                min={min}
                wingWidth={40}
                width={150}
                onChange={(_, value) => {
                    if (!Number.isNaN(value)) {
                        setField(key, Math.max(min, value));
                    }
                }}
            />
        </Stack>
    );

    return (
        <Card>
            <CardContent>
                <Stack gap={2}>
                    <Stack direction={{xs: 'column', sm: 'row'}} gap={2}>
                        <TextField
                            fullWidth
                            label={i18n.t("phase")}
                            value={values.phase}
                            onChange={(e) => setField("phase", e.target.value)}
                            {...saveOnCommit(flush)}
                        />
                        <TextField
                            fullWidth
                            label={i18n.t("match")}
                            value={values.match}
                            onChange={(e) => setField("match", e.target.value)}
                            {...saveOnCommit(flush)}
                        />
                    </Stack>
                    <Stack direction={"row"} gap={2} flexWrap={"wrap"} justifyContent={"space-around"}>
                        {number("bestOf", i18n.t("best_of", {value: ""}).trim(), 0)}
                        {number("players", i18n.t("players_per_team"), 1)}
                        {number("characters", i18n.t("characters_per_player"), 0)}
                    </Stack>
                </Stack>
            </CardContent>
        </Card>
    );
}
