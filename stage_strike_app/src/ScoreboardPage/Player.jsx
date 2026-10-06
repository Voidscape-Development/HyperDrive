import React from "react";
import {
    Autocomplete,
    Avatar,
    Box,
    Card,
    CardHeader,
    Collapse,
    IconButton,
    Stack,
    Typography,
} from "@mui/material";
import TextField from './TextField';
import i18n from "../i18n/config";
import {ExpandMore} from "@mui/icons-material";
import {CharSelector} from "./CharSelector";
import {useSelector} from "react-redux";
import {CountrySelector} from "../CountrySelector";
import {CountryStateSelector} from "../CountryStateSelector";
import {api} from "./api";
import {saveOnCommit, useAutoSaveForm} from "./useAutoSaveForm";

/**
 * @typedef {{
 *    charIdx: string,
 *    charName: string,
 *    charSkin: string | number
 * }} CharacterSelection
 */

/**
 * @typedef {Record.<number, CharacterSelection>} CharacterSelections
 */

/**
 * @param {HDPlayerDbEntry} player
 * @param {string} gameCodename
 * @param {number} count
 * @return {CharacterSelections}
 */
function getMains(player, gameCodename, count) {
    const /** @type CharacterSelections */ rval = {};
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
                charSkin: main?.[1] !== undefined && main?.[1] !== "" ? String(main[1]) : "",
                charIdx: i + 1
            };
        }
    }

    return rval;
}

/**
 * @param {HDCharacterSelections} hdChars
 * @returns {CharacterSelections}
 */
