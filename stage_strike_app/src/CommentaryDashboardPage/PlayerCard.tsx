import {BASE_URL} from "../env";
import i18n from "../i18n/config";
import type {Person} from "./types";
import {assetUrl, CharacterIcon, characterList, SectionTitle, SocialIcon} from "./util";
import {Avatar, AvatarFallback, AvatarImage} from "@/components/ui/avatar";
import {Badge} from "@/components/ui/badge";

const IMAGE = /\.(png|jpe?g|gif|webp|svg|avif)$/i;
const VIDEO = /\.(mp4|webm|mov|m4v)$/i;

/** Who a player is: tag, name, pronouns, where they're from, seed, socials and characters */
export function PlayerIdentity({person, color, aside}: {person: Person; color?: string; aside?: React.ReactNode}) {
    const avatar = assetUrl(person.avatar) ?? person.online_avatar ?? undefined;
    const countryCode = person.country?.code;
    const countryName = person.country?.display_name || person.country?.name || person.country?.en_name;
    const stateFlag = assetUrl(person.state?.asset);
    const characters = characterList(person.character);
    const socials = Object.entries(person.socials ?? {}).filter(([, handle]) => handle);
    if (socials.length === 0 && person.twitter) {
        socials.push(["twitter", person.twitter]);
    }
    const location = [person.city, person.state?.name, countryName].filter(Boolean).join(", ");

    return <div className="flex flex-col gap-3">
        <div className="flex items-start gap-3">
            <Avatar className="size-16 rounded-lg border-2" style={color ? {borderColor: color} : undefined}>
                <AvatarImage src={avatar} alt={i18n.t("avatar_for", {player: person.name})} className="object-cover"/>
                <AvatarFallback className="rounded-lg text-xl">{(person.name ?? "?").slice(0, 2)}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-x-2">
                    {person.team ? <span className="text-lg text-muted-foreground">{person.team}</span> : null}
                    <span className="text-2xl leading-tight font-bold break-words">{person.name || i18n.t("no_player")}</span>
                    {aside ? <span className="self-center">{aside}</span> : null}
                </div>
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
                    {person.real_name ? <span className="text-foreground">{person.real_name}</span> : null}
                    {person.pronoun ? <Badge variant="secondary">{person.pronoun}</Badge> : null}
                    {person.seed ? <Badge variant="outline">{i18n.t("seed_n", {value: person.seed})}</Badge> : null}
                    {person.wins !== undefined && person.losses !== undefined
                        ? <Badge variant="outline">{i18n.t("record", {wins: person.wins, losses: person.losses})}</Badge>
                        : null}
                </div>
                {location ? <div className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
                    {countryCode ? <img
                        alt=""
                        src={`${BASE_URL}/assets/country_flag/${countryCode.toLowerCase()}.png`}
                        className="h-3.5 w-auto"
                        onError={(e) => (e.currentTarget.style.display = "none")}
                    /> : null}
                    {stateFlag ? <img alt="" src={stateFlag} className="h-3.5 w-auto" onError={(e) => (e.currentTarget.style.display = "none")}/> : null}
                    <span className="truncate">{location}</span>
                </div> : null}
            </div>
        </div>

        {characters.length > 0 ? <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm">
            {characters.map((c, i) => <CharacterIcon key={i} character={c} showName className="size-7"/>)}
        </div> : null}

        {socials.length > 0 ? <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm text-muted-foreground">
            {socials.map(([platform, handle]) => <span key={platform} className="inline-flex items-center gap-1">
                <SocialIcon platform={platform}/>{handle}
            </span>)}
        </div> : null}
    </div>;
}

function CustomValue({value}: {value: unknown}) {
    if (typeof value === "string") {
        if (/^\.?\/?user_data\//.test(value) && IMAGE.test(value)) {
            return <img src={assetUrl(value) ?? undefined} alt="" className="max-h-48 max-w-full rounded-md object-contain"/>;
        }
        if (/^\.?\/?user_data\//.test(value) && VIDEO.test(value)) {
            return <video src={assetUrl(value) ?? undefined} className="max-h-48 max-w-full rounded-md" muted loop autoPlay playsInline/>;
        }
        return <p className="text-sm whitespace-pre-wrap">{value}</p>;
    }
    if (value && typeof value === "object" && !Array.isArray(value)) {
        return <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-sm">
            {Object.entries(value).map(([k, v]) => <div key={k} className="contents">
                <dt className="text-muted-foreground">{humanize(k)}</dt>
                <dd className="break-words">{typeof v === "object" && v !== null ? (Array.isArray(v) ? v.join(", ") : JSON.stringify(v)) : String(v)}</dd>
            </div>)}
        </dl>;
    }
    if (Array.isArray(value)) {
        return <p className="text-sm">{value.map((v) => (typeof v === "object" ? JSON.stringify(v) : String(v))).join(", ")}</p>;
    }
    return <p className="text-sm">{String(value)}</p>;
}

function humanize(key: string) {
    const text = key.replace(/[_-]+/g, " ").trim();
    return text.charAt(0).toUpperCase() + text.slice(1);
}

/**
 * The player's notes: "Additional information" from the player database and
 * the files in their custom data folder (user_data/custom_player_export/<tag>)
 */
export function PlayerNotes({person}: {person: Person}) {
    const custom = Object.entries(person.custom ?? {});
    if (!person.custom_textbox && custom.length === 0) {
        return null;
    }
    return <section className="flex flex-col gap-2">
        <SectionTitle>{i18n.t("notes")}</SectionTitle>
        <div className="flex flex-col gap-3 rounded-md border bg-muted/30 p-3">
            {person.custom_textbox ? <p className="text-sm whitespace-pre-wrap">{person.custom_textbox}</p> : null}
            {custom.map(([key, value]) => <div key={key} className="flex flex-col gap-1">
                <span className="text-xs font-medium text-muted-foreground">{humanize(key)}</span>
                <CustomValue value={value}/>
            </div>)}
        </div>
    </section>;
}
