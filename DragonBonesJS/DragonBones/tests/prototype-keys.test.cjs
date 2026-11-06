// Regression tests for names that collide with Object.prototype properties.
const test = require("node:test");
const assert = require("node:assert/strict");
const { BaseObject, ArmatureData, DragonBonesData, BoneData, AnimationData, SkinData } =
    require("../out/dragonBones.js");

test("ArmatureData does not mistake inherited properties for bones", () => {
    const armature = BaseObject.borrowObject(ArmatureData);
    assert.equal(armature.getBone("__proto__"), null);
    assert.equal(armature.getBone("constructor"), null);
    const bone = BaseObject.borrowObject(BoneData);
    bone.name = "__proto__";
    armature.addBone(bone);
    assert.strictEqual(armature.getBone("__proto__"), bone);
    armature.returnToPool();
});

test("ArmatureData preserves animation names matching Object.prototype", () => {
    const armature = BaseObject.borrowObject(ArmatureData);
    assert.equal(armature.getAnimation("toString"), null);
    const animation = BaseObject.borrowObject(AnimationData);
    animation.name = "constructor";
    armature.addAnimation(animation);
    assert.strictEqual(armature.getAnimation("constructor"), animation);
    assert.deepEqual(armature.animationNames, ["constructor"]);
    armature.returnToPool();
});

test("DragonBonesData resolves armature names without prototype collisions", () => {
    const data = BaseObject.borrowObject(DragonBonesData);
    assert.equal(data.getArmature("toString"), null);
    const armature = BaseObject.borrowObject(ArmatureData);
    armature.name = "__proto__";
    data.addArmature(armature);
    assert.strictEqual(data.getArmature("__proto__"), armature);
    assert.deepEqual(data.armatureNames, ["__proto__"]);
    data.returnToPool();
});

test("SkinData accepts slots named as inherited properties", () => {
    const skin = BaseObject.borrowObject(SkinData);
    assert.equal(skin.getDisplays("__proto__"), null);
    skin.addDisplay("__proto__", null);
    assert.deepEqual(skin.getDisplays("__proto__"), [null]);
    skin.returnToPool();
});
