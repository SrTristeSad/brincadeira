// A truncated .dbbin header should be rejected before typed-array views are created.
const test = require("node:test");
const assert = require("node:assert/strict");
const { BinaryDataParser } = require("../out/dragonBones.js");

function makeBinary(headerBytes, declaredLength = headerBytes.length) {
    const buffer = new ArrayBuffer(12 + headerBytes.length);
    const bytes = new Uint8Array(buffer);
    bytes.set([68, 66, 68, 84]); // DBDT
    new Uint32Array(buffer, 8, 1)[0] = declaredLength;
    bytes.set(headerBytes, 12);
    return buffer;
}

test("binary parser rejects non-ArrayBuffer inputs without throwing", () => {
    const parser = new BinaryDataParser();
    for (const input of [null, undefined, new Uint8Array(12)]) {
        // assert.equal also fails if parsing throws.
        assert.equal(parser.parseDragonBonesData(input), null);
    }
});

test("binary parser rejects incomplete fixed headers", () => {
    const parser = new BinaryDataParser();
    for (const size of [0, 7, 8, 11]) {
        const buffer = new ArrayBuffer(size);
        new Uint8Array(buffer).set([68, 66, 68, 84].slice(0, size));
        assert.equal(parser.parseDragonBonesData(buffer), null);
    }
});

test("binary parser rejects header lengths that exceed available bytes", () => {
    const parser = new BinaryDataParser();
    const truncated = makeBinary(Buffer.from("{}"), 1000);
    const initialBinary = parser._binary;
    assert.equal(parser.parseDragonBonesData(truncated), null);
    // A corrupt length must not change the parser's binary state.
    assert.strictEqual(parser._binary, initialBinary);
});

test("binary parser rejects an empty JSON header", () => {
    const parser = new BinaryDataParser();
    assert.equal(parser.parseDragonBonesData(makeBinary(Buffer.alloc(0), 0)), null);
});

test("binary parser accepts a complete header after a truncated attempt", () => {
    const parser = new BinaryDataParser();
    assert.equal(parser.parseDragonBonesData(makeBinary(Buffer.from("{}"), 99)), null);

    const header = Buffer.from(JSON.stringify({ version: "5.6", name: "minimal" }), "utf8");
    const data = parser.parseDragonBonesData(makeBinary(header), 0.5);
    assert.ok(data);
    try {
        assert.equal(data.version, "5.6");
        assert.equal(data.name, "minimal");
    }
    finally {
        data.returnToPool();
    }
});

test("binary parser rejects malformed JSON headers without throwing", () => {
    const parser = new BinaryDataParser();
    for (const text of ["{", "{\"version\":", "not-json"]) {
        const bytes = Buffer.from(text, "utf8");
        assert.equal(parser.parseDragonBonesData(makeBinary(bytes)), null);
    }
});

test("binary parser rejects JSON primitives and arrays as headers", () => {
    const parser = new BinaryDataParser();
    for (const text of ["null", "false", "42", "\"text\"", "[]"]) {
        const bytes = Buffer.from(text, "utf8");
        assert.equal(parser.parseDragonBonesData(makeBinary(bytes)), null);
    }
});

test("invalid JSON preserves parser state from a previous valid binary", () => {
    const parser = new BinaryDataParser();
    const validBytes = Buffer.from(JSON.stringify({
        version: "5.6", name: "previous"
    }), "utf8");
    const data = parser.parseDragonBonesData(makeBinary(validBytes));
    assert.ok(data);
    data.returnToPool();

    const previousBinary = parser._binary;
    const previousOffset = parser._binaryOffset;
    assert.equal(parser.parseDragonBonesData(makeBinary(Buffer.from("{"))), null);
    assert.strictEqual(parser._binary, previousBinary);
    assert.equal(parser._binaryOffset, previousOffset);

    const next = parser.parseDragonBonesData(makeBinary(Buffer.from(JSON.stringify({
        version: "5.6", name: "next"
    }), "utf8")));
    assert.ok(next);
    try {
        assert.equal(next.name, "next");
    }
    finally {
        next.returnToPool();
    }
});
