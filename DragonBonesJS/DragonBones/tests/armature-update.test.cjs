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
