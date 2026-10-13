import {useSelector} from "react-redux";
import i18n from "../i18n/config";
import {BACKEND_PORT, PROTOCOL} from "../env";
import type {ReduxState} from "../redux/store";
import type {HDCharacterDbEntry, HDCharacterSkin} from "../backendDataTypes";
import {Autocomplete} from "@/components/Autocomplete";
import {Field} from "@/components/Field";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";

const assetUrl = (path: string) => `${PROTOCOL}//${window.location.hostname}:${BACKEND_PORT}/${path.replace(/^\.\//, "")}`;

interface CharSelectorProps {
    id: string;
    charName: string;
    charSkin: string;
    onCharNameChanged: (character: HDCharacterDbEntry | null) => void;
    onCharSkinChanged: (skin: string) => void;
}

/** A character and its skin */
export function CharSelector({id, charName, charSkin, onCharNameChanged, onCharSkinChanged}: CharSelectorProps) {
    const characters = useSelector((state: ReduxState) => state.hdCharacters.characters);
    const hasCharName = !!charName;
    const skins = Object.entries(characters[charName]?.skins ?? {});

    return (
        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-4">
            <Field label={i18n.t("character")} htmlFor={id + "-name"}>
                <Autocomplete
                    id={id + "-name"}
                    options={Object.values(characters)}
                    value={characters?.[charName] ?? null}
                    getLabel={(char) => char?.display_name ?? ""}
                    getKey={(char) => char.en_name}
                    renderOption={(char) => {
                        const icon = char?.skins?.[0]?.assets?.["base_files/icon"]?.asset;
                        return <>
                            {icon
                                ? <img className="size-8 object-contain" alt="" src={assetUrl(icon)}/>
                                : <span className="size-8"/>
                            }
                            <span>{char?.display_name}</span>
                        </>;
                    }}
                    onSelect={onCharNameChanged}
                />
            </Field>

            <Field label={"Skin"} htmlFor={id + "-skin"}>
                <Select
                    value={hasCharName && charSkin !== "" ? charSkin : undefined}
                    disabled={!hasCharName}
                    onValueChange={onCharSkinChanged}
                >
                    <SelectTrigger id={id + "-skin"} className="h-14 w-24 data-[size=default]:h-14">
                        <SelectValue/>
                    </SelectTrigger>
                    <SelectContent className="min-w-0">
                        {skins.map(([idx, skin]) => (
                            <SelectItem key={charName + idx} value={idx}>
                                <img
                                    alt={`Skin ${idx}`}
                                    className="size-12 object-cover"
                                    src={getSkinAssetUrl(skin)}
                                />
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </Field>
        </div>
    );
}

function getSkinAssetUrl(skin: HDCharacterSkin) {
    const assets = skin?.assets;
    const asset = assets?.costume ?? assets?.full ?? assets?.["base_files/icon"];
    return asset ? assetUrl(asset.asset) : "about:blank";
}
