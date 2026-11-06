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

test("invert uses the identity fallback for all singular diagonal matrices", () => {
    const coefficients = matrix => [matrix.a, matrix.b, matrix.c, matrix.d, matrix.tx, matrix.ty];
    for (const values of [
        [0, 0, 0, 2, 5, 7],
        [2, 0, 0, 0, 5, 7],
        [0, 0, 0, 0, 5, 7]
    ]) {
        const matrix = new Matrix(...values);
        assert.strictEqual(matrix.invert(), matrix);
        assert.deepEqual(coefficients(matrix), [1, 0, 0, 1, 0, 0]);
    }
});

test("invert keeps the existing fallback for non-diagonal singular matrices", () => {
    const matrix = new Matrix(1, 1, 1, 1, 5, 7);
    matrix.invert();
    assert.deepEqual(
        [matrix.a, matrix.b, matrix.c, matrix.d, matrix.tx, matrix.ty],
        [1, 0, 0, 1, 0, 0]
    );
});

test("invert correctly restores points under shear and translation", () => {
    const matrix = new Matrix(2, 1, 3, 4, 5, -3);
    const inverse = new Matrix().copyFrom(matrix).invert();
    const point = { x: 0, y: 0 };
    const result = { x: 0, y: 0 };
    matrix.transformPoint(4, 8, point);
    inverse.transformPoint(point.x, point.y, result);
    assert.ok(Math.abs(result.x - 4) < 1e-12);
    assert.ok(Math.abs(result.y - 8) < 1e-12);
});
