// Checks layout/include/state_client.js, the state protocol's client (which
// the layouts load, and the web app and the Stream Deck plugin bundle),
// against the conformance fixture test/fixtures/state_protocol.json.
// Run from the repository root: node --test test/state_client.test.cjs
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const SOURCE = path.join(__dirname, "../layout/include/state_client.js");
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures/state_protocol.json"), "utf8"));

// Defines the global, as in a page
require(SOURCE);
const client = globalThis.HDStateClient;

const clone = (value) => JSON.parse(JSON.stringify(value));

function deepFreeze(value) {
  if (value !== null && typeof value === "object") {
    Object.values(value).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
}

test("is a classic script that only defines HDStateClient", () => {
  // Layouts load it with a <script> tag from file://: no module syntax
  const sandbox = { window: null };
  sandbox.window = sandbox;
  new vm.Script(fs.readFileSync(SOURCE, "utf8"), { filename: SOURCE }).runInNewContext(sandbox);
  assert.deepEqual(Object.keys(sandbox), ["window", "HDStateClient"]);
  assert.deepEqual(Object.keys(sandbox.HDStateClient), Object.keys(client));
});

test("knows the fixture's actions", () => {
  assert.deepEqual(client.SET_ACTIONS, fixture.actions.set);
  assert.deepEqual(client.REMOVE_ACTIONS, fixture.actions.remove);
  assert.deepEqual(client.ACTIONS, [...fixture.actions.set, ...fixture.actions.remove]);
});

for (const c of fixture.cases) {
  test(`fixture: ${c.name}`, () => {
    let requests = 0;
    const sync = client.createSync(() => requests++);
    let state = {};
    c.steps.forEach((step, i) => {
      const at = `step ${i + 1}`;
      const before = requests;
      if (step.full) {
        state = sync.full(clone(step.full));
      } else if (step.reset) {
        sync.reset();
        state = {};
      } else {
        // Frozen: applying must never write to the state it is given
        const held = deepFreeze(state);
        const result = sync.delta(deepFreeze(clone(step.delta)), held);
        assert.equal(result.status, step.status, at);
        if (step.status !== "applied") assert.equal(result.state, held, `${at}: the same state object`);
        state = result.state;
      }
      assert.equal(requests - before, step.resync ? 1 : 0, `${at}: whole state asked for`);
      assert.equal(sync.index, step.index, `${at}: index`);
      assert.equal(sync.resyncing, c.steps.slice(0, i + 1).reduce((r, s) => (s.delta ? r || s.resync : false), false), at);
      if ("state" in step) assert.deepEqual(state, step.state, at);
    });
  });
}

test("applyDeltas shares what didn't change", () => {
  const state = deepFreeze({
    score: { 1: { team: { 1: { score: 0, player: { 1: { name: "A" } } }, 2: { score: 0 } } } },
    sets: [{ id: 1 }, { id: 2 }],
    game: { name: "Game" },
  });
  const next = client.applyDeltas(state, [
    { path: ["score", "1", "team", "1", "score"], action: "values_changed", value: 1 },
    { path: ["sets", 1, "id"], action: "values_changed", value: 3 },
  ]);
  assert.notEqual(next, state);
  assert.equal(state.score[1].team[1].score, 0);
  assert.equal(next.score[1].team[1].score, 1);
  // Copied on the changed paths
  assert.notEqual(next.score, state.score);
  assert.notEqual(next.score[1].team[1], state.score[1].team[1]);
  assert.notEqual(next.sets, state.sets);
  assert.ok(Array.isArray(next.sets));
  // Shared everywhere else
  assert.equal(next.game, state.game);
  assert.equal(next.score[1].team[2], state.score[1].team[2]);
  assert.equal(next.score[1].team[1].player, state.score[1].team[1].player);
  assert.equal(next.sets[0], state.sets[0]);
});

test("applyDeltas throws HDDeltaError on what it doesn't know", () => {
  const state = deepFreeze({ list: [1, 2] });
  for (const deltas of [
    [{ path: ["list", 0], action: "iterable_item_removed", value: 1 }],
    [{ path: ["a"], action: "values_changed" }],
    [{ path: [], action: "values_changed", value: 1 }],
    [{ path: ["__proto__", "x"], action: "dictionary_item_added", value: 1 }],
    [null],
    "deltas",
  ]) {
    assert.throws(() => client.applyDeltas(state, deltas), { name: "HDDeltaError" });
  }
  assert.equal({}.x, undefined);
});
