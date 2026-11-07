// Pending pooled objects must survive failure during returnToPool().
const test = require("node:test");
const assert = require("node:assert/strict");
const { DragonBones } = require("../out/dragonBones.js");

function createEngine() {
    return new DragonBones({ dispatchDBEvent() {} });
}

test("successfully returned objects are not cleared a second time", () => {
    const engine = createEngine();
    let count = 0;
    engine.bufferObject({ returnToPool() { count++; } });

    engine.advanceTime(0);
    engine.advanceTime(0);
    assert.equal(count, 1);
});

test("an exception in returnToPool does not replay the failed entry", () => {
    const engine = createEngine();
    const order = [];
    engine.bufferObject({
        returnToPool() {
            order.push("failed");
            throw new Error("clear failed");
        }
    });
    engine.bufferObject({ returnToPool() { order.push("pending"); } });

    assert.throws(() => engine.advanceTime(0), /clear failed/);
    engine.advanceTime(0);
    engine.advanceTime(0);
    assert.deepEqual(order, ["failed", "pending"]);
});

test("object cleanup still drains objects appended during the same frame", () => {
    const engine = createEngine();
    const order = [];
    engine.bufferObject({
        returnToPool() {
            order.push("first");
            engine.bufferObject({
                returnToPool() { order.push("added"); }
            });
        }
    });

    engine.advanceTime(0);
    assert.deepEqual(order, ["first", "added"]);
    engine.advanceTime(0);
    assert.deepEqual(order, ["first", "added"]);
});

test("failed cleanup preserves objects added by the failing callback", () => {
    const engine = createEngine();
    const order = [];
    engine.bufferObject({
        returnToPool() {
            order.push("failed");
            engine.bufferObject({ returnToPool() { order.push("added"); } });
            throw new Error("pool failure");
        }
    });
    engine.bufferObject({ returnToPool() { order.push("pending"); } });

    assert.throws(() => engine.advanceTime(0), /pool failure/);
    engine.advanceTime(0);
    engine.advanceTime(0);
    assert.deepEqual(order, ["failed", "pending", "added"]);
});
