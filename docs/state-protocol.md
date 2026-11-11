# State protocol: how clients follow the program state

HyperDrive keeps one program state (a JSON object, see
[layout-data.md](layout-data.md) and the types in
[`layout/include/state.d.ts`](../layout/include/state.d.ts)) and sends it to
its clients over socket.io: the layouts, the web app (`stage_strike_app/`) and
the Stream Deck plugin (`streamdeck/`).

The client side is implemented once, in
[`layout/include/state_client.js`](../layout/include/state_client.js) (types
in `state_client.d.ts`):

| Client | How it gets the implementation |
| - | - |
| Layouts | `globals.js` loads `state_client.js` with the other scripts of `include/`. A plain script: OBS opens layouts from `file://`, where ES modules don't load. |
| Web app | `stage_strike_app/src/stateClient.ts` imports the same file; Vite bundles it. |
| Stream Deck plugin | `streamdeck/src/hyperdrive/state-client.ts` imports the same file; rollup bundles it. |

Each client owns its socket. The shared part is what to do with the
messages.

## Messages

| Event | Payload | Sent |
| - | - | - |
| `program_state` | `{state, delta_index}` | To a client when it connects, to a client that asks for it (it emits `program_state`), and to every client after a change too big for deltas |
| `program_state_update` | `{delta_index, delta: [...]}` | To every client, for each saved change of the state |

`delta_index` counts the changes since HyperDrive started: it is 0 again
after a restart. A whole state carries the number of the last change in it,
and the update after it has the next number.

A client that only needs some of the state connects with
`auth: {state_keys: ["score", "game"]}` and gets only those top-level keys,
in both messages. It still gets every update, with an empty `delta` when
none of its keys changed, so the numbers it sees stay one by one.

Each item of `delta` is a change at a `path` (a list of keys, from the
state's root):

| `action` | |
| - | - |
| `values_changed`, `type_changes`, `dictionary_item_added` | The value at `path` is `value` |
| `dictionary_item_removed` | The key at `path` is removed |

These are DeepDiff's flat deltas, with their other fields (`old_value`,
`type`...), which clients ignore. Lists whose items were added, removed or
moved are sent whole, as one `values_changed` of the list
(`StateManager.WholeListDeltas`); a value changed inside an item that stays
has the item's index in its path.

## What a client does

`HDStateClient.createSync(requestFullState)` follows the numbering;
`requestFullState` emits `program_state`.

- **A whole state is always taken**, and its `delta_index` becomes the
  client's number, a lower one included (HyperDrive restarted).
- **An update is applied only if its number is the client's plus one.** The
  client's number then moves on, with an empty `delta` too.
- **The same number as the client's is ignored**: the whole state was read
  after that change.
- **An older number, a skipped number, an update before any whole state, or
  an update the client can't apply** (see below) mean the client's state
  is off: it asks for the whole state, once, and ignores updates until it
  comes. An update is never applied in part.

An update can't be applied when it isn't `{delta_index: <integer>, delta:
[...]}`, or one of its deltas has an action other than the four above, no
path, no value to set (or DeepDiff's placeholder `"unknown___"`), or changes
a list other than by setting an item it has or the one after its last.

Applying leaves the previous state object as it was: the objects and lists
on the changed paths are copied, everything else is shared with the previous
state. Layouts compare the two to call `update()` with what changed, and the
web app's selectors keep returning the same objects for what didn't. On the
way to a path, a key that is missing (or holds a value that isn't an object)
becomes an object.

`sync.delta(message, state)` returns `{status, state}`:

| `status` | | Asks for the whole state |
| - | - | - |
| `applied` | Next in line; `state` is the new state | |
| `empty` | Next in line, nothing to apply | |
| `duplicate` | Same number as the client's | |
| `stale` | Older number | Yes |
| `gap` | Skipped numbers, or no whole state yet | Yes |
| `invalid` | Can't be applied | Yes |
| `waiting` | The whole state was asked for and hasn't come | |

Layouts opened from a file have no socket: they read
`out/program_state.json` again and again instead, which is always the whole
state.

## Tests

[`test/fixtures/state_protocol.json`](../test/fixtures/state_protocol.json)
is the protocol as cases: messages in order (every action, lists, gaps,
stale and duplicate numbers, a restart, subscriptions, malformed updates),
with the state, the number and whether the whole state is asked for after
each. It is run against:

- `layout/include/state_client.js`: `node --test test/state_client.test.cjs`
- the Stream Deck plugin's import of it: `streamdeck/test/state-client.test.ts`
- `test/state_protocol.py`, a Python port that the StateManager tests apply
  deltas with (`test/test_state_deltas.py`): `test/test_state_protocol.py`

A change to the protocol goes in `state_client.js`, `state_client.d.ts`,
`test/state_protocol.py` and the fixture.
