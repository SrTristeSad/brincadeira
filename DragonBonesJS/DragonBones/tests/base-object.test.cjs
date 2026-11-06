// Regression tests for object-pool safety; uses only the public BaseObject API.
const test = require("node:test");
const assert = require("node:assert/strict");
const { BaseObject } = require("../out/dragonBones.js");

class TrackedObject extends BaseObject {
    static toString() { return "[class dragonBones.TestTrackedObject]"; }
    constructor() {
        super();
        this.clears = 0;
    }
    _onClear() { this.clears += 1; }
}

class PrototypeKeyObject extends BaseObject {
    static toString() { return "__proto__"; }
    _onClear() { }
}

test("borrowed objects are cleared once and reused", () => {
    const first = BaseObject.borrowObject(TrackedObject);
    assert.equal(first.clears, 1);
    first.returnToPool();
    assert.equal(first.clears, 2);
    const second = BaseObject.borrowObject(TrackedObject);
    assert.strictEqual(second, first);
    assert.equal(second.clears, 2);
    BaseObject.clearPool(TrackedObject);
});

test("returning an object twice does not clear it twice", () => {
    const object = BaseObject.borrowObject(TrackedObject);
    const before = object.clears;
    object.returnToPool();
    assert.equal(object.clears, before + 1);
    object.returnToPool();
    assert.equal(object.clears, before + 1);
    BaseObject.clearPool(TrackedObject);
});

test("pool dictionaries safely handle inherited JavaScript object keys", () => {
    const first = BaseObject.borrowObject(PrototypeKeyObject);
    first.returnToPool();
    const second = BaseObject.borrowObject(PrototypeKeyObject);
    assert.strictEqual(second, first);
    BaseObject.clearPool(PrototypeKeyObject);
});
