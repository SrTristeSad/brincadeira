// Ensure animation replacement never imports inherited animation entries.
const test = require("node:test");
const assert = require("node:assert/strict");
const { BaseFactory } = require("../out/dragonBones.js");

function makeArmature(animations) {
    return { animation: { animations }, getSlots: () => [] };
}

test("non-override animation replacement ignores prototype properties", () => {
    const existing = Object.create({ inheritedExisting: { name: "invalid" } });
    existing.walk = { name: "walk" };
    const incoming = Object.create({ inheritedIncoming: { name: "invalid" } });
    incoming.run = { name: "run" };
    Object.defineProperty(incoming, "__proto__", {
        enumerable: true,
        value: { name: "special" }
    });
    const armature = makeArmature(existing);
    const data = { defaultSkin: {}, animations: incoming };
    const ok = BaseFactory.prototype.replaceAnimation.call({}, armature, data, false);

    assert.equal(ok, true);
    assert.deepEqual(Object.keys(armature.animation.animations).sort(), ["__proto__", "run", "walk"]);
    assert.equal(Object.getPrototypeOf(armature.animation.animations), null);
    assert.equal(armature.animation.animations["__proto__"].name, "special");
});

test("replacement animations still override previous entries with the same name", () => {
    const old = Object.create(null);
    old.walk = { name: "old" };
    const incoming = Object.create(null);
    incoming.walk = { name: "new" };
    const armature = makeArmature(old);
    const data = { defaultSkin: {}, animations: incoming };

    assert.equal(BaseFactory.prototype.replaceAnimation.call({}, armature, data, false), true);
    assert.strictEqual(armature.animation.animations.walk, incoming.walk);
});

test("override mode still keeps the provided animation catalog", () => {
    const source = Object.create(null);
    source.idle = { name: "idle" };
    const armature = makeArmature(Object.create(null));
    const data = { defaultSkin: {}, animations: source };

    assert.equal(BaseFactory.prototype.replaceAnimation.call({}, armature, data, true), true);
    assert.strictEqual(armature.animation.animations, source);
});
