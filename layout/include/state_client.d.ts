// Types of state_client.js, which defines the global HDStateClient. Written
// by hand: keep them in step with it. The web app and the Stream Deck
// plugin reach it through their stateClient modules.

declare namespace HDStateClient {
  type State = Record<string, any>;

  type SetAction = "values_changed" | "type_changes" | "dictionary_item_added";
  type RemoveAction = "dictionary_item_removed";
  type Action = SetAction | RemoveAction;

  /** One change: the value at path set, or the key at path removed. The server sends more fields (DeepDiff's), unused. */
  interface Delta {
    path: (string | number)[];
    action: Action | (string & {});
    value?: unknown;
  }

  /** "program_state": the whole state, or what the client subscribed to of it */
  interface StateMessage<S = State> {
    state: S;
    delta_index: number;
  }

  /** "program_state_update": changes since the message numbered one less */
  interface DeltaMessage {
    delta_index: number;
    delta: Delta[];
  }

  type DeltaStatus = "applied" | "empty" | "duplicate" | "stale" | "gap" | "invalid" | "waiting";
  /** The statuses the whole state is asked for with */
  type ResyncReason = "stale" | "gap" | "invalid";

  interface Sync {
    /** Number of the last message taken, null before the first whole state */
    readonly index: number | null;
    /** The whole state was asked for and hasn't come */
    readonly resyncing: boolean;
    /** Takes a whole state, whatever its number, and returns it */
    full<S extends State = State>(message: StateMessage<S> | null | undefined): S;
    /** Applies a delta message if it is next in line. The state given is never changed. */
    delta<S extends State = State>(
      message: DeltaMessage | null | undefined,
      state: S,
    ): { status: DeltaStatus; state: S };
    /** Forgets the numbering, for a connection that is gone or changed */
    reset(): void;
  }

  interface Api {
    readonly SET_ACTIONS: readonly SetAction[];
    readonly REMOVE_ACTIONS: readonly RemoveAction[];
    readonly ACTIONS: readonly Action[];
    /**
     * The state with the deltas applied. The state given is left as it was:
     * objects on the changed paths are copied, the rest is shared. Throws
     * (an Error named "HDDeltaError") on a delta the protocol doesn't know.
     */
    applyDeltas<S extends State = State>(state: S, deltas: Delta[]): S;
    /** requestFullState asks the server for the whole state: socket.emit("program_state", {}) */
    createSync(requestFullState: (reason: ResyncReason, deltaIndex: unknown) => void): Sync;
  }
}

declare const HDStateClient: HDStateClient.Api;
