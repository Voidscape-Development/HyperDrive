import {useEffect, useState} from "react";
import {shallowEqual, useSelector} from "react-redux";
import i18n from "../i18n/config";
import {BASE_URL} from "../env";
import type {ReduxState} from "../redux/store";
import type {HDCharacterDb, HDCountryDb, HDPlayerDb, HDPlayerDbEntry} from "../backendDataTypes";
import type {CharacterMap, CharacterRef, Person, PreviewResponse, QueueSet} from "./types";
import {PlayerIdentity, PlayerNotes} from "./PlayerCard";
import {HeadToHead, LastSets, PastEvents} from "./Stats";
import {etaText, teamName, teamPlayers} from "./util";
import {Badge} from "@/components/ui/badge";
import {Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle} from "@/components/ui/dialog";

/** A player as the stream queue has them, with what the player database adds */
function withDatabase(
    player: Person,
    db: HDPlayerDbEntry | undefined,
    gameCodename: string | undefined,
    characters: HDCharacterDb,
    countries: HDCountryDb,
): Person {
    // The stream queue's countries may only have their code
    if (player.country?.code && !player.country.name) {
        player = {...player, country: {...countries[player.country.code], ...player.country}};
    }
    if (!db) return player;
    const mains: CharacterMap = {};
    for (const [i, main] of (db.mains?.[gameCodename ?? ""] ?? []).entries()) {
        const character = characters[main?.[0]];
        if (character) {
            const assets = character.skins?.[main[1] ?? 0]?.assets ?? character.skins?.[0]?.assets;
            mains[String(i + 1)] = {...character, assets: assets as CharacterRef["assets"]};
        }
    }
    const country = db.country_code ? {...countries[db.country_code], code: db.country_code} : undefined;
    const state = db.state_code ? (countries[db.country_code ?? ""] as {states?: Record<string, {name?: string}>} | undefined)?.states?.[db.state_code] : undefined;
    const dbExtra = db as HDPlayerDbEntry & {socials?: Record<string, string>};

    return {
        ...player,
        real_name: player.real_name || db.name,
        pronoun: player.pronoun || db.pronoun,
        country: player.country?.code ? player.country : country,
        state: player.state?.name ? player.state : state ? {...state, code: db.state_code} : undefined,
        socials: {...(dbExtra.socials ?? {}), ...(player.socials ?? {})},
        twitter: player.twitter || db.twitter,
        character: Object.keys(player.character ?? {}).length ? player.character : mains,
        custom_textbox: db.custom_textbox,
    };
}

/** The players of a set in the stream queue, with their stats, fetched when it's opened */
export function PreviewDialog({set, onClose}: {set: QueueSet | null; onClose: () => void}) {
    const [response, setResponse] = useState<PreviewResponse | null>(null);
    const [failed, setFailed] = useState(false);
    const {players, characters, countries, gameCodename} = useSelector((state: ReduxState) => ({
        players: state.hdPlayers.players,
        characters: state.hdCharacters.characters,
        countries: state.hdCountries.value,
        gameCodename: (state.hdState.hdState as {game?: {codename?: string}}).game?.codename,
    }), shallowEqual);

    const teams = [teamPlayers(set?.team?.["1"]), teamPlayers(set?.team?.["2"])];
    const queueKey = set?.queueKey;

    useEffect(() => {
        setResponse(null);
        setFailed(false);
        if (!queueKey || !set) return;
        const controller = new AbortController();
        fetch(`${BASE_URL}/commentary-preview`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({teams: [teamPlayers(set.team?.["1"]), teamPlayers(set.team?.["2"])]}),
            signal: controller.signal,
        })
            .then((res) => {
                if (!res.ok) throw new Error(res.statusText);
                return res.json();
            })
            .then((data: PreviewResponse) => setResponse(data))
            .catch((e) => {
                if (e?.name !== "AbortError") setFailed(true);
            });
        return () => controller.abort();
        // Fetched again only for another set, not when the queue's ETAs tick
    }, [queueKey]);

    const singles = teams[0].length === 1 && teams[1].length === 1;
    // undefined: loading; null: can't be had
    function stats<T>(value: T[] | null | undefined): T[] | null | undefined {
        if (failed) return null;
        if (!response) return undefined;
        return response.stats ? value ?? null : null;
    }
    const findInDatabase = (player: Person) => {
        const tag = player.team ? `${player.team} ${player.name}` : player.name ?? "";
        return (players as HDPlayerDb)[tag] ?? Object.values(players as HDPlayerDb).find((p) => p.gamerTag?.toLowerCase() === player.name?.toLowerCase());
    };
    const eta = etaText(set?.eta_minutes);

    return <Dialog open={!!set} onOpenChange={(open) => !open && onClose()}>
        <DialogContent className="max-h-[calc(100dvh-2rem)] grid-cols-[minmax(0,1fr)] overflow-y-auto sm:max-w-6xl">
            <DialogHeader>
                <DialogTitle>{teamName(set?.team?.["1"]) || i18n.t("tbd")} {i18n.t("vs")} {teamName(set?.team?.["2"]) || i18n.t("tbd")}</DialogTitle>
                <DialogDescription className="flex flex-wrap items-center gap-1.5">
                    {[set?.phase, set?.match, set?.best_of_text].filter(Boolean).join(" · ")}
                    {set?.onStream ? <Badge>{i18n.t("on_stream")}</Badge> : eta ? <Badge variant="outline">{eta}</Badge> : null}
                </DialogDescription>
            </DialogHeader>

            {failed ? <p className="text-sm text-ban">{i18n.t("preview_failed")}</p> : null}

            {singles ? <HeadToHead
                sets={stats(response?.recent_sets)}
                names={[teamName(set?.team?.["1"]), teamName(set?.team?.["2"])]}
            /> : null}

            <div className="grid grid-cols-[minmax(0,1fr)] gap-6 md:grid-cols-2">
                {teams.map((players, t) => <div key={t} className="flex min-w-0 flex-col gap-6">
                    {players.map((player, p) => {
                        const extra = response?.teams?.[t]?.[p];
                        const person: Person = {
                            ...withDatabase(player, findInDatabase(player), gameCodename, characters, countries),
                            seed: player.seed ?? set?.team?.[String(t + 1)]?.seed,
                            avatar: extra?.avatar,
                            custom: extra?.custom,
                        };
                        if (person.seed && person.seed > 100000) person.seed = undefined;
                        return <div key={p} className="flex flex-col gap-4">
                            <PlayerIdentity person={person} color={t === 0 ? "var(--p1)" : "var(--p2)"}/>
                            <PlayerNotes person={person}/>
                            {singles ? <>
                                <LastSets sets={stats(extra?.last_sets)}/>
                                <PastEvents sets={stats(extra?.history_sets)}/>
                            </> : null}
                        </div>;
                    })}
                </div>)}
            </div>
        </DialogContent>
    </Dialog>;
}
