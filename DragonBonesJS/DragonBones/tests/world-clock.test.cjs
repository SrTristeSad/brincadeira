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

test("moving a nested WorldClock detaches its previous owner", () => {
    const original = new WorldClock();
    const destination = new WorldClock();
    const nested = new WorldClock();
    const leaf = animatable();

    nested.add(leaf);
    original.add(nested);
    destination.add(nested);
    assert.equal(nested.clock, destination);

    original.advanceTime(0.25);
    destination.advanceTime(0.5);
    assert.deepEqual(leaf.updates, [0.5]);
});

test("WorldClock rejects three-level cycles created with add", () => {
    const root = new WorldClock();
    const middle = new WorldClock();
    const leaf = new WorldClock();
    root.add(middle);
    middle.add(leaf);
    leaf.add(root);
    assert.equal(root.clock, null);
    assert.equal(middle.clock, root);
    assert.equal(leaf.clock, middle);
    root.advanceTime(0.25);
    assert.equal(leaf.time, 0.25);
});

test("WorldClock rejects three-level cycles created with the clock setter", () => {
    const root = new WorldClock();
    const middle = new WorldClock();
    const leaf = new WorldClock();
    middle.clock = root;
    leaf.clock = middle;
    root.clock = leaf;
    assert.equal(root.clock, null);
    assert.equal(middle.clock, root);
    assert.equal(leaf.clock, middle);
    root.advanceTime(0.2);
    assert.equal(leaf.time, 0.2);
});

test("WorldClock.contains safely rejects an external self-cycle", () => {
    const owner = new WorldClock();
    const broken = new WorldClock();
    // Simulate corrupt clock data supplied by an external runtime.
    Object.defineProperty(broken, "clock", { configurable: true, value: broken });
    assert.equal(owner.contains(broken), false);
});

test("WorldClock.contains safely rejects an external two-clock cycle", () => {
    const owner = new WorldClock();
    const first = new WorldClock();
    const second = new WorldClock();
    Object.defineProperty(first, "clock", { configurable: true, value: second });
    Object.defineProperty(second, "clock", { configurable: true, value: first });
    assert.equal(owner.contains(first), false);
    assert.equal(owner.contains(second), false);
});

test("WorldClock.contains preserves normal descendant and self behavior", () => {
    const root = new WorldClock();
    const child = new WorldClock();
    const grandchild = new WorldClock();
    root.add(child);
    child.add(grandchild);
    assert.equal(root.contains(grandchild), true);
    assert.equal(grandchild.contains(root), false);
    assert.equal(root.contains(root), false);
    grandchild.add(root);
    assert.equal(root.clock, null);
    assert.equal(grandchild.clock, child);
});

test("WorldClock.clear retains newly added members from a clock setter", () => {
    const clock = new WorldClock();
    const replacement = animatable();
    const original = {
        _owner: null,
        updates: [],
        get clock() { return this._owner; },
        set clock(value) {
            this._owner = value;
            if (value === null) {
                clock.add(replacement);
            }
        },
        advanceTime(time) { this.updates.push(time); }
    };

    clock.add(original);
    clock.clear();
    assert.equal(original.clock, null);
    assert.equal(replacement.clock, clock);
    clock.advanceTime(0.25);
    assert.deepEqual(original.updates, []);
    assert.deepEqual(replacement.updates, [0.25]);
});

test("WorldClock.clear compacts entries after a clock setter fails", () => {
    const clock = new WorldClock();
    const first = {
        _owner: null,
        get clock() { return this._owner; },
        set clock(value) {
            this._owner = value;
            if (value === null) {
                throw new Error("detach failure");
            }
        },
        advanceTime() {}
    };
    const second = animatable();
    clock.add(first);
    clock.add(second);

    assert.throws(() => clock.clear(), /detach failure/);
    assert.equal(first.clock, null);
    assert.equal(second.clock, clock);
    assert.equal(clock.contains(second), true);
    clock.advanceTime(0.2);
    assert.deepEqual(second.updates, [0.2]);
    clock.remove(second);
    assert.equal(clock._animatebles.length, 0);
});

test("WorldClock.clear during an update preserves new members for the next frame", () => {
    const clock = new WorldClock();
    const replacement = animatable();
    const original = {
        _owner: null,
        get clock() { return this._owner; },
        set clock(value) {
            this._owner = value;
            if (value === null) {
                clock.add(replacement);
            }
        },
        advanceTime() { clock.clear(); }
    };

    clock.add(original);
    clock.advanceTime(0.2);
    assert.deepEqual(replacement.updates, []);
    clock.advanceTime(0.3);
    assert.deepEqual(replacement.updates, [0.3]);
});

