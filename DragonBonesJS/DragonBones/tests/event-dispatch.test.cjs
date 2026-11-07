// Event dispatch must remain safe when a listener fails midway through a frame.
const test = require("node:test");
const assert = require("node:assert/strict");
const { DragonBones, EventObject, BaseObject } = require("../out/dragonBones.js");

function makeEvent(type, dispatch) {
    const event = BaseObject.borrowObject(EventObject);
    event.type = type;
    event.armature = {
        _armatureData: {},
        eventDispatcher: { dispatchDBEvent: dispatch }
    };
    return event;
}

test("normal dispatch releases processed events on the next update", () => {
    const calls = [];
    const engine = new DragonBones({ dispatchDBEvent() {} });
    const first = makeEvent(EventObject.FRAME_EVENT, () => calls.push("first"));
    const second = makeEvent(EventObject.COMPLETE, () => calls.push("second"));
    engine.bufferEvent(first);
    engine.bufferEvent(second);

    engine.advanceTime(0);
    assert.deepEqual(calls, ["first", "second"]);
    engine.advanceTime(0);
    assert.equal(first.armature, null);
    assert.equal(second.armature, null);
});

test("a throwing animation callback cannot cause a duplicate dispatch", () => {
    const calls = [];
    const engine = new DragonBones({ dispatchDBEvent() {} });
    const first = makeEvent(EventObject.FRAME_EVENT, () => {
        calls.push("first");
        throw new Error("listener failed");
    });
    const second = makeEvent(EventObject.COMPLETE, () => calls.push("second"));
    engine.bufferEvent(first);
    engine.bufferEvent(second);

    assert.throws(() => engine.advanceTime(0), /listener failed/);
    engine.advanceTime(0);
    engine.advanceTime(0);
    assert.deepEqual(calls, ["first", "second"]);
    assert.equal(first.armature, null);
    assert.equal(second.armature, null);
});

test("a throwing sound listener leaves subsequent events pending", () => {
    const calls = [];
    const engine = new DragonBones({
        dispatchDBEvent() { throw new Error("audio failed"); }
    });
    const sound = makeEvent(EventObject.SOUND_EVENT, () => calls.push("sound"));
    const later = makeEvent(EventObject.COMPLETE, () => calls.push("later"));
    engine.bufferEvent(sound);
    engine.bufferEvent(later);

    assert.throws(() => engine.advanceTime(0), /audio failed/);
    engine.advanceTime(0);
    engine.advanceTime(0);
    assert.deepEqual(calls, ["sound", "later"]);
    assert.equal(sound.armature, null);
    assert.equal(later.armature, null);
});

test("event callbacks can still queue another event in the same frame", () => {
    const calls = [];
    const engine = new DragonBones({ dispatchDBEvent() {} });
    const later = makeEvent(EventObject.COMPLETE, () => calls.push("later"));
    const first = makeEvent(EventObject.FRAME_EVENT, () => {
        calls.push("first");
        engine.bufferEvent(later);
    });
    engine.bufferEvent(first);

    engine.advanceTime(0);
    assert.deepEqual(calls, ["first", "later"]);
    engine.advanceTime(0);
    assert.equal(first.armature, null);
    assert.equal(later.armature, null);
});
