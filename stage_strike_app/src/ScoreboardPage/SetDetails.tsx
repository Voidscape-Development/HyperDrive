import i18n from "../i18n/config";
import {NumberInput} from "../NumberInput";
import {api} from "./api";
import {saveOnCommit, useAutoSaveForm} from "./useAutoSaveForm";
import type {HDScoreInfo} from "../backendDataTypes";
import {Field} from "@/components/Field";
import {Card, CardContent} from "@/components/ui/card";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {cn} from "@/lib/utils";

const countOf = (obj: object) => Object.keys(obj ?? {}).length;

interface SegmentedProps {
    id: string;
    label: string;
    options: {value: number; label: string}[];
    value: number;
    onChange: (value: number) => void;
}

/** A few choices side by side, one picked */
function Segmented({id, label, options, value, onChange}: SegmentedProps) {
    // A value set elsewhere that isn't one of the choices still shows, picked
    const all = options.some((o) => o.value === value) ? options : [...options, {value, label: String(value)}];
    return (
        <div className="flex flex-col gap-1.5">
            <Label id={id} className="text-xs text-muted-foreground">{label}</Label>
            <div role="radiogroup" aria-labelledby={id} className="flex w-fit rounded-lg bg-muted p-[3px]">
                {all.map((o) => (
                    <button
                        key={o.value}
                        type="button"
                        role="radio"
                        aria-checked={o.value === value}
                        onClick={() => onChange(o.value)}
                        className={cn(
                            "h-9 min-w-10 cursor-pointer rounded-md px-2.5 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                            o.value === value
                                ? "bg-primary font-semibold text-primary-foreground"
                                : "text-muted-foreground hover:text-foreground",
                        )}
                    >
                        {o.label}
                    </button>
                ))}
            </div>
        </div>
    );
}

/**
 * The set's phase, match and best of, and how many players and characters
 * the scoreboard has. Saves as it's edited.
 */
export default function SetDetails({scoreboardNumber, score}: {scoreboardNumber: number; score: HDScoreInfo}) {
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

    return (
        <Card className="py-4">
            <CardContent className="flex flex-col gap-4 px-4">
                <h2 className="sr-only">{i18n.t("set_details")}</h2>
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
                <div className="flex flex-wrap items-end gap-x-6 gap-y-4">
                    <Segmented
                        id={idBase + "bestOf"}
                        label={i18n.t("best_of", {value: ""}).trim()}
                        options={[
                            {value: 0, label: i18n.t("no_best_of")},
                            ...[1, 3, 5, 7].map((n) => ({value: n, label: String(n)})),
                        ]}
                        value={values.bestOf}
                        onChange={(v) => setField("bestOf", v, {immediate: true})}
                    />
                    <Segmented
                        id={idBase + "players"}
                        label={i18n.t("players_per_team")}
                        options={[1, 2, 3, 4].map((n) => ({value: n, label: String(n)}))}
                        value={values.players}
                        onChange={(v) => setField("players", v, {immediate: true})}
                    />
                    <Field label={i18n.t("characters_per_player")} htmlFor={idBase + "characters"}>
                        <NumberInput
                            id={idBase + "characters"}
                            value={values.characters}
                            min={0}
                            onChange={(_, value) => {
                                if (!Number.isNaN(value)) {
                                    setField("characters", Math.max(0, value));
                                }
                            }}
                        />
                    </Field>
                </div>
            </CardContent>
        </Card>
    );
}
