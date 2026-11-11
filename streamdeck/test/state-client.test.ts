import { describe, expect, it } from "vitest";

import fixture from "../../test/fixtures/state_protocol.json";
import { ACTIONS, createSync, REMOVE_ACTIONS, SET_ACTIONS, type DeltaMessage } from "../src/hyperdrive/state-client.ts";
import type { State } from "../src/hyperdrive/state.ts";

type Step = {
	full?: { state: State; delta_index?: number };
	delta?: unknown;
	reset?: boolean;
	status?: string;
	resync: boolean;
	index: number | null;
	state?: State;
};

// The protocol's conformance fixture, shared with the layouts' client and
// the Python tests: what the plugin holds after each message
describe("state protocol fixture", () => {
	it("knows the fixture's actions", () => {
		expect(SET_ACTIONS).toEqual(fixture.actions.set);
		expect(REMOVE_ACTIONS).toEqual(fixture.actions.remove);
		expect(ACTIONS).toEqual([...fixture.actions.set, ...fixture.actions.remove]);
	});

	for (const c of fixture.cases) {
		it(c.name, () => {
			let requests = 0;
			const sync = createSync(() => requests++);
			let state: State = {};
			(c.steps as unknown as Step[]).forEach((step, i) => {
				const at = `step ${i + 1}`;
				const before = requests;
				if (step.full) {
					state = sync.full(structuredClone(step.full) as { state: State; delta_index: number });
				} else if (step.reset) {
					sync.reset();
					state = {};
				} else {
					const held = state;
					const snapshot = structuredClone(held);
					const result = sync.delta(structuredClone(step.delta) as DeltaMessage, held);
					expect(result.status, at).toBe(step.status);
					// The state given is never written to
					expect(held, at).toEqual(snapshot);
					if (step.status !== "applied") {
						expect(result.state, at).toBe(held);
					}
					state = result.state;
				}
				expect(requests - before, `${at}: whole state asked for`).toBe(step.resync ? 1 : 0);
				expect(sync.index, at).toBe(step.index);
				if (step.state !== undefined) {
					expect(state, at).toEqual(step.state);
				}
			});
		});
	}
});
