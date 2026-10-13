import i18n from "../i18n/config";
import {NumberInput} from "../NumberInput";
import {api} from "./api";
import {saveOnCommit, useAutoSaveForm} from "./useAutoSaveForm";
import type {HDScoreInfo} from "../backendDataTypes";
import {Field} from "@/components/Field";
import {Card, CardContent} from "@/components/ui/card";
import {Input} from "@/components/ui/input";

const countOf = (obj: object) => Object.keys(obj ?? {}).length;

/**
 * The set's phase, match and best of, and how many players and characters
 * the scoreboard has. Saves as it's edited.
 */
export default function MatchInfo({scoreboardNumber, score}: {scoreboardNumber: number; score: HDScoreInfo}) {
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

    const idBase = `s-${scoreboardNumber}-info-`;
    const number = (key: "bestOf" | "players" | "characters", label: string, min: number) => (
        <Field label={label} htmlFor={idBase + key} className="items-center">
            <NumberInput
                id={idBase + key}
                value={values[key]}
                min={min}
                onChange={(_, value) => {
                    if (!Number.isNaN(value)) {
                        setField(key, Math.max(min, value));
                    }
                }}
            />
        </Field>
    );

    return (
        <Card className="py-4">
            <CardContent className="flex flex-col gap-4 px-4">
                <div className="flex flex-col gap-4 sm:flex-row">
                    <Field label={i18n.t("phase")} htmlFor={idBase + "phase"} className="flex-1">
                        <Input
                            id={idBase + "phase"}
                            value={values.phase}
                            onChange={(e) => setField("phase", e.target.value)}
                            {...saveOnCommit(flush)}
                        />
                    </Field>
                    <Field label={i18n.t("match")} htmlFor={idBase + "match"} className="flex-1">
                        <Input
                            id={idBase + "match"}
                            value={values.match}
                            onChange={(e) => setField("match", e.target.value)}
                            {...saveOnCommit(flush)}
                        />
                    </Field>
                </div>
                <div className="flex flex-wrap justify-around gap-4">
                    {number("bestOf", i18n.t("best_of", {value: ""}).trim(), 0)}
                    {number("players", i18n.t("players_per_team"), 1)}
                    {number("characters", i18n.t("characters_per_player"), 0)}
                </div>
            </CardContent>
        </Card>
    );
}
