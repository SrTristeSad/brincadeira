// Preserve the mathematical behavior of the original public Matrix API.
const test = require("node:test");
const assert = require("node:assert/strict");
const { Matrix } = require("../out/dragonBones.js");

test("identity and copyFrom preserve the six matrix coefficients", () => {
    const original = new Matrix(2, 3, 4, 5, 6, 7);
    const copy = new Matrix().copyFrom(original);
    assert.notStrictEqual(copy, original);
    assert.deepEqual(
        [copy.a, copy.b, copy.c, copy.d, copy.tx, copy.ty],
        [2, 3, 4, 5, 6, 7]
    );
    assert.strictEqual(copy.identity(), copy);
    assert.deepEqual(
        [copy.a, copy.b, copy.c, copy.d, copy.tx, copy.ty],
        [1, 0, 0, 1, 0, 0]
    );
});

test("transformPoint retains translation and delta semantics", () => {
    const matrix = new Matrix(2, 0, 0, 3, 5, -7);
    const point = { x: 0, y: 0 };
    matrix.transformPoint(4, 5, point);
    assert.deepEqual(point, { x: 13, y: 8 });
    matrix.transformPoint(4, 5, point, true);
    assert.deepEqual(point, { x: 8, y: 15 });
});

test("invert restores a point transformed by a nonsingular matrix", () => {
    const matrix = new Matrix(2, 0, 0, 3, 5, -7);
    const inverse = new Matrix().copyFrom(matrix).invert();
    const transformed = { x: 0, y: 0 };
    const restored = { x: 0, y: 0 };
    matrix.transformPoint(4, 5, transformed);
    inverse.transformPoint(transformed.x, transformed.y, restored);
    assert.ok(Math.abs(restored.x - 4) < 1e-12);
    assert.ok(Math.abs(restored.y - 5) < 1e-12);
});

test("transformRectangle preserves integer bounding-box behavior", () => {
    const matrix = new Matrix(2, 0, 0, 3, 5, -7);
    const rectangle = { x: 1, y: 2, width: 3, height: 4 };
    matrix.transformRectangle(rectangle);
    assert.deepEqual(rectangle, { x: 7, y: -1, width: 6, height: 12 });
});
