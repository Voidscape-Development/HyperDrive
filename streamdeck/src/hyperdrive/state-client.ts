/**
 * HyperDrive's state protocol: which deltas to apply, how, and when to ask
 * for the whole state again. The one implementation is the layouts' plain
 * script layout/include/state_client.js (see docs/state-protocol.md), bundled
 * here as it is: importing it defines the global HDStateClient.
 */
/// <reference path="../../../layout/include/state_client.d.ts" />
import "../../../layout/include/state_client.js";

export const { ACTIONS, SET_ACTIONS, REMOVE_ACTIONS, applyDeltas, createSync } = HDStateClient;

export type Delta = HDStateClient.Delta;
export type StateMessage = HDStateClient.StateMessage;
export type DeltaMessage = HDStateClient.DeltaMessage;
export type DeltaStatus = HDStateClient.DeltaStatus;
export type Sync = HDStateClient.Sync;
