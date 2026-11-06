// Regression coverage for animation dictionaries and inherited JS keys.
const test = require("node:test");
const assert = require("node:assert/strict");
const { Animation, BlendState, BaseObject } = require("../out/dragonBones.js");

test("blend states use own entries for special bone and slot names", () => {
    const animation = BaseObject.borrowObject(Animation);
    try {
        const proto = animation.getBlendState("boneTransform", "__proto__", animation);
        const constructorName = animation.getBlendState("boneTransform", "constructor", animation);
        const ordinary = animation.getBlendState("boneTransform", "ordinary", animation);
        assert.ok(proto instanceof BlendState);
        assert.ok(constructorName instanceof BlendState);
        assert.ok(ordinary instanceof BlendState);
        assert.notStrictEqual(proto, constructorName);
        assert.notStrictEqual(constructorName, ordinary);
        assert.strictEqual(animation.getBlendState("boneTransform", "__proto__", animation), proto);
    } finally {
        animation.returnToPool();
    }
});

test("animation catalogs ignore inherited enumerable entries", () => {
    const animation = BaseObject.borrowObject(Animation);
    try {
        const catalog = Object.create({ inheritedAnimation: { name: "should-not-copy" } });
        catalog.walk = { name: "walk" };
        Object.defineProperty(catalog, "__proto__", {
            configurable: true, enumerable: true, writable: true,
            value: { name: "__proto__" }
        });
        animation.animations = catalog;
        assert.deepEqual(Array.from(animation.animationNames).sort(), ["__proto__", "walk"]);
        assert.equal(Object.getPrototypeOf(animation.animations), null);
        assert.equal(animation.animations.inheritedAnimation, undefined);
        assert.equal(animation.animations.walk.name, "walk");
        assert.equal(animation.animations["__proto__"].name, "__proto__");
    } finally {
        animation.returnToPool();
    }
});
