// Regression tests for the existing WorldClock API.
const test = require("node:test");
const assert = require("node:assert/strict");
const { WorldClock } = require("../out/dragonBones.js");

function animatable() {
    return {
        clock: null,
        updates: [],
        advanceTime(seconds) {
            this.updates.push(seconds);
        },
    };
}

test("WorldClock advances an animatable and supports removal", () => {
    const clock = new WorldClock();
    const child = animatable();
    clock.add(child);
    assert.equal(child.clock, clock);
    clock.advanceTime(0.25);
    assert.deepEqual(child.updates, [0.25]);
    clock.remove(child);
    assert.equal(child.clock, null);
    clock.advanceTime(0.5);
    assert.deepEqual(child.updates, [0.25]);
});

test("WorldClock cannot be added to itself", () => {
    const clock = new WorldClock();
    clock.add(clock);
    assert.equal(clock.clock, null);
    clock.clock = clock;
    assert.equal(clock.clock, null);
    clock.advanceTime(0.25);
    assert.equal(clock.time, 0.25);
});

test("WorldClock rejects cycles created with add", () => {
    const parent = new WorldClock();
    const child = new WorldClock();
    const leaf = animatable();
    parent.add(child);
    child.add(leaf);
    child.add(parent); // Would otherwise create recursive advanceTime calls.
    assert.equal(parent.clock, null);
    assert.equal(child.clock, parent);
    assert.equal(parent.contains(child), true);
    parent.advanceTime(0.5);
    assert.deepEqual(leaf.updates, [0.5]);
});

test("WorldClock rejects cycles created through the clock setter", () => {
    const parent = new WorldClock();
    const child = new WorldClock();
    child.clock = parent;
    parent.clock = child;
    assert.equal(parent.clock, null);
    assert.equal(child.clock, parent);
    parent.advanceTime(0.125);
    assert.equal(child.time, 0.125);
});

test("WorldClock clears all attached animatables", () => {
    const clock = new WorldClock();
    const first = animatable();
    const second = animatable();
    clock.add(first);
    clock.add(second);
    clock.clear();
    assert.equal(first.clock, null);
    assert.equal(second.clock, null);
    clock.advanceTime(0.25);
    assert.deepEqual(first.updates, []);
    assert.deepEqual(second.updates, []);
});