function charsFromHd(hdChars) {
    const res = {};
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

/** @param {HDPlayerInfo} player */
const formFromPlayer = (player) => ({
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
 * One player of a team. Changes are sent to HyperDrive as they're made: text when
 * the field loses focus, Enter is pressed or typing stops for a moment, and
 * picks (a player from the database, a character, a country) right away.
 *
 * @param {Object} props
 * @param {number} props.scoreboardNumber
 * @param {string|number} props.hdTeamId
 * @param {string} props.teamId
 * @param {string} props.teamKey
 * @param {HDPlayerInfo} props.player
 * @param {boolean} props.defaultExpanded
 */
export default function Player({scoreboardNumber, hdTeamId, teamId, teamKey, player, defaultExpanded = true}) {
    const [expanded, setExpanded] = React.useState(defaultExpanded);

    const gameCodename = useSelector((s) => s.hdState.hdState?.game?.codename);
    /** @type HDPlayerDb */ const playerDb = useSelector((s) => s.hdPlayers.players);
    /** @type {HDCharacterDb} */ const characters = useSelector((s) => s.hdCharacters.characters);
    const playerOptions = React.useMemo(() => Object.values(playerDb ?? {}), [playerDb]);

    const playerId = `${teamId}-p-${teamKey}`;
    const idBase = `team-${teamId}-player-${playerId}-`;

    /** @returns {HDPlayerInfo} */
    const payload = (form) => {
        /*
         * The fields here are slightly off... The API sends the scoreboard out with the real name in the
         * player's "real_name" field and the tag in the "name" field. But on save it uses a slightly different
         * format where "name" is where the real name is stored and "gamerTag" holds the tag.
         */
        const rval = {
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
        const mains = [];
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

    const text = (field, label, props = {}) => (
        <TextField
            label={label}
            id={idBase + field}
            value={values[field]}
            onChange={(e) => setField(field, e.target.value)}
            {...saveOnCommit(flush)}
            {...props}
        />
    );

    /**
     * @param {React.SyntheticEvent} event
     * @param {HDPlayerDbEntry|string|null} picked
     */
    const onTagChanged = (event, picked) => {
        if (picked instanceof Object && picked.hasOwnProperty("gamerTag")) {
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
        } else {
            setField("name", picked ?? "", {immediate: true});
        }
    };

    const setCharacter = (charIdx, changes) => {
        setField("charSelections", {
            ...values.charSelections,
            [charIdx]: {...(values.charSelections[charIdx] ?? {charIdx}), ...changes},
        }, {immediate: true});
    };

    const onCharNameChanged = (charIdx, newChar) => {
        const skins = characters?.[newChar?.en_name]?.skins;
        setCharacter(charIdx, {
            charName: newChar?.en_name ?? newChar ?? "",
            charSkin: skins && Object.keys(skins).length > 0 ? "0" : "",
        });
    };

    const tag = values.team ? `${values.team} | ${values.name}` : values.name;
    const subtitle = [
        values.realName,
        Object.values(values.charSelections)
            .map((c) => characters?.[c.charName]?.display_name ?? c.charName)
            .filter(Boolean)
            .join(", "),
    ].filter(Boolean).join(" · ");
    const rowProps = {direction: {xs: 'column', sm: 'row'}, spacing: 2};

    return (
        <Card variant={"outlined"}>
            <CardHeader
                sx={{py: 1, cursor: 'pointer', '& .MuiCardHeader-content': {minWidth: 0}}}
                onClick={() => setExpanded(!expanded)}
                avatar={<Avatar
                    src={player?.online_avatar}
                    sx={{objectFit: "contain"}}
                    alt={i18n.t("avatar_for", {player: values.name})}
                >{values.name?.at(0) ?? "?"}</Avatar>}
                action={<IconButton
                    aria-label={i18n.t("expand_player")}
                    onClick={(e) => {
                        e.stopPropagation();
                        setExpanded(!expanded);
                    }}
                >
                    <ExpandMore sx={{transform: expanded ? 'rotate(0deg)' : 'rotate(270deg)'}}/>
                </IconButton>}
                title={<Typography noWrap sx={{fontWeight: 600}}>{tag || i18n.t("player_n", {value: teamKey})}</Typography>}
                subheader={subtitle ? <Typography variant={"body2"} color={"text.secondary"} noWrap>{subtitle}</Typography> : null}
            />
            <Collapse in={expanded} timeout={"auto"} unmountOnExit={false}>
                <Box sx={{px: 2, pb: 2, pt: 1}}>
                    <Stack spacing={2}>
                        <Stack {...rowProps}>
                            {text("team", i18n.t("sponsor"), {sx: {width: {xs: '100%', sm: '35%'}}})}
                            <Autocomplete
                                id={idBase + "tag"}
                                options={playerOptions}
                                value={values.name}
                                isOptionEqualToValue={(option, value) =>
                                    (option?.gamerTag ?? option) === (value?.gamerTag ?? value)}
                                getOptionLabel={(/** HDPlayerDbEntry|string */ p) => p?.prefixed_tag ?? p ?? ""}
                                freeSolo={true}
                                autoSelect={false}
                                sx={{flex: 1}}
                                onChange={onTagChanged}
                                onInputChange={(e, value, reason) => {
                                    if (reason === "input") {
                                        setField("name", value);
                                    }
                                }}
                                onBlur={flush}
                                renderInput={(params) => <TextField {...params} label={i18n.t("tag")}/>}
                            />
                        </Stack>

                        {text("realName", i18n.t("real_name"))}

                        <Stack {...rowProps}>
                            {text("twitter", i18n.t("twitter"), {sx: {flex: 1}})}
                            {text("pronoun", i18n.t("pronouns"), {sx: {flex: 1}})}
                        </Stack>

                        <Stack {...rowProps}>
                            <CountrySelector
                                sx={{flex: 1}}
                                label={i18n.t("country")}
                                value={values.countryCode}
                                onChange={(code) => {
                                    setField("countryCode", code ?? "");
                                    setField("stateCode", "", {immediate: true});
                                }}
                            />
                            <CountryStateSelector
                                countryCode={values.countryCode}
                                sx={{flex: 1}}
                                label={i18n.t("state")}
                                value={values.stateCode}
                                onChange={(code) => setField("stateCode", code ?? "", {immediate: true})}
                            />
                        </Stack>

                        {Object.values(values.charSelections).map((cs) =>
                            <CharSelector
                                key={`${playerId}-cs-${cs.charIdx}`}
                                id={`${playerId}-cs-${cs.charIdx}`}
                                charName={cs.charName}
                                charSkin={cs.charSkin}
                                onCharNameChanged={(ev, val) => onCharNameChanged(cs.charIdx, val)}
                                onCharSkinChanged={(ev) => setCharacter(cs.charIdx, {charSkin: ev.target.value})}
                                stackProps={{direction: 'row', spacing: 2}}
                            />
                        )}
                    </Stack>
                </Box>
            </Collapse>
        </Card>
    );
}
