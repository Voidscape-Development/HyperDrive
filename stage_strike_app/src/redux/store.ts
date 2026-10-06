import {configureStore, combineReducers, Action} from '@reduxjs/toolkit'
import {
    hdCharactersSlice,
    hdCountriesSlice,
    hdGamesSlice,
    hdPlayersSlice,
    hdStateSlice,
    websocketInfoSlice
} from './hdState';
import {selectedScoreboardSlice} from "./uiState";
import {produce} from "immer";

export const hdStore = configureStore({
    reducer: combineReducers({
        hdState: hdStateSlice.reducer,
        hdPlayers: hdPlayersSlice.reducer,
        hdCharacters: hdCharactersSlice.reducer,
        hdGames: hdGamesSlice.reducer,
        hdCountries: hdCountriesSlice.reducer,
        websocketInfo: websocketInfoSlice.reducer,
        selectedScoreboard: selectedScoreboardSlice.reducer,
    }),
    devTools: {
        // Helps keep the devtools crispy.
        stateSanitizer: function<S>(state: S, index) {
            return produce(state, (ds: any) => {
                try {
                    ds.hdPlayers = `<${objLen(ds.hdPlayers.players)} players>`;
                    ds.hdCountries = `<${objLen(ds.hdCountries.value)} countries>`;
                    for (let k in ds.hdCharacters.characters) {
                        ds.hdCharacters.characters[k].skins = `<${objLen(ds.hdCharacters.characters[k].skins)} skins>`
                    }
                    ds.hdState.hdState.bracket = "omitted";
                    ds.hdState.hdState.player_list = "omitted";
                } catch {}
            });
        },
        predicate: function<S, A extends Action>(state: S, action: A) {
            return action.type !== 'hdState/maybeApplySavedDeltas';
        }
    },
});

const objLen = (o: any) => Object.keys(o).length;

export type HdStore = typeof hdStore;
export type ReduxState = ReturnType<HdStore['getState']>
export type ReduxDispatch = HdStore['dispatch'];
