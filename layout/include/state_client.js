// HyperDrive's state protocol, client side. The one implementation: the
// layouts load this file as it is (globals.js), and the web app
// (stage_strike_app/src/stateClient.ts) and the Stream Deck plugin
// (streamdeck/src/hyperdrive/state-client.ts) bundle this same file. Types
// in state_client.d.ts, the contract in docs/state-protocol.md, and
// test/fixtures/state_protocol.json is what every client is tested with.
//
// The web server sends, over socket.io:
//   program_state         { state, delta_index }   the whole state: on
//                         connect, when asked for (emit "program_state"), and
//                         to everyone after a change too big for a delta
//   program_state_update  { delta_index, delta: [{ path, action, value }] }
//                         numbered one by one from the last whole state
//
// No dependencies and no module syntax on purpose: a classic script for the
// layouts (OBS opens them from file://, where ES modules don't load), which
// bundlers import for its side effect of defining HDStateClient.
(function (root) {
  "use strict";

  // What StateManager sends (see DiffStates there): a value set or a key
  // removed, and a changed list as the whole list. type_changes is no
  // longer sent, and stays known for servers that still do.
  const SET_ACTIONS = ["values_changed", "type_changes", "dictionary_item_added"];
  const REMOVE_ACTIONS = ["dictionary_item_removed"];
  const ACTIONS = SET_ACTIONS.concat(REMOVE_ACTIONS);

  // What older servers sent for a change they had no value of (1 becoming true)
  const UNKNOWN_VALUE = "unknown___";

  const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);

  function fail(message, delta) {
    const error = new Error(`${message}: ${JSON.stringify(delta)}`);
    error.name = "HDDeltaError";
    return error;
  }

  // A list's index from a path key: 0 to the list's length (one past the
  // end adds an item), or -1
  function listIndex(list, key) {
    const index = typeof key === "number" ? key : /^\d+$/.test(key) ? Number(key) : -1;
    return Number.isInteger(index) && index >= 0 && index <= list.length ? index : -1;
  }

  // The state with the deltas applied, leaving the state as it was: only
  // the objects on the changed paths are copied, the rest is shared.
  // Throws on a delta this protocol doesn't know, without a half applied
  // state: the caller's is untouched.
  function applyDeltas(state, deltas) {
    if (!Array.isArray(deltas)) throw fail("Not a list of deltas", deltas);
    const root = Object.assign({}, state);
    const copied = new Set([root]);

    for (const delta of deltas) {
      const path = delta && delta.path;
      if (!Array.isArray(path) || path.length === 0) throw fail("Delta without a path", delta);
      const remove = REMOVE_ACTIONS.includes(delta.action);
      if (!remove) {
        if (!SET_ACTIONS.includes(delta.action)) throw fail("Unsupported delta action", delta);
        if (delta.value === undefined || delta.value === UNKNOWN_VALUE) throw fail("Delta without a value", delta);
      }

      let node = root;
      for (let i = 0; i < path.length; i++) {
        let key = path[i];
        if ((typeof key !== "string" && typeof key !== "number") || key === "__proto__") {
          throw fail("Invalid key in a delta's path", delta);
        }
        if (Array.isArray(node)) {
          key = listIndex(node, key);
          // Items are never removed from lists: the whole list is sent
          if (key < 0 || (remove && i === path.length - 1)) throw fail("Invalid list change", delta);
        }
        if (i === path.length - 1) {
          if (remove) delete node[key];
          else node[key] = delta.value;
          break;
        }
        // On the way: a copy of what is there, or a new object where there
        // is none (or a value that isn't one)
        let next = node[key];
        if (!own(node, key) || next === null || typeof next !== "object") {
          next = {};
        } else if (!copied.has(next)) {
          next = Array.isArray(next) ? next.slice() : Object.assign({}, next);
        }
        copied.add(next);
        node[key] = next;
        node = next;
      }
    }
    return root;
  }

  // Follows the numbering of the messages of one connection, and applies
  // the deltas that are next in line. requestFullState() asks the server
  // for the whole state (socket.emit("program_state", {})).
  //
  //   full(message)          → the state; always taken, whatever its number
  //                            (HyperDrive restarted counts from 0 again)
  //   delta(message, state)  → { status, state }, the state as given unless
  //                            status is "applied":
  //     "applied"    next in line and applied
  //     "empty"      next in line, with nothing the client subscribed to
  //     "duplicate"  same number as the state held, which has it: ignored
  //     "stale"      older number                   } the state here is
  //     "gap"        skipped numbers, or no state   } off: the whole state
  //     "invalid"    not a delta message this       } is asked for, once
  //                  protocol knows                 }
  //     "waiting"    the whole state was asked for and hasn't come: ignored
  function createSync(requestFullState) {
    const sync = {
      // Number of the last message taken, null before the first whole state
      index: null,
      // The whole state was asked for and hasn't come
      resyncing: false,

      full(message) {
        const index = message ? message.delta_index : undefined;
        sync.index = Number.isInteger(index) ? index : null;
        sync.resyncing = false;
        const state = message ? message.state : undefined;
        return state !== null && typeof state === "object" && !Array.isArray(state) ? state : {};
      },

      delta(message, state) {
        if (sync.resyncing) return { status: "waiting", state };
        const index = message ? message.delta_index : undefined;
        let status;
        if (!Number.isInteger(index) || !Array.isArray(message.delta)) status = "invalid";
        else if (sync.index === null || index > sync.index + 1) status = "gap";
        else if (index === sync.index) status = "duplicate";
        else if (index < sync.index) status = "stale";
        else if (message.delta.length === 0) status = "empty";
        else {
          try {
            state = applyDeltas(state, message.delta);
            status = "applied";
          } catch (e) {
            if (!e || e.name !== "HDDeltaError") throw e;
            status = "invalid";
          }
        }

        if (status === "applied" || status === "empty") sync.index = index;
        else if (status !== "duplicate") {
          sync.resyncing = true;
          requestFullState(status, index);
        }
        return { status, state };
      },

      // The connection is gone or changed: nothing is known any more
      reset() {
        sync.index = null;
        sync.resyncing = false;
      },
    };
    return sync;
  }

  root.HDStateClient = { SET_ACTIONS, REMOVE_ACTIONS, ACTIONS, applyDeltas, createSync };
})(typeof globalThis !== "undefined" ? globalThis : window);
