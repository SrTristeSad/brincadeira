// Validate package entry points after npm test has completed its build step.
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");
const pkg = require("../package.json");

const baseDir = path.resolve(__dirname, "..");

test("package entry points exist after npm run build", () => {
    assert.equal(pkg.main, "./out/dragonBones.js");
    assert.equal(pkg.types, "./out/dragonBones.d.ts");
    assert.ok(fs.existsSync(path.resolve(baseDir, pkg.main)), "missing runtime output");
    assert.ok(fs.existsSync(path.resolve(baseDir, pkg.types)), "missing TypeScript declarations");
});

test("package root resolves to the existing public API", () => {
    const runtime = require("../");
    assert.equal(typeof runtime.WorldClock, "function");
    assert.equal(typeof runtime.BaseObject, "function");
    assert.equal(typeof runtime.DragonBones, "function");
});

test("package preserves bundled MIT licensing", () => {
    assert.equal(pkg.license, "MIT");
    assert.ok(fs.existsSync(path.resolve(baseDir, "LICENSE")));
    assert.ok(pkg.files.includes("out/"));
});
