import {
    hdCharactersSlice,
    hdCountriesSlice,
    hdGamesSlice,
    hdPlayersSlice,
    hdStateSlice,
    websocketInfoSlice
} from "../redux/hdState";
import { hdStore } from "../redux/store";
import socketConnection from "../websocketConnection";
import {BACKEND_PORT, PROTOCOL} from "../env";
import {createSync} from "../stateClient";
import {HDState} from "../backendDataTypes";

let initialized = false;

export default function websocketInit() {
    if (initialized) {
        return;
    }

    initialized = true;
    const socket = socketConnection.instance();

    // The state protocol, shared with the layouts: applies the deltas that
    // are next in line, and asks for the whole state when one is missing or
    // older than the state held.
    const sync = createSync((reason, index) => {
        console.warn(`Delta ${index} after ${sync.index} (${reason}): requesting new full state.`);
        socket.emit("program_state", {});
    });
    // The state with every delta received applied, and whether the store
    // has it yet
    let latest = {} as HDState;
    let stored = true;
    const store = () => {
        stored = true;
        hdStore.dispatch(hdStateSlice.actions.overwrite({state: latest, delta_index: sync.index ?? -1}));
    };

    socket.on("connect", () => {
        console.log("SocketIO connection established.");
        hdStore.dispatch(websocketInfoSlice.actions.setStatus("connected"));
        socket.emit("playerdb", {}, () => {
            console.log("HyperDrive acked player db request")
        });
        socket.emit("characters", {}, () => {
            console.log("HyperDrive acked characters request")
        });
        socket.emit("games", {}, () => {
            console.log("HyperDrive acked games request")
        });

        loadCountriesFile();
    });

    socket.on("program_state", data => {
        console.log("HyperDrive state received ", data);
        latest = sync.full<HDState>(data);
        store();
    });

    socket.on("games", data => {
        console.log("HyperDrive game info received ", data);
        hdStore.dispatch(hdGamesSlice.actions.overwrite(data));
    })

    socket.on("countries", data => {
        console.log("HyperDrive countries info received.")
        hdStore.dispatch(hdCountriesSlice.actions.overwrite(data));

    });

    socket.on("program_state_update", deltaMessage => {
        console.log("HyperDrive state update received", deltaMessage);
        const result = sync.delta(deltaMessage, latest);
        if (result.status === "applied") {
            latest = result.state;
            stored = false;
        }
    });

    socket.on("playerdb", data => {
        console.log("Player data received", data);
        hdStore.dispatch(hdPlayersSlice.actions.overwrite(data));
    })

    socket.on("characters", data => {
        console.log("Character data received", data);
        hdStore.dispatch(hdCharactersSlice.actions.overwrite(data));
    })

    socket.on("disconnect", () => {
        console.log("SocketIO disconnected.")
        hdStore.dispatch(websocketInfoSlice.actions.setStatus("disconnected"));
        socket.connect();
    });

    socket.on('error', (err) => {
        console.log(err);
        hdStore.dispatch(websocketInfoSlice.actions.setStatus("errored"));
    });

    // This can't be set up twice because of the initialization guard at the top of the function.
    // Often enough that a change made on a page shows there without a lag
    // Deltas come in bursts: the store gets their result, not each of them
    setInterval(() => {
        if (!stored) {
            store();
        }
    }, 200);
}

// Todo, maybe move this to a thunk or something.
const loadCountriesFile = () => {
    fetch(
        `${PROTOCOL}//${window.location.hostname}:${BACKEND_PORT}/assets/data_countries.json`
    ).then(
        (resp) => resp.json()
    ).then((json) => {
        for (let key in json) {
            json[key].code = key;
        }

        console.log("Loaded countries json file", json);
        hdStore.dispatch(hdCountriesSlice.actions.overwrite(json));
    }).catch((e) => {
        console.error("Failed to request countries file", e);
        hdStore.dispatch(hdCountriesSlice.actions.overwrite({}));
    });
}

