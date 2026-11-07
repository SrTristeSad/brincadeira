// Ensures the TypeScript-generated ES5 inheritance helper is not overridden.
const test = require("node:test");
const assert = require("node:assert/strict");
const {
    BaseObject,
    BoneData,
    SurfaceData,
    ArmatureData,
    AnimationData
} = require("../out/dragonBones.js");

test("ES5 classes preserve the static constructor inheritance chain", () => {
    for (const Derived of [BoneData, ArmatureData, AnimationData]) {
        assert.strictEqual(Object.getPrototypeOf(Derived), BaseObject);
    }
    assert.strictEqual(Object.getPrototypeOf(SurfaceData), BoneData);
});

test("derived classes inherit static members added to their parent", () => {
    // A symbol avoids colliding with any public DragonBones API name.
    const marker = Symbol("static-inheritance-test");
    const check = () => "inherited";
    Object.defineProperty(BaseObject, marker, {
        configurable: true,
        value: check,
    });
    try {
        assert.strictEqual(BoneData[marker], check);
        assert.strictEqual(ArmatureData[marker], check);
        assert.strictEqual(SurfaceData[marker], check);
    } finally {
        delete BaseObject[marker];
    }
});
