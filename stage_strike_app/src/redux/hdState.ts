import {createSlice, PayloadAction} from '@reduxjs/toolkit'
import {
    HDCountryDb,
    HDCharacterDb,
    HDCharacterDbEntry,
    HDPlayerDb,
    HDState,
    HDGamesDb
} from "../backendDataTypes";

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
    /** Number of the last state message in hdState (-1: none, or unnumbered) */
    maxAppliedDeltaIdx: number;
    initializing: boolean;
};

/**
 * The program state. Following the server's messages (which deltas apply,
 * when to ask for the whole state again) is the state client's job, shared
 * with the layouts: see ScoreboardPage/websocketInit.ts, which hands the
 * resulting states to overwrite(). They share what didn't change with the
 * state before.
 */
export const hdStateSlice = createSlice({
    name: 'hdState',
    initialState: {
        hdState: {} as HDState,
        maxAppliedDeltaIdx: -1,
        initializing: true,
    } as HdStateReduxState,
    reducers: {
        overwrite(state: HdStateReduxState, action: PayloadAction<HDStateMessage>) {
            state.hdState = action.payload.state;
            // As given, even lower: HyperDrive counts from 0 again when it restarts
            state.maxAppliedDeltaIdx = action.payload.delta_index;
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
