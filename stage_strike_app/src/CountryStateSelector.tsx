import {useEffect, useState} from "react";
import {Autocomplete} from "@/components/Autocomplete";
import {Flag} from "./CountrySelector";
import {BACKEND_PORT, PROTOCOL} from "./env";
import type {HDStateInfo} from "./backendDataTypes";

interface CountryStateSelectorProps {
    id?: string;
    countryCode: string;
    // The state's code
    value: string;
    onChange: (code: string) => void;
    className?: string;
}

/** A state of the player's country, once a country is picked */
export function CountryStateSelector({id, countryCode, value, onChange, className}: CountryStateSelectorProps) {
    const isValidCountryCode = countryCode !== "" && !!countryCode;
    const [stateData, setStateData] = useState<{states: Record<string, HDStateInfo>; isLoading: boolean}>({
        states: {},
        isLoading: true,
    });

    useEffect(() => {
        if (isValidCountryCode) {
            fetch(`${PROTOCOL}//${window.location.hostname}:${BACKEND_PORT}/states?countryCode=${countryCode}`)
                .then(d => d.json())
                .then(j => setStateData({states: j, isLoading: false}))
                .catch(e => {
                    console.warn(`Failed to load autocomplete state data for country code ${countryCode}`, e);
                    setStateData({states: {}, isLoading: false});
                });
        }
    }, [countryCode, isValidCountryCode]);

    const isDisabled = !isValidCountryCode || stateData.isLoading;
    const selectedState = (!stateData.isLoading && stateData.states[value]) || null;

    const flagUrl = (state: HDStateInfo) => {
        if (state.asset && state.asset[0] === ".") {
            return `${PROTOCOL}//${window.location.hostname}:${BACKEND_PORT}${state.asset.slice(1)}`;
        }
        return `${PROTOCOL}//${window.location.hostname}:${BACKEND_PORT}/assets/state_flag/${countryCode}/${state.code}.png`;
    };
    const label = (state: HDStateInfo) => `${state.name} (${state.code})`;

    return <Autocomplete
        id={id}
        className={className}
        disabled={isDisabled}
        options={Object.values(stateData.states)}
        value={isDisabled ? null : selectedState}
        getLabel={label}
        getKey={(state) => state.code}
        startAdornment={selectedState && !isDisabled ? <Flag src={flagUrl(selectedState)}/> : null}
        renderOption={(state) => <>
            <Flag src={flagUrl(state)}/>
            <span>{label(state)}</span>
        </>}
        onSelect={(state) => onChange(state?.code ?? "")}
    />;
}
