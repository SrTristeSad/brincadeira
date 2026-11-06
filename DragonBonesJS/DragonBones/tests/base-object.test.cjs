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

class SharedNameA extends BaseObject {
    static toString() { return "[class dragonBones.Duplicate]"; }
    _onClear() { }
}

class SharedNameB extends BaseObject {
    static toString() { return "[class dragonBones.Duplicate]"; }
    _onClear() { }
}

class InheritedClassName extends BaseObject {
    // Inherits the BaseObject.toString() method, which deliberately throws.
    _onClear() { }
}

test("pools never mix classes with matching toString values", () => {
    const a = BaseObject.borrowObject(SharedNameA);
    a.returnToPool();
    const b = BaseObject.borrowObject(SharedNameB);
    assert.ok(b instanceof SharedNameB);
    assert.notStrictEqual(b, a);
    b.returnToPool();
    BaseObject.clearPool(SharedNameA);
    BaseObject.clearPool(SharedNameB);
});

test("borrowObject supports subclasses without a static toString override", () => {
    const child = BaseObject.borrowObject(InheritedClassName);
    assert.ok(child instanceof InheritedClassName);
    child.returnToPool();
    BaseObject.clearPool(InheritedClassName);
});

test("setMaxCount is isolated when different classes have the same string name", () => {
    BaseObject.setMaxCount(SharedNameA, 0);
    try {
        const a = BaseObject.borrowObject(SharedNameA);
        a.returnToPool();
        const b = BaseObject.borrowObject(SharedNameB);
        b.returnToPool();
        assert.strictEqual(BaseObject.borrowObject(SharedNameB), b);
    } finally {
        BaseObject.setMaxCount(SharedNameA, 3000);
        BaseObject.clearPool(SharedNameA);
        BaseObject.clearPool(SharedNameB);
    }
});
