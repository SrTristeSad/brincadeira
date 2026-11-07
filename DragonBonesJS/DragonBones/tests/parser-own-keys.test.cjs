const test = require("node:test");
const assert = require("node:assert/strict");
const { ObjectDataParser } = require("../out/dragonBones.js");

// The real parser method is exercised with only its frame-buffer dependencies.
function makeParser() {
    const parser = Object.create(ObjectDataParser.prototype);
    parser._frameIntArray = [];
    parser._colorArray = [];
    parser._defaultColorOffset = -1;
    parser._parseTweenFrame = () => 3;
    parser._helpColorTransform = {
        alphaMultiplier: 1,
        redMultiplier: 1,
        greenMultiplier: 1,
        blueMultiplier: 1,
        alphaOffset: 0,
        redOffset: 0,
        greenOffset: 0,
        blueOffset: 0
    };
    return parser;
}

test("slot colors ignore inherited-only values and reuse the default color", () => {
    const parser = makeParser();
    parser._parseColorTransform = () => {
        throw new Error("inherited color values must not be parsed");
    };
    const inheritedColor = Object.create({ redMultiplier: 0.3 });
    assert.equal(parser._parseSlotColorFrame({ value: inheritedColor }, 0, 1), 3);
    assert.deepEqual(parser._colorArray, [100, 100, 100, 100, 0, 0, 0, 0]);
    assert.deepEqual(parser._frameIntArray, [0]);
    assert.equal(parser._parseSlotColorFrame({ value: {} }, 0, 1), 3);
    assert.equal(parser._colorArray.length, 8, "default color should be reused");
});

test("slot colors still parse explicit own values", () => {
    const parser = makeParser();
    let calls = 0;
    parser._parseColorTransform = (value, target) => {
        calls++;
        target.redMultiplier = value.redMultiplier;
    };
    assert.equal(parser._parseSlotColorFrame({ value: { redMultiplier: 0.5 } }, 0, 1), 3);
    assert.equal(calls, 1);
    assert.deepEqual(parser._colorArray, [100, 50, 100, 100, 0, 0, 0, 0]);
});
