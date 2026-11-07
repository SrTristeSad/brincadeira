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

test("invalid armature cache rates leave clip caching disabled", () => {
    const { ArmatureData } = require("../out/dragonBones.js");
    const armature = BaseObject.borrowObject(ArmatureData);
    const clip = BaseObject.borrowObject(AnimationData);
    clip.name = "walk";
    clip.duration = 1;
    armature.addAnimation(clip);
    try {
        for (const rate of [0, -1, NaN, Infinity, -Infinity]) {
            assert.doesNotThrow(() => armature.cacheFrames(rate));
            assert.equal(armature.cacheFrameRate, 0);
            assert.equal(clip.cacheFrameRate, 0);
            assert.deepEqual(clip.cachedFrames, []);
        }
    }
    finally {
        armature.returnToPool();
    }
});

test("a valid armature cache rate works after invalid attempts", () => {
    const { ArmatureData } = require("../out/dragonBones.js");
    const armature = BaseObject.borrowObject(ArmatureData);
    const clip = BaseObject.borrowObject(AnimationData);
    clip.name = "walk";
    clip.duration = 1;
    armature.addAnimation(clip);
    try {
        armature.cacheFrames(0);
        armature.cacheFrames(24);
        assert.equal(armature.cacheFrameRate, 24);
        assert.equal(clip.cacheFrameRate, 24);
        assert.deepEqual(clip.cachedFrames, Array(25).fill(false));
    }
    finally {
        armature.returnToPool();
    }
});

test("cacheFrames rejects invalid animation durations without poisoning the cache", () => {
    for (const duration of [NaN, Infinity, -1]) {
        const animation = createAnimation(duration);
        try {
            assert.doesNotThrow(() => animation.cacheFrames(24));
            assert.equal(animation.cacheFrameRate, 0);
            assert.deepEqual(animation.cachedFrames, []);
            animation.duration = 1;
            animation.cacheFrames(24);
            assert.equal(animation.cacheFrameRate, 24);
            assert.deepEqual(animation.cachedFrames, Array(25).fill(false));
        }
        finally {
            animation.returnToPool();
        }
    }
});

test("cacheFrames rejects invalid animation scales and rates", () => {
    for (const scale of [NaN, Infinity, -Infinity]) {
        const animation = createAnimation(1, scale);
        try {
            assert.doesNotThrow(() => animation.cacheFrames(24));
            assert.equal(animation.cacheFrameRate, 0);
            animation.scale = 1;
            animation.cacheFrames(24);
            assert.equal(animation.cacheFrameRate, 24);
        }
        finally {
            animation.returnToPool();
        }
    }

    for (const rate of [NaN, Infinity, -Infinity, 0, -1]) {
        const animation = createAnimation(1);
        try {
            assert.doesNotThrow(() => animation.cacheFrames(rate));
            assert.equal(animation.cacheFrameRate, 0);
        }
        finally {
            animation.returnToPool();
        }
    }
});

test("cacheFrames avoids array lengths larger than the ES5 limit", () => {
    const animation = createAnimation(3000000000);
    try {
        assert.doesNotThrow(() => animation.cacheFrames(2));
        assert.equal(animation.cacheFrameRate, 0);
        assert.deepEqual(animation.cachedFrames, []);
        animation.duration = 1;
        animation.cacheFrames(2);
        assert.deepEqual(animation.cachedFrames, [false, false, false]);
    }
    finally {
        animation.returnToPool();
    }
});

test("valid cache rates still initialize bone and slot frame tables", () => {
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
