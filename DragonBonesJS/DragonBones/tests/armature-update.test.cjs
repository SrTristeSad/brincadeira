// Regression tests for armature update guards after a failed frame.
const test = require("node:test");
const assert = require("node:assert/strict");
const { Armature } = require("../out/dragonBones.js");

function makeArmature(update) {
    // Exercise the real advanceTime prototype without constructing display
    // adapters, textures or a rendering backend.
    const armature = Object.create(Armature.prototype);
    armature._lockUpdate = false;
    armature._armatureData = { parent: {} };
    armature._animation = { advanceTime: update || (() => {}) };
    armature._proxy = { dbUpdate() {} };
    armature._slotsDirty = false;
    armature._zIndexDirty = false;
    armature._alphaDirty = false;
    armature._cacheFrameIndex = 0;
    armature._bones = [];
    armature._slots = [];
    armature._actions = [];
    return armature;
}

test("a failed animation update releases the lock and allows the next frame", () => {
    let calls = 0;
    const armature = makeArmature(() => {
        calls++;
        if (calls === 1) {
            throw new Error("animation failure");
        }
    });
    assert.throws(() => armature.advanceTime(0.1), /animation failure/);
    assert.equal(armature._lockUpdate, false);
    armature.advanceTime(0.2);
    assert.equal(calls, 2);
});

test("an unavailable armature data parent does not lock updates forever", () => {
    let calls = 0;
    const armature = makeArmature(() => calls++);
    const previousWarn = console.warn;
    try {
        console.warn = () => {};
        armature._armatureData.parent = null;
        armature.advanceTime(0.1);
    }
    finally {
        console.warn = previousWarn;
    }
    assert.equal(armature._lockUpdate, false);
    armature._armatureData.parent = {};
    armature.advanceTime(0.2);
    assert.equal(calls, 1);
});

test("a disposed armature does not keep the transient update lock", () => {
    const armature = makeArmature();
    armature._armatureData = null;
    const previousWarn = console.warn;
    try {
        console.warn = () => {};
        armature.advanceTime(0.1);
    }
    finally {
        console.warn = previousWarn;
    }
    assert.equal(armature._lockUpdate, false);
});

test("a failing bone update releases the lock", () => {
    const armature = makeArmature();
    armature._cacheFrameIndex = -1;
    armature._bones = [{ update() { throw new Error("bone failure"); } }];
    assert.throws(() => armature.advanceTime(0.1), /bone failure/);
    assert.equal(armature._lockUpdate, false);
    armature._bones = [];
    armature.advanceTime(0.1);
});

test("the proxy callback runs after the update lock is released", () => {
    const armature = makeArmature();
    let unlocked = false;
    armature._proxy.dbUpdate = () => { unlocked = !armature._lockUpdate; };
    armature.advanceTime(0.1);
    assert.equal(unlocked, true);
});

test("nested animation updates remain blocked while the outer update runs", () => {
    let calls = 0;
    const armature = makeArmature(() => {
        calls++;
        armature.advanceTime(0.1);
    });
    armature.advanceTime(0.1);
    assert.equal(calls, 1);
    assert.equal(armature._lockUpdate, false);
});

function queuedAction(name, released, type = 0) {
    return {
        actionData: { name, type },
        slot: null,
        bone: null,
        returnToPool() {
            released.push(name);
            this.actionData = null;
        }
    };
}

test("a failing fadeIn releases only the processed action and keeps later actions", () => {
    const armature = makeArmature();
    const played = [];
    const released = [];
    const first = queuedAction("first", released);
    const pending = queuedAction("pending", released);
    armature._actions.push(first, pending);
    armature._animation.fadeIn = name => {
        played.push(name);
        if (name === "first") throw new Error("fadeIn failed");
    };

    assert.throws(() => armature.advanceTime(0.1), /fadeIn failed/);
    assert.equal(armature._lockUpdate, false);
    assert.deepEqual(armature._actions, [pending]);
    assert.deepEqual(released, ["first"]);
    armature.advanceTime(0.2);
    assert.deepEqual(played, ["first", "pending"]);
    assert.deepEqual(released, ["first", "pending"]);
    assert.deepEqual(armature._actions, []);
});

test("actions inserted at the front during playback run without repeats", () => {
    const armature = makeArmature();
    const played = [];
    const released = [];
    armature._actions.push(queuedAction("first", released), queuedAction("last", released));
    armature._animation.fadeIn = name => {
        played.push(name);
        if (name === "first") {
            armature._bufferAction(queuedAction("urgent", released), false);
        }
    };

    armature.advanceTime(0.1);
    assert.deepEqual(played, ["first", "urgent", "last"]);
    assert.deepEqual(released, ["first", "urgent", "last"]);
    assert.deepEqual(armature._actions, []);
});

test("actions appended during playback run in the same frame", () => {
    const armature = makeArmature();
    const played = [];
    const released = [];
    armature._actions.push(queuedAction("first", released));
    armature._animation.fadeIn = name => {
        played.push(name);
        if (name === "first") {
            armature._bufferAction(queuedAction("added", released), true);
        }
    };

    armature.advanceTime(0.1);
    assert.deepEqual(played, ["first", "added"]);
    assert.deepEqual(released, ["first", "added"]);
});

test("a failed returnToPool does not replay the action on the next frame", () => {
    const armature = makeArmature();
    const played = [];
    const released = [];
    const failed = queuedAction("failed", released);
    failed.returnToPool = () => {
        released.push("failed");
        throw new Error("pool failed");
    };
    armature._actions.push(failed, queuedAction("pending", released));
    armature._animation.fadeIn = name => played.push(name);

    assert.throws(() => armature.advanceTime(0.1), /pool failed/);
    assert.deepEqual(armature._actions.map(action => action.actionData.name), ["pending"]);
    armature.advanceTime(0.2);
    assert.deepEqual(played, ["failed", "pending"]);
    assert.deepEqual(released, ["failed", "pending"]);
});

test("non-play actions are still returned to the pool", () => {
    const armature = makeArmature();
    const released = [];
    let faded = 0;
    armature._animation.fadeIn = () => faded++;
    armature._actions.push(queuedAction("sound", released, 11));

    armature.advanceTime(0.1);
    assert.equal(faded, 0);
    assert.deepEqual(released, ["sound"]);
    assert.deepEqual(armature._actions, []);
});
