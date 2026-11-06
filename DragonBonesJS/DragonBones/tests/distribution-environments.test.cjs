// Verify legacy distribution formats in isolated loader contexts.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const outputs = ["dragonBones.js", "dragonBones.min.js"];

for (const filename of outputs) {
    const script = fs.readFileSync(path.join(__dirname, "..", "out", filename), "utf8");

    test(filename + " registers an AMD module without depending on itself", () => {
        let registration = null;
        function define(dependencies, factory) {
            assert.equal(registration, null, "AMD module registered more than once");
            registration = { dependencies: Array.from(dependencies), factory };
        }
        define.amd = {};

        vm.runInNewContext(script, { define, console, Date }, { filename });
        assert.ok(registration, "AMD loader did not receive a registration");
        assert.deepEqual(registration.dependencies, []);
        assert.equal(typeof registration.factory().DragonBones, "function");
    });

    test(filename + " populates the provided exports-only object", () => {
        // Wrap exports in a function parameter to model a consumer-owned object.
        // Reassigning the local exports variable must not count as exporting.
        const destination = {};
        vm.runInNewContext(
            "(function (exports) {\n" + script + "\n})(destination);",
            { destination, console, Date },
            { filename }
        );
        for (const member of ["DragonBones", "WorldClock", "Animation", "Matrix"]) {
            assert.equal(typeof destination[member], "function", member + " not exported");
        }
    });
}
