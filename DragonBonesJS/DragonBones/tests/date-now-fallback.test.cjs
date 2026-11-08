// Regression test for legacy runtimes without Date.now.
const test = require("node:test");
const assert = require("node:assert/strict");

test("WorldClock.advanceTime works without Date.now", function () {
    const OriginalDate = global.Date;

    function DateWithoutNow() {
        return new OriginalDate();
    }
    DateWithoutNow.prototype = OriginalDate.prototype;
    DateWithoutNow.parse = OriginalDate.parse;
    DateWithoutNow.UTC = OriginalDate.UTC;

    try {
        global.Date = DateWithoutNow;
        assert.equal(typeof Date.now, "undefined");

        const WorldClock = require("../out/dragonBones.js").WorldClock;
        assert.doesNotThrow(function () {
            new WorldClock().advanceTime(1 / 60);
        });
    }
    finally {
        global.Date = OriginalDate;
    }
});
