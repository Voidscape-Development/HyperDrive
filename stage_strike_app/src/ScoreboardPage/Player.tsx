import React from "react";
import {ChevronDown} from "lucide-react";
import {useSelector} from "react-redux";
import i18n from "../i18n/config";
import {CharSelector} from "./CharSelector";
import {CountrySelector} from "../CountrySelector";
import {CountryStateSelector} from "../CountryStateSelector";
import {api} from "./api";
import {saveOnCommit, useAutoSaveForm} from "./useAutoSaveForm";
import type {ReduxState} from "../redux/store";
import type {
    HDCharacterDbEntry,
    HDCharacterSelections,
    HDMain,
    HDPlayerDbEntry,
    HDPlayerInfo,
} from "../backendDataTypes";
import {Autocomplete} from "@/components/Autocomplete";
import {Field} from "@/components/Field";
import {Avatar, AvatarFallback, AvatarImage} from "@/components/ui/avatar";
import {Collapsible, CollapsibleContent, CollapsibleTrigger} from "@/components/ui/collapsible";
import {Input} from "@/components/ui/input";
import {cn} from "@/lib/utils";

interface CharacterSelection {
    charIdx: string | number;
    charName: string;
    // The skin picker's values are strings, "" for none
    charSkin: string;
}

type CharacterSelections = Record<number, CharacterSelection>;

function getMains(player: HDPlayerDbEntry, gameCodename: string, count: number): CharacterSelections {
    const rval: CharacterSelections = {};
    // Yeah, we do 1-based counting here.
    for (let i = 1; i < count + 1; i += 1) {
        rval[i] = {
            charName: "",
            charSkin: "",
            charIdx: i
        };
    }

    const mains = player.mains?.[gameCodename];
    if (mains) {
        for (let i = 0; i < count && i < mains.length; i += 1) {
            const main = mains[i];
            rval[i + 1] = {
                charName: main?.[0] ?? "",
                charSkin: String(main?.[1] ?? ""),
                charIdx: i + 1
            };
        }
    }

    return rval;
}

function charsFromHd(hdChars: HDCharacterSelections): CharacterSelections {
    const res: CharacterSelections = {};
    for (const i in hdChars) {
        res[i] = {
            charIdx: i,
            charName: hdChars[i].en_name ?? "",
            // The skin picker's values are strings; HyperDrive uses -1 for no skin
            charSkin: hdChars[i].skin >= 0 ? String(hdChars[i].skin) : "",
        };
    }
    return res;
}

const formFromPlayer = (player: HDPlayerInfo) => ({
    countryCode: player.country?.code ?? "",
    stateCode: player.state?.code ?? "",
    team: player.team ?? "",
    name: player.name ?? "",
    realName: player.real_name ?? "",
    twitter: player.twitter ?? "",
    pronoun: player.pronoun ?? "",
    charSelections: charsFromHd(player.character),
});

/**
 * One player of a team: what's shown on stream first (tag, sponsor, characters),
 * the rest folded under "More details". Changes are sent to HyperDrive as they're made: text when
 * the field loses focus, Enter is pressed or typing stops for a moment, and
 * picks (a player from the database, a character, a country) right away.
 */
