const test = require("node:test");
const assert = require("node:assert/strict");
const { BaseObject, ArmatureData, BoneData, IKConstraintData } =
    require("../out/dragonBones.js");

function bone(name) {
    const data = BaseObject.borrowObject(BoneData);
    data.name = name;
    return data;
}

test("sortBones preserves valid parent and constraint order", () => {
    const armature = BaseObject.borrowObject(ArmatureData);
    const root = bone("root");
    const child = bone("child");
    const target = bone("target");
    const constrained = bone("constrained");
    child.parent = root;

    armature.addBone(constrained);
    armature.addBone(child);
    armature.addBone(target);
    armature.addBone(root);

    const ik = BaseObject.borrowObject(IKConstraintData);
    ik.name = "ik";
    ik.root = constrained;
    ik.target = target;
    armature.addConstraint(ik);

    const publicArray = armature.sortedBones;
    armature.sortBones();
    assert.strictEqual(armature.sortedBones, publicArray);
    assert.deepEqual(armature.sortedBones.map(value => value.name),
        ["target", "root", "constrained", "child"]);

    armature.sortBones();
    assert.deepEqual(armature.sortedBones.map(value => value.name),
        ["target", "root", "constrained", "child"]);
    armature.returnToPool();
});

test("sortBones rejects circular parent relationships without losing bone data", () => {
    const armature = BaseObject.borrowObject(ArmatureData);
    const first = bone("first");
    const second = bone("second");
    first.parent = second;
    second.parent = first;
    armature.addBone(first);
    armature.addBone(second);

    const initial = armature.sortedBones.slice();
    assert.throws(() => armature.sortBones(), /cyclic or unresolved/);
    assert.deepEqual(armature.sortedBones, initial);
    armature.returnToPool();
});

test("sortBones rejects absent parent references and preserves original ordering", () => {
    const armature = BaseObject.borrowObject(ArmatureData);
    const dependent = bone("dependent");
    const missing = bone("missing");
    dependent.parent = missing;
    armature.addBone(dependent);

    assert.throws(() => armature.sortBones(), /cyclic or unresolved/);
    assert.deepEqual(armature.sortedBones, [dependent]);
    armature.returnToPool();
    missing.returnToPool();
});

test("sortBones rejects cyclic constraint dependencies without partial sorting", () => {
    const armature = BaseObject.borrowObject(ArmatureData);
    const first = bone("first");
    const second = bone("second");
    armature.addBone(first);
    armature.addBone(second);

    const firstConstraint = BaseObject.borrowObject(IKConstraintData);
    firstConstraint.name = "firstConstraint";
    firstConstraint.root = first;
    firstConstraint.target = second;
    armature.addConstraint(firstConstraint);

    const secondConstraint = BaseObject.borrowObject(IKConstraintData);
    secondConstraint.name = "secondConstraint";
    secondConstraint.root = second;
    secondConstraint.target = first;
    armature.addConstraint(secondConstraint);

    const initial = armature.sortedBones.slice();
    assert.throws(() => armature.sortBones(), /cyclic or unresolved/);
    assert.deepEqual(armature.sortedBones, initial);
    armature.returnToPool();
});
