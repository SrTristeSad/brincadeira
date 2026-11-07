// Guard Animation.advanceTime against invalid independent/inherited time scales.
const test = require("node:test");
const assert = require("node:assert/strict");
const { BaseObject, Animation } = require("../out/dragonBones.js");

function createAnimation() {
    const animation = BaseObject.borrowObject(Animation);
    const advances = [];
    animation._armature = { inheritAnimation: false, _parent: null };
    animation._animationStates.push({
        _fadeState: 0,
        _subFadeState: 0,
        animationData: { cacheFrameRate: 0 },
        advanceTime(value) { advances.push(value); }
    });
    return {
        animation,
        advances,
        dispose() {
            // This recording state is a stub, not a pooled AnimationState.
            animation._animationStates.length = 0;
            animation.returnToPool();
        }
    };
}

test("invalid animation time scales never reach animation states", () => {
    const context = createAnimation();
    try {
        for (const scale of [NaN, Infinity, -Infinity]) {
            context.animation.timeScale = scale;
            context.animation.advanceTime(0.25);
            assert.deepEqual(context.advances, []);
        }
        context.animation.timeScale = 1;
        context.animation.advanceTime(0.25);
        assert.deepEqual(context.advances, [0.25]);
    }
    finally {
        context.dispose();
    }
});

test("non-finite elapsed time does not reach animation states", () => {
    const context = createAnimation();
    try {
        for (const elapsed of [NaN, Infinity, -Infinity]) {
            context.animation.advanceTime(elapsed);
        }
        assert.deepEqual(context.advances, []);
        context.animation.advanceTime(0.5);
        assert.deepEqual(context.advances, [0.5]);
    }
    finally {
        context.dispose();
    }
});

test("finite animation time inputs that overflow are ignored", () => {
    const context = createAnimation();
    try {
        context.animation.timeScale = Number.MAX_VALUE;
        context.animation.advanceTime(Number.MAX_VALUE);
        assert.deepEqual(context.advances, []);
        context.animation.timeScale = 1;
        context.animation.advanceTime(0.125);
        assert.deepEqual(context.advances, [0.125]);
    }
    finally {
        context.dispose();
    }
});

test("inherited invalid animation speed is rejected and can recover", () => {
    const context = createAnimation();
    try {
        const parentAnimation = { _inheritTimeScale: Infinity };
        context.animation._armature.inheritAnimation = true;
        context.animation._armature._parent = { _armature: { animation: parentAnimation } };
        context.animation.advanceTime(0.25);
        assert.deepEqual(context.advances, []);

        parentAnimation._inheritTimeScale = 2;
        context.animation.advanceTime(0.25);
        assert.deepEqual(context.advances, [0.5]);
    }
    finally {
        context.dispose();
    }
});

test("finite negative animation speed and zero-time updates retain behavior", () => {
    const context = createAnimation();
    try {
        context.animation.timeScale = -2;
        context.animation.advanceTime(0.25);
        context.animation.timeScale = 1;
        context.animation.advanceTime(0);
        assert.deepEqual(context.advances, [-0.5, 0]);
    }
    finally {
        context.dispose();
    }
});
