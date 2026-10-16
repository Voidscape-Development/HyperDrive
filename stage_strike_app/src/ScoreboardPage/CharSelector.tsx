import {useSelector} from "react-redux";
import i18n from "../i18n/config";
import {BACKEND_PORT, PROTOCOL} from "../env";
import type {ReduxState} from "../redux/store";
import type {HDCharacterDbEntry, HDCharacterSkin} from "../backendDataTypes";
import {Autocomplete} from "@/components/Autocomplete";
import {Field} from "@/components/Field";
import {cn} from "@/lib/utils";

const assetUrl = (path: string) => `${PROTOCOL}//${window.location.hostname}:${BACKEND_PORT}/${path.replace(/^\.\//, "")}`;

interface CharSelectorProps {
    id: string;
    label: string;
    charName: string;
    charSkin: string;
    // The player's mains, offered as one-tap picks
    mains?: string[];
    onCharNameChanged: (character: HDCharacterDbEntry | null) => void;
    onCharSkinChanged: (skin: string) => void;
}

/** A character, picked by search or from the player's mains, and its costume */
export function CharSelector({id, label, charName, charSkin, mains = [], onCharNameChanged, onCharSkinChanged}: CharSelectorProps) {
    const characters = useSelector((state: ReduxState) => state.hdCharacters.characters);
    const skins = Object.entries(characters[charName]?.skins ?? {});
    const suggestions = mains.filter((m) => characters[m] && m !== charName);

    return (
        <div className="flex flex-col gap-2.5">
            <Field label={label} htmlFor={id + "-name"}>
                <Autocomplete
                    id={id + "-name"}
                    options={Object.values(characters)}
                    value={characters?.[charName] ?? null}
                    getLabel={(char) => char?.display_name ?? ""}
                    getKey={(char) => char.en_name}
                    startAdornment={charName && characterIcon(characters[charName])
                        ? <img className="size-6 object-contain" alt="" src={characterIcon(characters[charName])}/>
                        : undefined}
                    renderOption={(char) => {
                        const icon = characterIcon(char);
                        return <>
                            {icon
                                ? <img className="size-8 object-contain" alt="" src={icon}/>
                                : <span className="size-8"/>
                            }
                            <span>{char?.display_name}</span>
                        </>;
                    }}
                    onSelect={onCharNameChanged}
                />
            </Field>

            {suggestions.length > 0 && (
                <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs text-muted-foreground">{i18n.t("mains")}</span>
                    {suggestions.map((m) => (
                        <button
                            key={m}
                            type="button"
                            onClick={() => onCharNameChanged(characters[m])}
                            className="flex h-9 cursor-pointer items-center gap-1.5 rounded-full border px-3 text-sm outline-none hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50"
                        >
                            {characterIcon(characters[m]) &&
                                <img className="size-5 object-contain" alt="" src={characterIcon(characters[m])}/>}
                            {characters[m].display_name}
                        </button>
                    ))}
                </div>
            )}

            {skins.length > 1 && (
                <div className="flex flex-col gap-1.5">
                    <span id={id + "-skin"} className="text-xs text-muted-foreground">{i18n.t("costume")}</span>
                    <div role="radiogroup" aria-labelledby={id + "-skin"} className="grid grid-cols-[repeat(auto-fill,minmax(2.75rem,1fr))] gap-1.5">
                        {skins.map(([idx, skin]) => (
                            <button
                                key={charName + idx}
                                type="button"
                                role="radio"
                                aria-checked={charSkin === idx}
                                aria-label={i18n.t("costume_n", {value: Number(idx) + 1})}
                                onClick={() => onCharSkinChanged(idx)}
                                className={cn(
                                    "aspect-square cursor-pointer overflow-hidden rounded-lg border-2 bg-background p-0.5 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                                    charSkin === idx ? "border-foreground" : "border-transparent hover:border-border",
                                )}
                            >
                                <img alt="" className="size-full rounded-md object-cover" src={getSkinAssetUrl(skin)}/>
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

function characterIcon(char: HDCharacterDbEntry | undefined) {
    const icon = char?.skins?.[0]?.assets?.["base_files/icon"]?.asset;
    return icon ? assetUrl(icon) : undefined;
}

function getSkinAssetUrl(skin: HDCharacterSkin) {
    const assets = skin?.assets;
    const asset = assets?.costume ?? assets?.full ?? assets?.["base_files/icon"];
    return asset ? assetUrl(asset.asset) : "about:blank";
}
