// Validate that both legacy distribution artifacts keep the same public exports.
const test = require("node:test");
const assert = require("node:assert/strict");
const original = require("../out/dragonBones.js");
const minified = require("../out/dragonBones.min.js");

test("unminified and minified builds retain the public core classes", () => {
    for (const key of ["DragonBones", "WorldClock", "BaseObject", "Matrix", "Armature", "Animation"]) {
        assert.equal(typeof original[key], "function", key + " missing from regular build");
        assert.equal(typeof minified[key], "function", key + " missing from minified build");
    }
});

test("minification retains WorldClock behavior", () => {
    const originalClock = new original.WorldClock();
    const minifiedClock = new minified.WorldClock();
    originalClock.advanceTime(0.5);
    minifiedClock.advanceTime(0.5);
    assert.equal(originalClock.time, minifiedClock.time);
});