export default function Player({scoreboardNumber, hdTeamId, teamId, teamKey, player, showHeading}: {
    scoreboardNumber: number;
    hdTeamId: string;
    teamId: string;
    teamKey: string;
    player: HDPlayerInfo;
    // With more than one player on the team, each gets a heading
    showHeading: boolean;
}) {
    const [detailsOpen, setDetailsOpen] = React.useState(false);

    const gameCodename = useSelector((s: ReduxState) => s.hdState.hdState?.game?.codename);
    const playerDb = useSelector((s: ReduxState) => s.hdPlayers.players);
    const characters = useSelector((s: ReduxState) => s.hdCharacters.characters);
    const playerOptions = React.useMemo(() => Object.values(playerDb ?? {}), [playerDb]);

    const playerId = `${teamId}-p-${teamKey}`;
    const idBase = `team-${teamId}-player-${playerId}-`;

    const payload = (form: ReturnType<typeof formFromPlayer>) => {
        /*
         * The fields here are slightly off... The API sends the scoreboard out with the real name in the
         * player's "real_name" field and the tag in the "name" field. But on save it uses a slightly different
         * format where "name" is where the real name is stored and "gamerTag" holds the tag.
         */
        const rval: Record<string, unknown> = {
            country_code: form.countryCode,
            state_code: form.stateCode,
            prefix: form.team,
            gamerTag: form.name,
            name: form.realName,
            twitter: form.twitter,
            pronoun: form.pronoun,
        };

        /*
         * Sending characters also updates the player's mains in the player DB. So that mains aren't
         * overwritten with nothing, slots without a character keep the player's existing mains.
         */
        const lookupName = form.team ? `${form.team} ${form.name}` : form.name;
        const existingMains = Object.values(playerDb?.[lookupName]?.mains?.[gameCodename] ?? []);
        const charsFromForm = Object.values(form.charSelections);
        const mains: HDMain[] = [];
        for (let i = 0; i < charsFromForm.length; i += 1) {
            if (charsFromForm[i].charName) {
                mains.push([
                    characters?.[charsFromForm[i].charName]?.en_name ?? charsFromForm[i].charName,
                    Number(charsFromForm[i].charSkin) || 0,
                    ""
                ]);
            } else if (i < existingMains.length) {
                mains.push(existingMains[i]);
            } else {
                mains.push(["", 0, ""]);
            }
        }
        rval.mains = {[gameCodename]: mains};

        // Don't persist player info to DB if they have no tag.
        rval.savePlayerToDb = !!form.name;
        return rval;
    };

    const {values, setField, flush} = useAutoSaveForm(
        formFromPlayer(player),
        (form) => api.updatePlayer(scoreboardNumber, hdTeamId, teamKey, payload(form)),
    );

    const text = (field: "team" | "realName" | "twitter" | "pronoun", label: string) => (
        <Field label={label} htmlFor={idBase + field}>
            <Input
                id={idBase + field}
                value={values[field]}
                onChange={(e) => setField(field, e.target.value)}
                {...saveOnCommit(flush)}
            />
        </Field>
    );

    const onTagChanged = (picked: HDPlayerDbEntry | null) => {
        if (!picked) {
            return;
        }
        // A player from the database fills in everything they have
        const count = Object.keys(values.charSelections).length;
        setField("countryCode", picked.country_code ?? "");
        setField("stateCode", picked.state_code ?? "");
        setField("team", picked.prefix ?? "");
        setField("realName", picked.name ?? "");
        setField("twitter", picked.twitter ?? "");
        setField("pronoun", picked.pronoun ?? "");
        setField("charSelections", getMains(picked, gameCodename, count));
        setField("name", picked.gamerTag, {immediate: true});
    };

    const heading = (values.team ? `${values.team} | ${values.name}` : values.name) || i18n.t("player_n", {value: teamKey});
    // What's in "More details", so it shows without opening it
    const details = [values.realName, values.twitter, values.countryCode].filter(Boolean).join(" · ");

    const setCharacter = (charIdx: string | number, changes: Partial<CharacterSelection>) => {
        setField("charSelections", {
            ...values.charSelections,
            [charIdx]: {...(values.charSelections[charIdx] ?? {charIdx}), ...changes},
        }, {immediate: true});
    };

    const onCharNameChanged = (charIdx: string | number, newChar: HDCharacterDbEntry | null) => {
        const skins = characters?.[newChar?.en_name]?.skins;
        setCharacter(charIdx, {
            charName: newChar?.en_name ?? "",
            charSkin: skins && Object.keys(skins).length > 0 ? "0" : "",
        });
    };

    const lookupName = values.team ? `${values.team} ${values.name}` : values.name;
    const mains = Object.values(playerDb?.[lookupName]?.mains?.[gameCodename] ?? [])
        .map((m) => m?.[0])
        .filter(Boolean);
    const charSlots = Object.values(values.charSelections);
    const row = "grid grid-cols-1 gap-4 sm:grid-cols-2";

    return (
        <section aria-label={heading} className="flex flex-col gap-4">
            {showHeading && (
                <div className="flex items-center gap-3">
                    <Avatar className="size-9">
                        <AvatarImage
                            src={player?.online_avatar}
                            className="object-contain"
                            alt={i18n.t("avatar_for", {player: values.name})}
                        />
                        <AvatarFallback>{values.name?.at(0) ?? "?"}</AvatarFallback>
                    </Avatar>
                    <h3 className="min-w-0 truncate font-semibold">{heading}</h3>
                </div>
            )}

            <Field label={i18n.t("tag")} htmlFor={idBase + "tag"}>
                <Autocomplete
                    id={idBase + "tag"}
                    freeSolo
                    options={playerOptions}
                    value={null}
                    inputValue={values.name}
                    getLabel={(p) => p?.prefixed_tag ?? ""}
                    getKey={(p) => p.prefixed_tag}
                    renderOption={(p) => {
                        const chars = (p.mains?.[gameCodename] ?? [])
                            .map((m) => characters?.[m?.[0]]?.display_name ?? m?.[0])
                            .filter(Boolean)
                            .join(", ");
                        return <span className="flex min-w-0 flex-col">
                            <span className="truncate font-medium">{p.prefixed_tag}</span>
                            {chars && <span className="truncate text-xs text-muted-foreground">{chars}</span>}
                        </span>;
                    }}
                    minChars={1}
                    limit={20}
                    onSelect={onTagChanged}
                    onInputChange={(value) => setField("name", value)}
                    onBlur={flush}
                    onKeyDown={saveOnCommit(flush).onKeyDown}
                />
            </Field>

            <div className="grid grid-cols-2 gap-4">
                {text("team", i18n.t("sponsor"))}
                {text("pronoun", i18n.t("pronouns"))}
            </div>

            {charSlots.map((cs, i) =>
                <CharSelector
                    key={`${playerId}-cs-${cs.charIdx}`}
                    id={`${playerId}-cs-${cs.charIdx}`}
                    label={charSlots.length > 1 ? i18n.t("character_n", {value: i + 1}) : i18n.t("character")}
                    charName={cs.charName}
                    charSkin={cs.charSkin}
                    mains={mains}
                    onCharNameChanged={(val) => onCharNameChanged(cs.charIdx, val)}
                    onCharSkinChanged={(skin) => setCharacter(cs.charIdx, {charSkin: skin})}
                />
            )}

            <Collapsible open={detailsOpen} onOpenChange={setDetailsOpen}>
                <CollapsibleTrigger asChild>
                    <button
                        type="button"
                        className="flex min-h-14 w-full cursor-pointer items-center gap-3 rounded-xl border px-3.5 text-left outline-none hover:bg-accent/40 focus-visible:ring-[3px] focus-visible:ring-ring/50"
                    >
                        <span className="min-w-0 flex-1">
                            <span className="block text-sm font-semibold">{i18n.t("more_details")}</span>
                            <span className="block truncate text-xs text-muted-foreground">
                                {details || i18n.t("more_details_hint")}
                            </span>
                        </span>
                        <ChevronDown className={cn("size-5 shrink-0 text-muted-foreground transition-transform", detailsOpen && "rotate-180")}/>
                    </button>
                </CollapsibleTrigger>
                <CollapsibleContent className="flex flex-col gap-4 pt-4">
                    {text("realName", i18n.t("real_name"))}
                    {text("twitter", i18n.t("twitter"))}
                    <div className={row}>
                        <Field label={i18n.t("country")} htmlFor={idBase + "country"}>
                            <CountrySelector
                                id={idBase + "country"}
                                value={values.countryCode}
                                onChange={(code) => {
                                    setField("countryCode", code ?? "");
                                    setField("stateCode", "", {immediate: true});
                                }}
                            />
                        </Field>
                        <Field label={i18n.t("state")} htmlFor={idBase + "state"}>
                            <CountryStateSelector
                                id={idBase + "state"}
                                countryCode={values.countryCode}
                                value={values.stateCode}
                                onChange={(code) => setField("stateCode", code ?? "", {immediate: true})}
                            />
                        </Field>
                    </div>
                </CollapsibleContent>
            </Collapsible>
        </section>
    );
}
