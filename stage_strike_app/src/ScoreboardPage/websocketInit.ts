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

let initialized = false;

export default function websocketInit() {
    if (initialized) {
        return;
    }

    initialized = true;
    const socket = socketConnection.instance();

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
        hdStore.dispatch(hdStateSlice.actions.overwrite(data));
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
        hdStore.dispatch(hdStateSlice.actions.addDeltas(deltaMessage));
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
    setInterval(() => {
        const state = hdStore.getState();
        if (state.websocketInfo.status === "connected" && state.hdState?.stateDeltas.length > 0) {
            hdStore.dispatch(hdStateSlice.actions.applySavedDeltas());
        }
    }, 1000);
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

