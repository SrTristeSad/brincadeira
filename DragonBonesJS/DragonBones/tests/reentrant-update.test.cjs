// Reentrant advanceTime calls must not dispatch or dispose the same entry twice.
const test = require("node:test");
const assert = require("node:assert/strict");
const { DragonBones, EventObject, BaseObject } = require("../out/dragonBones.js");

function createEvent(type, dispatch) {
    const event = BaseObject.borrowObject(EventObject);
    event.type = type;
    event.armature = {
        _armatureData: {},
        eventDispatcher: { dispatchDBEvent: dispatch }
    };
    return event;
}

test("reentrant animation event dispatch does not repeat the current event", () => {
    const engine = new DragonBones({ dispatchDBEvent() {} });
    const calls = [];
    engine.bufferEvent(createEvent(EventObject.FRAME_EVENT, () => {
        calls.push("first");
        engine.advanceTime(0);
    }));
    engine.bufferEvent(createEvent(EventObject.COMPLETE, () => calls.push("second")));

    engine.advanceTime(0);
    engine.advanceTime(0);
    assert.deepEqual(calls, ["first", "second"]);
});

test("reentrant sound manager dispatch handles a sound once", () => {
    let engine;
    let calls = 0;
    engine = new DragonBones({
        dispatchDBEvent() {
            calls++;
            engine.advanceTime(0);
        }
    });
    engine.bufferEvent(createEvent(EventObject.SOUND_EVENT, () => {}));

    engine.advanceTime(0);
    engine.advanceTime(0);
    assert.equal(calls, 1);
});

test("reentrant pool cleanup never clears the same object twice", () => {
    const engine = new DragonBones({ dispatchDBEvent() {} });
    const calls = [];
    engine.bufferObject({
        returnToPool() {
            calls.push("first");
            engine.advanceTime(0);
        }
    });
    engine.bufferObject({ returnToPool() { calls.push("second"); } });

    engine.advanceTime(0);
    engine.advanceTime(0);
    assert.deepEqual(calls, ["first", "second"]);
});

test("events added during a reentrant callback still run in the same update", () => {
    const engine = new DragonBones({ dispatchDBEvent() {} });
    const calls = [];
    const added = createEvent(EventObject.COMPLETE, () => calls.push("added"));
    engine.bufferEvent(createEvent(EventObject.FRAME_EVENT, () => {
        calls.push("first");
        engine.bufferEvent(added);
        engine.advanceTime(0);
    }));

    engine.advanceTime(0);
    assert.deepEqual(calls, ["first", "added"]);
});

test("a throwing reentrant event callback releases its guard and keeps pending events", () => {
    const engine = new DragonBones({ dispatchDBEvent() {} });
    const calls = [];
    engine.bufferEvent(createEvent(EventObject.FRAME_EVENT, () => {
        calls.push("failed");
        engine.advanceTime(0);
        throw new Error("listener failure");
    }));
    engine.bufferEvent(createEvent(EventObject.COMPLETE, () => calls.push("pending")));

    assert.throws(() => engine.advanceTime(0), /listener failure/);
    engine.advanceTime(0);
    engine.advanceTime(0);
    assert.deepEqual(calls, ["failed", "pending"]);
});

test("a throwing reentrant pool cleanup preserves the remaining entries", () => {
    const engine = new DragonBones({ dispatchDBEvent() {} });
    const calls = [];
    engine.bufferObject({
        returnToPool() {
            calls.push("failed");
            engine.advanceTime(0);
            throw new Error("pool failure");
        }
    });
    engine.bufferObject({ returnToPool() { calls.push("pending"); } });

    assert.throws(() => engine.advanceTime(0), /pool failure/);
    engine.advanceTime(0);
    engine.advanceTime(0);
    assert.deepEqual(calls, ["failed", "pending"]);
});
