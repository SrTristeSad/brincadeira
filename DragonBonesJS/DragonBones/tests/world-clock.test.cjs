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

test("WorldClock.clear discards references and does not resume removed animatables", () => {
    const clock = new WorldClock();
    const first = animatable();
    clock.add(first);
    clock.clear();
    clock.advanceTime(0.1);
    assert.deepEqual(first.updates, []);

    const second = animatable();
    clock.add(second);
    clock.advanceTime(0.2);
    assert.deepEqual(first.updates, []);
    assert.deepEqual(second.updates, [0.2]);
});

test("WorldClock.clear detaches nested clocks without clearing their own contents", () => {
    const parent = new WorldClock();
    const child = new WorldClock();
    const leaf = animatable();
    child.add(leaf);
    parent.add(child);
    parent.clear();
    assert.equal(child.clock, null);
    parent.advanceTime(0.2);
    assert.deepEqual(leaf.updates, []);
    child.advanceTime(0.3);
    assert.deepEqual(leaf.updates, [0.3]);
});

test("WorldClock.clear is safe when called during advanceTime", () => {
    const clock = new WorldClock();
    const first = {
        clock: null,
        updates: 0,
        advanceTime() {
            this.updates += 1;
            clock.clear();
        },
    };
    const later = animatable();
    clock.add(first);
    clock.add(later);
    clock.advanceTime(0.1);
    assert.equal(first.updates, 1);
    assert.deepEqual(later.updates, []);
    assert.equal(first.clock, null);
    assert.equal(later.clock, null);
    clock.advanceTime(0.2);
    assert.equal(first.updates, 1);
    assert.deepEqual(later.updates, []);
});

test("WorldClock.remove releases slots immediately outside advanceTime", () => {
    const clock = new WorldClock();
    const first = animatable();
    const second = animatable();
    clock.add(first);
    clock.add(second);
    clock.remove(first);
    assert.equal(clock._animatebles.length, 1);
    assert.strictEqual(clock._animatebles[0], second);
    clock.remove(second);
    assert.equal(clock._animatebles.length, 0);
});

test("WorldClock.clear does not retain unused slots between frames", () => {
    const clock = new WorldClock();
    for (let i = 0; i < 20; ++i) {
        const child = animatable();
        clock.add(child);
        clock.clear();
        assert.equal(clock._animatebles.length, 0);
        assert.equal(child.clock, null);
    }
});

test("WorldClock.clear compacts after a callback in the same frame", () => {
    const clock = new WorldClock();
    const later = animatable();
    const first = {
        clock: null,
        advanceTime() {
            clock.clear();
        }
    };
    clock.add(first);
    clock.add(later);
    clock.advanceTime(0.1);
    assert.equal(clock._animatebles.length, 0);
    assert.deepEqual(later.updates, []);
});

test("WorldClock cleans up correctly after a callback throws", () => {
    const clock = new WorldClock();
    const failing = {
        clock: null,
        advanceTime() {
            throw new Error("expected test exception");
        }
    };
    clock.add(failing);
    assert.throws(() => clock.advanceTime(0.1), /expected test exception/);
    clock.clear();
    assert.equal(clock._animatebles.length, 0);
});

test("WorldClock reentrant updates do not compact the active iteration", () => {
    const clock = new WorldClock();
    let reentered = false;
    const item = {
        clock: null,
        calls: 0,
        advanceTime() {
            this.calls++;
            if (!reentered) {
                reentered = true;
                clock.advanceTime(0.1);
                clock.remove(this);
            }
        }
    };
    clock.add(item);
    clock.advanceTime(0.1);
    assert.equal(item.calls, 2);
    assert.equal(item.clock, null);
    assert.equal(clock._animatebles.length, 0);
});

test("moving a plain IAnimatable between clocks removes its old owner", () => {
    const original = new WorldClock();
    const destination = new WorldClock();
    const child = animatable();

    original.add(child);
    destination.add(child);

    assert.equal(child.clock, destination);
    original.advanceTime(0.25);
    destination.advanceTime(0.5);
    assert.deepEqual(child.updates, [0.5]);
});

test("moving an animatable during an update does not advance it twice", () => {
    const original = new WorldClock();
    const destination = new WorldClock();
    const child = animatable();
    const transfer = {
        clock: null,
        advanceTime() {
            destination.add(child);
        }
    };

    original.add(transfer);
    original.add(child);
    original.advanceTime(0.25);
    destination.advanceTime(0.5);

    assert.equal(child.clock, destination);
    assert.deepEqual(child.updates, [0.5]);
});

test("readding an animatable to its current owner does not duplicate updates", () => {
    const clock = new WorldClock();
    const child = animatable();
    clock.add(child);
    clock.add(child);
    clock.advanceTime(0.25);
    assert.deepEqual(child.updates, [0.25]);
});
