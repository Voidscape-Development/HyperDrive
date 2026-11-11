/**
 * HyperDrive's state protocol: which deltas to apply, how, and when to ask
 * for the whole state again. The one implementation is the layouts' plain
 * script layout/include/state_client.js (see docs/state-protocol.md), bundled
 * here as it is: importing it defines the global HDStateClient.
 *
 * applyDeltas() leaves the state it is given as it was and shares what didn't
 * change with it, so it is fine with the frozen states the redux store holds,
 * and selectors of unchanged parts keep returning the same objects.
 */
/// <reference path="../../layout/include/state_client.d.ts" />
/// <reference path="../../layout/include/state.d.ts" />
import "../../layout/include/state_client.js";

export const { ACTIONS, SET_ACTIONS, REMOVE_ACTIONS, applyDeltas, createSync } = HDStateClient;

export type Delta = HDStateClient.Delta;
export type StateMessage<S> = HDStateClient.StateMessage<S>;
export type DeltaMessage = HDStateClient.DeltaMessage;
export type DeltaStatus = HDStateClient.DeltaStatus;
export type Sync = HDStateClient.Sync;

/** The program state's shape, generated from src/state_schema.py (layout/include/state.d.ts) */
export type ProgramState = HDState.State;