test("nested WorldClock.clear detaches existing members without losing new ones", () => {
    const clock = new WorldClock();
    const second = animatable();
    const replacement = animatable();
    const original = {
        _owner: null,
        get clock() { return this._owner; },
        set clock(value) {
            this._owner = value;
            if (value === null) {
                clock.clear();
                clock.add(replacement);
            }
        },
        advanceTime() {}
    };

    clock.add(original);
    clock.add(second);
    clock.clear();
    assert.equal(original.clock, null);
    assert.equal(second.clock, null);
    assert.equal(replacement.clock, clock);
    clock.advanceTime(0.1);
    assert.deepEqual(replacement.updates, [0.1]);
});

test("WorldClock.clear continues releasing all ordinary members", () => {
    const clock = new WorldClock();
    const first = animatable();
    const second = animatable();
    clock.add(first);
    clock.add(second);
    clock.clear();
    assert.equal(first.clock, null);
    assert.equal(second.clock, null);
    assert.equal(clock._animatebles.length, 0);
});

test("WorldClock.add rolls back members whose clock setter throws", () => {
    const clock = new WorldClock();
    let updates = 0;
    const rejected = {
        owner: null,
        get clock() { return this.owner; },
        set clock(value) {
            if (value !== null) {
                throw new Error("cannot attach");
            }
            this.owner = null;
        },
        advanceTime() { updates++; }
    };

    assert.throws(() => clock.add(rejected), /cannot attach/);
    assert.equal(clock._animatebles.length, 0);
    clock.advanceTime(0.2);
    assert.equal(updates, 0);
});

test("WorldClock.add does not track members that refuse ownership", () => {
    const clock = new WorldClock();
    let updates = 0;
    const refused = {
        get clock() { return null; },
        set clock(value) { /* Ignore rejected ownership. */ },
        advanceTime() { updates++; }
    };

    clock.add(refused);
    assert.equal(clock._animatebles.length, 0);
    clock.advanceTime(0.5);
    assert.equal(updates, 0);
});

test("WorldClock.add rolls back failed registrations during advanceTime", () => {
    const clock = new WorldClock();
    let updates = 0;
    let attempt = true;
    const rejected = {
        get clock() { return null; },
        set clock(value) {
            if (value !== null) {
                throw new Error("failed during frame");
            }
        },
        advanceTime() { updates++; }
    };
    const trigger = {
        clock: null,
        advanceTime() {
            if (attempt) {
                attempt = false;
                clock.add(rejected);
            }
        }
    };
    clock.add(trigger);
    assert.throws(() => clock.advanceTime(0.1), /failed during frame/);
    assert.deepEqual(clock._animatebles, [trigger]);
    clock.advanceTime(0.2);
    assert.equal(updates, 0);
});

test("WorldClock.add does not retain a member when its setter throws after assignment", () => {
    const clock = new WorldClock();
    let updates = 0;
    const rejected = {
        owner: null,
        get clock() { return this.owner; },
        set clock(value) {
            this.owner = value;
            if (value !== null) {
                throw new Error("after assignment");
            }
        },
        advanceTime() { updates++; }
    };

    assert.throws(() => clock.add(rejected), /after assignment/);
    assert.equal(clock._animatebles.length, 0);
    clock.advanceTime(0.25);
    assert.equal(updates, 0);
});

test("WorldClock ignores infinite elapsed time and recovers on the next update", () => {
    const clock = new WorldClock();
    const child = animatable();
    clock.add(child);
    clock.advanceTime(Infinity);
    assert.equal(clock.time, 0);
    assert.deepEqual(child.updates, []);
    clock.advanceTime(0.25);
    assert.equal(clock.time, 0.25);
    assert.deepEqual(child.updates, [0.25]);
});

test("WorldClock rejects non-finite timeScale without poisoning later updates", () => {
    const clock = new WorldClock();
    const child = animatable();
    clock.add(child);
    for (const scale of [NaN, Infinity, -Infinity]) {
        clock.timeScale = scale;
        clock.advanceTime(0.5);
        assert.equal(clock.time, 0);
        assert.deepEqual(child.updates, []);
    }
    clock.timeScale = 1;
    clock.advanceTime(0.5);
    assert.equal(clock.time, 0.5);
    assert.deepEqual(child.updates, [0.5]);
});

test("WorldClock prevents overflow when finite time values are multiplied", () => {
    const clock = new WorldClock();
    const child = animatable();
    clock.add(child);
    clock.timeScale = Number.MAX_VALUE;
    clock.advanceTime(Number.MAX_VALUE);
    assert.equal(clock.time, 0);
    assert.deepEqual(child.updates, []);
    clock.timeScale = 1;
    clock.advanceTime(1);
    assert.equal(clock.time, 1);
    assert.deepEqual(child.updates, [1]);
});

test("WorldClock still supports finite negative timeScale", () => {
    const clock = new WorldClock();
    const child = animatable();
    clock.add(child);
    clock.timeScale = -2;
    clock.advanceTime(0.25);
    assert.equal(clock.time, 0.5);
    assert.deepEqual(child.updates, [-0.5]);
    clock.timeScale = 1;
    clock.advanceTime(0.25);
    assert.equal(clock.time, 0.75);
    assert.deepEqual(child.updates, [-0.5, 0.25]);
});
