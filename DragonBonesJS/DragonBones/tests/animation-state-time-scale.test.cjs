// Regression checks for independent AnimationState playback speed.
const test = require("node:test");
const assert = require("node:assert/strict");
const { AnimationState, BaseObject } = require("../out/dragonBones.js");

function createState() {
    const state = BaseObject.borrowObject(AnimationState);
    // Run the real advanceTime method without a renderer or rig. A zero-weight
    // state returns before evaluating bone/slot timelines.
    state._timelineDirty = 0;
    state._playheadState = 3;
    state._fadeState = 0;
    state._subFadeState = 0;
    state._weight = 0;
    state._actionTimeline = { playState: 1 };
    return state;
}

function releaseState(state) {
    // _actionTimeline is a deliberately minimal test stub, not a pooled object.
    state._actionTimeline = null;
    state.returnToPool();
}

test("invalid individual playback speed does not poison accumulated time", () => {
    const state = createState();
    try {
        for (const speed of [NaN, Infinity, -Infinity]) {
            state.timeScale = speed;
            state.advanceTime(0.25, 0);
            assert.equal(state._time, 0);
        }
        state.timeScale = 1;
        state.advanceTime(0.25, 0);
        assert.equal(state._time, 0.25);
    }
    finally {
        releaseState(state);
    }
});

test("non-finite elapsed time never reaches fade or playhead", () => {
    const state = createState();
    try {
        state._fadeState = 1;
        state.fadeTotalTime = 2;
        for (const delta of [NaN, Infinity, -Infinity]) {
            state.advanceTime(delta, 0);
            assert.equal(state._fadeTime, 0);
            assert.equal(state._time, 0);
        }
        state.advanceTime(0.25, 0);
        assert.equal(state._fadeTime, 0.25);
        assert.equal(state._time, 0.25);
    }
    finally {
        releaseState(state);
    }
});

test("multiplication overflow leaves AnimationState retryable", () => {
    const state = createState();
    try {
        state.timeScale = Number.MAX_VALUE;
        state.advanceTime(Number.MAX_VALUE, 0);
        assert.equal(state._time, 0);
        state.timeScale = 1;
        state.advanceTime(0.5, 0);
        assert.equal(state._time, 0.5);
    }
    finally {
        releaseState(state);
    }
});

test("accumulated AnimationState time cannot overflow", () => {
    const state = createState();
    try {
        state._time = Number.MAX_VALUE;
        state.advanceTime(Number.MAX_VALUE, 0);
        assert.equal(state._time, Number.MAX_VALUE);
        state._time = 0;
        state.advanceTime(0.5, 0);
        assert.equal(state._time, 0.5);
    }
    finally {
        releaseState(state);
    }
});

test("finite negative speeds and zero elapsed time remain valid", () => {
    const state = createState();
    try {
        state.timeScale = -2;
        state.advanceTime(0.25, 0);
        assert.equal(state._time, -0.5);
        state.advanceTime(0, 0);
        assert.equal(state._time, -0.5);
    }
    finally {
        releaseState(state);
    }
});

test("paused fade can complete with invalid speed without corrupting playhead", () => {
    const state = createState();
    try {
        state._playheadState = 2;
        state._fadeState = -1;
        state._subFadeState = 0;
        state.fadeTotalTime = 1;
        state.timeScale = NaN;
        state.advanceTime(0.5, 0);
        assert.equal(state._fadeTime, 0.5);
        assert.equal(state._time, 0);
        state.advanceTime(0.5, 0);
        assert.equal(state._fadeProgress, 1);
        assert.equal(state._playheadState, 3);
        assert.equal(state._time, 0);

        state.timeScale = 1;
        state.advanceTime(0.25, 0);
        assert.equal(state._time, 0.25);
    }
    finally {
        releaseState(state);
    }
});
