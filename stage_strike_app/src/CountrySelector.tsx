import {useSelector} from "react-redux";
import {Autocomplete} from "@/components/Autocomplete";
import {BACKEND_PORT, PROTOCOL, inlineFlagWidth} from "./env";
import type {ReduxState} from "./redux/store";
import type {HDCountryInfo} from "./backendDataTypes";

const flagUrl = (country: HDCountryInfo) => country?.code?.toLowerCase
    ? `${PROTOCOL}//${window.location.hostname}:${BACKEND_PORT}/assets/country_flag/${country.code.toLowerCase()}.png`
    : null;

/** A flag, removed if there's no picture of it */
export function Flag({src}: {src: string | null}) {
    if (!src) return null;
    return <img
        alt=""
        loading={"lazy"}
        src={src}
        width={inlineFlagWidth}
        onError={(e) => e.currentTarget.remove()}
    />;
}

interface CountrySelectorProps {
    id?: string;
    // The country's code
    value: string;
    onChange: (code: string) => void;
    className?: string;
}

export function CountrySelector({id, value, onChange, className}: CountrySelectorProps) {
    const countries = useSelector((state: ReduxState) => state.hdCountries.value);
    const country = countries[value] ?? null;
    const label = (c: HDCountryInfo) => c?.name ? `${c.name} (${c.code})` : "";

    return <Autocomplete
        id={id}
        className={className}
        options={Object.values(countries)}
        value={country}
        getLabel={label}
        getKey={(c) => c.code}
        minChars={2}
        limit={8}
        startAdornment={country?.name ? <Flag src={flagUrl(country)}/> : null}
        renderOption={(c) => <>
            <Flag src={flagUrl(c)}/>
            <span>{label(c)}</span>
        </>}
        onSelect={(c) => onChange(c?.code ?? "")}
    />;
}
