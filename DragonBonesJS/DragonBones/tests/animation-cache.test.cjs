// Regression coverage for explicit animation cache initialization.
const test = require("node:test");
const assert = require("node:assert/strict");
const { BaseObject, AnimationData } = require("../out/dragonBones.js");

function createAnimation(duration = 1, scale = 1) {
    const animation = BaseObject.borrowObject(AnimationData);
    animation.duration = duration;
    animation.scale = scale;
    animation.parent = {
        sortedBones: [{ name: "root" }],
        sortedSlots: [{ name: "hand" }]
    };
    return animation;
}

test("cacheFrames initializes every frame flag to false", () => {
    const animation = createAnimation(1);
    try {
        animation.cacheFrames(12);
        assert.equal(animation.cachedFrames.length, 13);
        assert.deepEqual(animation.cachedFrames, Array(13).fill(false));
    }
    finally {
        animation.returnToPool();
    }
});

test("cacheFrames creates no sparse frame flags", () => {
    const animation = createAnimation(1);
    try {
        animation.cacheFrames(10);
        for (let i = 0; i < animation.cachedFrames.length; i++) {
            assert.equal(Object.prototype.hasOwnProperty.call(animation.cachedFrames, i), true);
            assert.strictEqual(animation.cachedFrames[i], false);
        }
    }
    finally {
        animation.returnToPool();
    }
});

test("cacheFrames keeps a single initialized frame for zero duration", () => {
    const animation = createAnimation(0);
    try {
        animation.cacheFrames(5);
        assert.deepEqual(animation.cachedFrames, [false]);
    }
    finally {
        animation.returnToPool();
    }
});

test("cacheFrames retains initialized bone and slot index tables", () => {
    const animation = createAnimation(1);
    try {
        animation.cacheFrames(4);
        assert.deepEqual(animation.cachedFrames, Array(5).fill(false));
        assert.deepEqual(animation.boneCachedFrameIndices.root, Array(5).fill(-1));
        assert.deepEqual(animation.slotCachedFrameIndices.hand, Array(5).fill(-1));
    }
    finally {
        animation.returnToPool();
    }
});
