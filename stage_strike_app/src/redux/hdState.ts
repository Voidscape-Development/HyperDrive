import {Action, createSlice, PayloadAction, WritableDraft} from '@reduxjs/toolkit'
import {applyDeltas, combineDeltas} from "../stateDelta";
import websocketConnection from "../websocketConnection";
import {
    HDCountryDb,
    HDCharacterDb,
    HDCharacterDbEntry,
    HDPlayerDb,
    HDState,
    HDGamesDb, Delta
} from "../backendDataTypes";

export type ReceivedDeltas = {
    delta_index: number;
    delta: Delta[];
};

export type HDStateMessage = {
    state: HDState;
    delta_index: number;
}

export type WebsocketStatus =
    'initial'
    | 'connected'
    | 'errored'
    | 'disconnected';

export const websocketInfoSlice = createSlice({
    name: 'websocketInfo',
    initialState: {
        status: 'initial' as WebsocketStatus,
        errorMessage: null as (null | string)
    },
    reducers: {
        setStatus(state, action: PayloadAction<WebsocketStatus>) {
            state.status = action.payload;
        }
    }
});

export type HdStateReduxState = {
    hdState: HDState;
    stateDeltas: ReceivedDeltas[];
    maxAppliedDeltaIdx: number;
    initializing: boolean;
};

export const hdStateSlice = createSlice({
    name: 'hdState',
    initialState: {
        hdState: {} as HDState,
        stateDeltas: [],
        maxAppliedDeltaIdx: -1,
        initializing: true,
    } as HdStateReduxState,
    reducers: {
        applySavedDeltas(state: WritableDraft<HdStateReduxState>, action: Action) {
            let sortedDeltas = state.stateDeltas.toSorted((a, b) => a.delta_index - b.delta_index);
            const staleDeltas = sortedDeltas.filter((d) => d.delta_index < state.maxAppliedDeltaIdx);
            sortedDeltas = sortedDeltas.filter((d) => d.delta_index >= state.maxAppliedDeltaIdx);

            if (staleDeltas.length > 0) {
                console.warn("Skipping applying stale deltas...", staleDeltas);
            }

            if (sortedDeltas.length > 0) {
                for (let deltaSet of sortedDeltas) {
                    console.log("Applying deltas: ", combineDeltas(deltaSet.delta));
                    applyDeltas(state.hdState, deltaSet.delta);
                }
                state.maxAppliedDeltaIdx = sortedDeltas[sortedDeltas.length-1].delta_index;
            }

            state.initializing = false;
            state.stateDeltas = [];
        },

        addDeltas(state: HdStateReduxState, action: PayloadAction<ReceivedDeltas>){
            if (action.payload.delta_index < state.maxAppliedDeltaIdx) {
                console.warn("Received out of order delta! Requesting new full state.");
                websocketConnection.instance().emit("program_state", {});
            }

            state.stateDeltas.push(action.payload);
        },

        overwrite(state: HdStateReduxState, action: PayloadAction<HDStateMessage>) {
            state.hdState = action.payload.state;
            state.maxAppliedDeltaIdx = Math.max(action.payload.delta_index, state.maxAppliedDeltaIdx);
            state.stateDeltas = [];
            state.initializing = false;
        },

        loadingNewData(state, action) {
            state.initializing = true;
        }
    }
})

export const hdPlayersSlice = createSlice({
    name: 'hdPlayers',
    initialState: {
        players: {} as HDPlayerDb,
        initializing: true,
    },
    reducers: {
        overwrite(state, action: PayloadAction<HDPlayerDb>) {
            state.players = action.payload;
            for (let k in state.players) {
                state.players[k].prefixed_tag = k;
            }
            state.initializing = false;
        }
    }
});

export const hdCharactersSlice = createSlice({
    name: 'hdCharacters',
    initialState: {
        characters: {} as HDCharacterDb,
        initializing: true,
    },
    reducers: {
        overwrite(state, action: PayloadAction<HDCharacterDb>) {
            // We need our character list to be keyed by the en_name, because things like player mains are set
            // to the english name instead the localized name. We won't be able to do lookups if we don't
            // rearrange it like this.
            const enChars: HDCharacterDb = {};
            Object.values(action.payload).forEach((char: HDCharacterDbEntry) => {
                enChars[char.en_name] = char;
            });
            console.log("Character data set", enChars);
            state.characters = enChars;
            state.initializing = false;
        }
    }
});

export const hdGamesSlice = createSlice({
    name: 'hdGames',
    initialState: {
        value: {} as HDGamesDb,
        initializing: true
    },
    reducers: {
        overwrite(state, action: PayloadAction<HDGamesDb>) {
            state.value = action.payload;
            for (let k in state.value) {
                state.value[k].codename = k;
            }
            state.initializing = false;
        }
    }
});

export const hdCountriesSlice = createSlice({
    name: 'hdCountries',
    initialState: {
        value: {} as HDCountryDb,
        initializing: true,
    },
    reducers: {
        overwrite(state, action: PayloadAction<HDCountryDb>) {
            state.value = action.payload;
            state.initializing = false;
        }
    }
});
